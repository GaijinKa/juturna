import logging
import pathlib
import threading

import pytest

from juturna.components import Pipeline
from juturna.components import pipeline_layers
from juturna.components import layered_stop

from tests._loopback import LoopbackTransport


def _node(name, node_type, worker, **configuration):
    return {
        'name': name,
        'type': f'contrib.jt_test.nodes.{node_type}',
        'configuration': configuration,
        'worker': worker,
    }


def _pipeline(tmp_path, nodes, links):
    return {
        'pipeline': {
            'name': 'layered',
            'id': 'layered-1',
            'folder': str(tmp_path),
            'nodes': nodes,
            'links': [{'from': a, 'to': b} for a, b in links],
        },
    }


def _chain_config(tmp_path):
    return _pipeline(
        tmp_path,
        [
            _node('s', 'DataStreamer', 'main', rate=20),
            _node('a', 'PassthroughIdentity', 'x', delay=0.05),
            _node('b', 'PassthroughIdentity', 'y', delay=0.05),
            _node('k', 'Dumper', 'main'),
        ],
        [('s', 'a'), ('a', 'b'), ('b', 'k')],
    )


def _fork_config(tmp_path):
    return _pipeline(
        tmp_path,
        [
            _node('s', 'DataStreamer', 'main', rate=20),
            _node('a', 'PassthroughIdentity', 'x', delay=0.05),
            _node('b', 'PassthroughIdentity', 'y', delay=0.05),
            _node('k1', 'Dumper', 'main'),
            _node('k2', 'Dumper', 'main'),
        ],
        [('s', 'a'), ('s', 'b'), ('a', 'k1'), ('b', 'k2')],
    )


@pytest.fixture
def workers():
    """Build one pipeline per worker of a config; kill them all at the end."""
    pipes = dict()

    def _build(config, names=('main', 'x', 'y')):
        peers = dict()

        for worker in names:
            pipe = Pipeline(config, worker=worker)
            pipe._transport = LoopbackTransport(peers, delay=0.01)
            pipes[worker] = pipe

        for node in config['pipeline']['nodes']:
            peers[node['name']] = pipes[node['worker']]

        for pipe in pipes.values():
            pipe.warmup()

        for pipe in pipes.values():
            pipe.start()

        return pipes

    yield _build

    for pipe in pipes.values():
        pipe.kill()

    for pipe in pipes.values():
        pipe.destroy()


def _sent_count(tmp_path):
    # DataStreamer dumps message_<version>.json after transmitting each one
    return len(list(pathlib.Path(tmp_path, 's').glob('message_*.json')))


def test_layered_stop_loses_no_message_in_flight(
    tmp_path, wait_for_condition, workers
):
    config = _chain_config(tmp_path)
    pipes = workers(config)
    sink = pipes['main']._nodes['k']

    started = wait_for_condition(lambda: len(sink.versions) >= 3, timeout=10)
    assert started, f'Expected 3 messages at k, got {sink.versions}'

    layered_stop(list(pipes.values()), pipeline_layers(config))

    sent = _sent_count(tmp_path)
    assert sink.versions == list(range(sent)), sink.versions


def test_dead_link_does_not_block_stop_or_the_other_branch(
    tmp_path, wait_for_condition, workers, jt_records
):
    config = _fork_config(tmp_path)
    pipes = workers(config)
    k1 = pipes['main']._nodes['k1']
    k2 = pipes['main']._nodes['k2']

    started = wait_for_condition(lambda: len(k2.versions) >= 2, timeout=10)
    assert started, f'Expected 2 messages at k2, got {k2.versions}'

    pipes['main']._remote_destinations['b'].kill_link()
    after_kill = len(k1.versions)
    grows = wait_for_condition(
        lambda: len(k1.versions) >= after_kill + 5, timeout=10
    )
    assert grows, f'k1 stuck at {len(k1.versions)} after the kill'

    stopper = threading.Thread(
        target=layered_stop,
        args=(list(pipes.values()), pipeline_layers(config)),
        daemon=True,
    )
    stopper.start()
    stopper.join(timeout=30)

    assert not stopper.is_alive(), 'layered_stop blocked on the dead link'
    sent = _sent_count(tmp_path)
    assert k1.versions == list(range(sent)), k1.versions

    warnings = [
        r
        for r in jt_records
        if r.levelno == logging.WARNING and 'link to b is dead' in r.msg
    ]
    assert len(warnings) == 1, f'Expected 1 warning, got {len(warnings)}'


class FakeParticipant:
    def __init__(self, alive=True, claims=True):
        self.alive = alive
        self.claims = claims
        self.calls = list()

    def begin_stop(self):
        self.calls.append('begin_stop')

        return self.claims

    def close_remote(self, nodes):
        self.calls.append(('close_remote', list(nodes)))

    def stop_nodes(self, nodes):
        self.calls.append(('stop_nodes', list(nodes)))

    def end_stop(self):
        self.calls.append('end_stop')

    def abort_stop(self):
        self.calls.append('abort_stop')


def test_dead_participant_is_skipped_and_stopped_participant_not_ended():
    live, dead, stopped = (
        FakeParticipant(),
        FakeParticipant(alive=False),
        FakeParticipant(claims=False),
    )

    layered_stop([live, dead, stopped], [['s'], ['k']])

    assert live.calls == [
        'begin_stop',
        ('close_remote', ['s']),
        ('stop_nodes', ['s']),
        ('close_remote', ['k']),
        ('stop_nodes', ['k']),
        'end_stop',
    ], live.calls
    assert dead.calls == [], dead.calls
    assert stopped.calls == ['begin_stop'], stopped.calls


def test_layered_stop_aborts_the_claimed_participants_on_failure():
    good, stopped = FakeParticipant(), FakeParticipant(claims=False)
    failing = FakeParticipant()

    def _fail(nodes):
        raise RuntimeError('boom')

    failing.stop_nodes = _fail

    with pytest.raises(RuntimeError, match='boom'):
        layered_stop([good, failing, stopped], [['s']])

    assert good.calls[-1] == 'abort_stop', good.calls
    assert failing.calls[-1] == 'abort_stop', failing.calls
    assert 'abort_stop' not in stopped.calls, stopped.calls
