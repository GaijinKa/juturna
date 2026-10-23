import contextlib
import copy
import os
import dataclasses
import logging
import pathlib
import subprocess
import sys
import threading

import pytest

pytest.importorskip('grpc')

import juturna as jt

from juturna.components import Message
from juturna.components import Pipeline
from juturna.components import layered_stop
from juturna.components import pipeline_layers
from juturna.components.exceptions import PipelineNotRunningError
from juturna.payloads import BasePayload
from juturna.payloads import BytesPayload


def _node(name, node_type, worker, **configuration):
    return {
        'name': name,
        'type': f'contrib.jt_test.nodes.{node_type}',
        'configuration': configuration,
        'worker': worker,
    }


def _config(folder, pipe_id, nodes, links):
    return {
        'pipeline': {
            'name': pipe_id,
            'id': pipe_id,
            'folder': str(folder),
            'nodes': nodes,
            'links': [{'from': a, 'to': b} for a, b in links],
        },
    }


def _stream_config(folder, pipe_id='grpc-1'):
    return _config(
        folder,
        pipe_id,
        [
            _node('s', 'DataStreamer', 'main', rate=20),
            _node('k', 'Dumper', 'x'),
        ],
        [('s', 'k')],
    )


def _sent_count(folder):
    # DataStreamer dumps message_<version>.json after transmitting each one
    return len(list(pathlib.Path(folder, 's').glob('message_*.json')))


@dataclasses.dataclass(frozen=True)
class Unsendable(BasePayload):
    value: int = 0


def _kill(pipe):
    # a pipeline only warmed up cannot be killed, destroy() is enough
    with contextlib.suppress(PipelineNotRunningError):
        pipe.kill()


@pytest.fixture
def cluster():
    """Start data servers and pipelines; tear everything down at the end."""
    from juturna.transport.grpc import DataServer

    servers, senders, receivers = list(), list(), list()

    class Cluster:
        def server(self, max_streams=16):
            server = DataServer('127.0.0.1:0', max_streams=max_streams)
            server.address = server.start()
            servers.append(server)

            return server

        def build(self, config, server, queue_size=64, start=True):
            """One pipeline per worker; the nodes of x live on `server`."""
            pipe_id = config['pipeline']['id']
            peers = {
                node['name']: server.address
                for node in config['pipeline']['nodes']
                if node['worker'] == 'x'
            }
            pipes = dict()

            for worker in ('main', 'x'):
                worker_config = copy.deepcopy(config)
                worker_config['pipeline']['transport'] = {
                    'name': 'grpc',
                    'worker': worker,
                    'pipe_id': pipe_id,
                    'peers': peers,
                    'queue_size': queue_size,
                }
                pipes[worker] = Pipeline(worker_config, worker=worker)

            senders.append(pipes['main'])
            receivers.append(pipes['x'])

            for pipe in pipes.values():
                pipe.warmup()

            server.register(pipe_id, pipes['x']._nodes)

            if start:
                pipes['x'].start()
                pipes['main'].start()

            return pipes

    yield Cluster()

    # senders first, so no handler is fed while the receivers go away
    for pipe in senders:
        _kill(pipe)

    for server in servers:
        for pipe in receivers:
            server.unregister(pipe._pipe_id)

        server.stop(0)

    for pipe in receivers:
        _kill(pipe)

    for pipe in senders + receivers:
        pipe.destroy()


def test_messages_arrive_in_order_and_close_waits_for_them(
    tmp_path, wait_for_condition, cluster
):
    config = _stream_config(tmp_path)
    pipes = cluster.build(config, cluster.server())
    sink = pipes['x']._nodes['k']

    started = wait_for_condition(lambda: len(sink.versions) >= 5, timeout=10)
    assert started, f'Expected 5 messages at k, got {sink.versions}'

    layered_stop(list(pipes.values()), pipeline_layers(config))

    sent = _sent_count(tmp_path)
    assert sink.versions == list(range(sent)), (
        f'Expected versions 0..{sent - 1}, got {sink.versions}'
    )


def test_unsendable_payload_is_dropped_and_local_sibling_still_receives(
    tmp_path, wait_for_condition, cluster, jt_records
):
    config = _config(
        tmp_path,
        'grpc-strict',
        [
            _node('p', 'PassthroughIdentity', 'main', delay=0),
            _node('r', 'Dumper', 'x'),
            _node('l', 'Dumper', 'main'),
        ],
        # the remote link first: a raising put would skip the local one
        [('p', 'r'), ('p', 'l')],
    )
    pipes = cluster.build(config, cluster.server())
    sender = pipes['main']._nodes['p']
    local = pipes['main']._nodes['l']
    remote = pipes['x']._nodes['r']

    for version in range(3):
        sender.put(
            Message(creator='test', version=version, payload=Unsendable())
        )

    arrived = wait_for_condition(lambda: len(local.versions) == 3, timeout=10)
    assert arrived, f'Expected 3 messages at l, got {local.versions}'

    layered_stop(list(pipes.values()), pipeline_layers(config))

    assert remote.versions == [], f'r received {remote.versions}'
    dropped = [r for r in jt_records if 'cannot be sent' in r.getMessage()]
    assert len(dropped) == 1, f'Expected 1 warning, got {len(dropped)}'
    failures = sender.health['update_failures']
    assert failures == 0, f'Expected no update failures, got {failures}'


def test_streams_are_routed_by_pipe_id(tmp_path, wait_for_condition, cluster):
    server = cluster.server()
    configs = [
        _stream_config(tmp_path / 'a', 'grpc-a'),
        _stream_config(tmp_path / 'b', 'grpc-b'),
    ]
    all_pipes = [cluster.build(config, server) for config in configs]
    sinks = [pipes['x']._nodes['k'] for pipes in all_pipes]

    started = wait_for_condition(
        lambda: all(len(sink.versions) >= 5 for sink in sinks), timeout=10
    )
    assert started, f'Expected 5 messages each, got {sinks[0].versions}, ' + (
        f'{sinks[1].versions}'
    )

    for config, pipes in zip(configs, all_pipes, strict=True):
        layered_stop(list(pipes.values()), pipeline_layers(config))

    for config, sink in zip(configs, sinks, strict=True):
        sent = _sent_count(config['pipeline']['folder'])
        assert sink.versions == list(range(sent)), (
            f'{config["pipeline"]["id"]}: expected 0..{sent - 1}, '
            f'got {sink.versions}'
        )


def test_dead_receiver_unblocks_writers(
    tmp_path, wait_for_condition, cluster, jt_records, monkeypatch
):
    from juturna.transport.grpc import GrpcTransport

    monkeypatch.setattr(jt.meta, 'JUTURNA_MAX_QUEUE_SIZE', 2)
    server = cluster.server()
    config = _stream_config(tmp_path)
    # k is registered but never started: its queue fills and stays full
    cluster.build(config, server, start=False)
    transport = GrpcTransport(
        worker='main',
        pipe_id='grpc-1',
        peers={'k': server.address},
        queue_size=1,
    )
    destination = transport.remote_destination('k')
    in_put = [False, False]

    def _write(index):
        payload = BytesPayload(cnt=b'\0' * 256_000)

        for version in range(1000):
            message = Message(creator='w', version=version, payload=payload)
            message._freeze()
            in_put[index] = True
            destination.put(message)
            in_put[index] = False

            if destination._dead.is_set():
                return

    writers = [
        threading.Thread(target=_write, args=(i,), daemon=True)
        for i in range(2)
    ]

    for writer in writers:
        writer.start()

    blocked = wait_for_condition(
        lambda: all(in_put) and destination._queue.full(), timeout=20
    )
    assert blocked, 'the writers never blocked on the full link'

    server.stop(0)

    for writer in writers:
        writer.join(timeout=20)

    assert not any(w.is_alive() for w in writers), 'a writer is still blocked'
    lost = [
        r
        for r in jt_records
        if r.levelno == logging.WARNING and 'lost' in r.getMessage()
    ]
    assert len(lost) == 1, f'Expected 1 lost warning, got {len(lost)}'


def test_kill_releases_the_receiver_thread(
    tmp_path, wait_for_condition, cluster
):
    from juturna.transport.grpc import GrpcTransport

    server = cluster.server(max_streams=1)
    config = _stream_config(tmp_path)
    pipes = cluster.build(config, server)
    sink = pipes['x']._nodes['k']

    started = wait_for_condition(lambda: len(sink.versions) >= 2, timeout=10)
    assert started, f'Expected 2 messages at k, got {sink.versions}'

    pipes['main'].kill()

    def _served():
        # a refused stream is dead for good: try again on a fresh one
        transport = GrpcTransport(
            worker='other', pipe_id='grpc-1', peers={'k': server.address}
        )
        destination = transport.remote_destination('k')
        destination.put(Message(creator='o', version=10_000, payload=None))
        destination.close()

        return 10_000 in sink.versions

    served = wait_for_condition(_served, timeout=20, interval=0.2)
    assert served, 'the stream of the killed pipeline still holds the thread'


def test_wildcard_data_address_is_refused():
    from juturna.transport.grpc import DataServer

    for address in ('0.0.0.0:0', '[::]:0'):
        with pytest.raises(ValueError, match='give an address'):
            DataServer(address).start()


def test_unknown_peer_is_a_value_error():
    from juturna.transport.grpc import GrpcTransport

    transport = GrpcTransport(worker='main', pipe_id='p', peers={})

    with pytest.raises(ValueError, match='k'):
        transport.remote_destination('k')


def test_import_juturna_does_not_import_grpc(tmp_path):
    script = f"""
import sys
sys.modules['grpc'] = None
import juturna
from juturna.components import Pipeline
pipe = Pipeline({{'pipeline': {{
    'name': 'g', 'id': 'g', 'folder': {str(tmp_path)!r},
    'nodes': [{{'name': 'k', 'type': 'contrib.jt_test.nodes.Dumper',
               'configuration': {{}}}}],
    'links': [],
}}}})
pipe.warmup()
pipe.start()
pipe.stop()
pipe.destroy()
"""
    result = subprocess.run(
        [sys.executable, '-c', script],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=pathlib.Path(__file__).parent.parent,
        env={**os.environ, 'PYTHONPATH': 'tests/_nodes'},
    )

    assert result.returncode == 0, result.stderr
