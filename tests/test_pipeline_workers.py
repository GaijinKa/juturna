import pytest

from juturna.components import Pipeline
from juturna.components import pipeline_layers
from juturna.names import PipelineStatus
from juturna.transport import ThreadingTransport


class Collector:
    """Stands for a node of another worker: all it needs is put()."""

    def __init__(self):
        self.messages = list()
        self.closed = False
        self.cancelled = False

    def put(self, message):
        self.messages.append(message)

    def close(self):
        self.closed = True

    def cancel(self):
        self.cancelled = True


class RemoteTransport(ThreadingTransport):
    def __init__(self):
        super().__init__()

        self.destinations = dict()

    def remote_destination(self, node_name):
        return self.destinations.setdefault(node_name, Collector())


def _config(tmp_path, sink_worker='b'):
    return {
        'pipeline': {
            'name': 'workers',
            'id': 'workers-1',
            'folder': str(tmp_path),
            'nodes': [
                {
                    'name': 's',
                    'type': 'contrib.jt_test.nodes.DataStreamer',
                    'configuration': {'rate': 20},
                },
                {
                    'name': 'k',
                    'type': 'contrib.jt_test.nodes.Dumper',
                    'configuration': {},
                    'worker': sink_worker,
                },
            ],
            'links': [{'from': 's', 'to': 'k'}],
        },
    }


def test_only_the_nodes_of_the_worker_are_built(tmp_path):
    main = Pipeline(_config(tmp_path))
    main._transport = RemoteTransport()
    main.warmup()

    other = Pipeline(_config(tmp_path), worker='b')
    other.warmup()

    assert list(main._nodes) == ['s'], f'main built {list(main._nodes)}'
    assert list(other._nodes) == ['k'], f'b built {list(other._nodes)}'


def test_link_from_another_worker_adds_an_origin(tmp_path):
    other = Pipeline(_config(tmp_path), worker='b')
    other.warmup()

    origins = other._nodes['k'].origins
    assert origins == ['s'], f'Expected origins [s], got {origins}'


def test_link_to_another_worker_goes_through_the_transport(
    tmp_path, wait_for_condition
):
    transport = RemoteTransport()
    main = Pipeline(_config(tmp_path))
    main._transport = transport

    main.warmup()
    main.start()

    remote = transport.destinations['k']
    arrived = wait_for_condition(lambda: len(remote.messages) >= 2, timeout=5)
    main.stop()

    assert arrived, f'Expected 2 messages, got {len(remote.messages)}'


def test_link_to_another_worker_needs_transport_support(tmp_path):
    main = Pipeline(_config(tmp_path))

    with pytest.raises(ValueError, match='node k runs in another worker'):
        main.warmup()


def test_nodes_default_to_the_main_worker(tmp_path):
    config = _config(tmp_path, sink_worker='main')
    del config['pipeline']['nodes'][1]['worker']

    main = Pipeline(config)
    main.warmup()

    assert sorted(main._nodes) == ['k', 's'], f'built {sorted(main._nodes)}'


def _chain(tmp_path, nodes, extra_links=()):
    """DataStreamer, then PassthroughIdentity nodes, then a Dumper."""
    configs = list()

    for index, (name, worker) in enumerate(nodes):
        if index == 0:
            node_type, configuration = 'DataStreamer', {'rate': 20}
        elif index == len(nodes) - 1:
            node_type, configuration = 'Dumper', {}
        else:
            node_type, configuration = 'PassthroughIdentity', {'delay': 0}

        configs.append(
            {
                'name': name,
                'type': f'contrib.jt_test.nodes.{node_type}',
                'configuration': configuration,
                'worker': worker,
            }
        )

    links = [
        {'from': a, 'to': b}
        for (a, _), (b, _) in zip(nodes, nodes[1:], strict=False)
    ]
    links += [{'from': a, 'to': b} for a, b in extra_links]

    return {
        'pipeline': {
            'name': 'chain',
            'id': 'chain-1',
            'folder': str(tmp_path),
            'nodes': configs,
            'links': links,
        },
    }


def test_pipeline_layers_follow_the_global_graph(tmp_path):
    config = _chain(tmp_path, [('s', 'main'), ('b', 'x'), ('k', 'main')])

    layers = pipeline_layers(config)

    assert layers == [['s'], ['b'], ['k']], f'got {layers}'


def test_pipeline_layers_refuse_a_cycle(tmp_path):
    config = _chain(
        tmp_path, [('a', 'main'), ('b', 'x')], extra_links=[('b', 'a')]
    )

    with pytest.raises(ValueError, match='contains a cycle'):
        pipeline_layers(config)


def test_abort_start_goes_back_to_ready(tmp_path):
    pipe = Pipeline(_chain(tmp_path, [('s', 'main'), ('k', 'main')]))
    pipe.warmup()
    pipe.start()

    try:
        pipe.abort_start()
        status = pipe._status

        pipe.start()
        restarted = pipe._status
    finally:
        pipe.kill()

    assert status == PipelineStatus.READY, f'got {status}'
    assert restarted == PipelineStatus.RUNNING, f'got {restarted}'


def test_abort_start_needs_a_running_pipeline(tmp_path):
    pipe = Pipeline(_chain(tmp_path, [('s', 'main'), ('k', 'main')]))
    pipe.warmup()

    with pytest.raises(RuntimeError):
        pipe.abort_start()


def test_layered_stop_closes_only_the_given_links(tmp_path):
    transport = RemoteTransport()
    pipe = Pipeline(_chain(tmp_path, [('s', 'main'), ('k', 'x')]))
    pipe._transport = transport
    pipe.warmup()
    pipe.start()

    remote = transport.destinations['k']

    assert pipe.begin_stop()
    pipe.stop_nodes(['s', 'unknown'])
    open_after_stop = not remote.closed
    pipe.close_remote(['k', 'unknown'])
    pipe.stop_nodes(['k'])
    pipe.end_stop()

    assert open_after_stop, 'stop_nodes closed a remote link'
    assert remote.closed, 'the link to k was not closed'
    assert not remote.cancelled, 'the link to k was cancelled'
    assert pipe._status == PipelineStatus.STOPPED, f'got {pipe._status}'


def test_abort_stop_without_a_stop_does_nothing(tmp_path):
    pipe = Pipeline(_chain(tmp_path, [('s', 'main'), ('k', 'main')]))
    pipe.warmup()
    pipe.start()

    try:
        pipe.abort_stop()
        status, busy = pipe._status, pipe._transitioning

        assert pipe.begin_stop()
        pipe.abort_stop()
        aborted = pipe._status, pipe._transitioning
    finally:
        pipe.kill()

    assert (status, busy) == (PipelineStatus.RUNNING, False)
    assert aborted == (PipelineStatus.RUNNING, False), f'got {aborted}'


def test_kill_cancels_the_remote_links(tmp_path):
    transport = RemoteTransport()
    pipe = Pipeline(_chain(tmp_path, [('s', 'main'), ('k', 'x')]))
    pipe._transport = transport
    pipe.warmup()
    pipe.start()

    pipe.kill()

    assert transport.destinations['k'].cancelled, 'kill did not cancel k'


def test_destroy_cancels_the_remote_links(tmp_path):
    transport = RemoteTransport()
    pipe = Pipeline(_chain(tmp_path, [('s', 'main'), ('k', 'x')]))
    pipe._transport = transport
    pipe.warmup()

    pipe.destroy()

    assert transport.destinations['k'].cancelled, 'destroy did not cancel k'
