import logging
import pathlib
import threading

import pytest

pytest.importorskip('grpc')

from juturna.distributed import DistributedPipeline  # noqa: E402
from juturna.distributed import DistributionError  # noqa: E402
from juturna.distributed import WorkerAgent  # noqa: E402
from juturna.distributed import WorkerRegistry  # noqa: E402
from juturna.names import PipelineStatus  # noqa: E402
from juturna.transport.grpc import DataServer  # noqa: E402

TOKEN = 'pipeline-token'


def _node(name, node_type, worker, **configuration):
    return {
        'name': name,
        'type': f'contrib.jt_test.nodes.{node_type}',
        'configuration': configuration,
        'worker': worker,
    }


def _config(tmp_path, nodes, links, pipe_id='dist-1'):
    return {
        'version': '0.1.0',
        'pipeline': {
            'name': 'dist',
            'id': pipe_id,
            'folder': str(tmp_path / 'host' / f'dist_{pipe_id}'),
            'nodes': nodes,
            'links': [{'from': a, 'to': b} for a, b in links],
        },
    }


def _chain(tmp_path):
    return _config(
        tmp_path,
        [
            _node('s', 'DataStreamer', 'main', rate=20),
            _node('a', 'PassthroughIdentity', 'x', delay=0.05),
            _node('b', 'PassthroughIdentity', 'y', delay=0.05),
            _node('k', 'Dumper', 'main'),
        ],
        [('s', 'a'), ('a', 'b'), ('b', 'k')],
    )


def _sent_count(folder):
    # DataStreamer dumps message_<version>.json after transmitting each one
    return len(list(pathlib.Path(folder, 's').glob('message_*.json')))


@pytest.fixture
def cluster(tmp_path):
    """Registry, host data server, agents and pipelines; all closed after."""
    registry = WorkerRegistry(TOKEN)
    address = registry.start('127.0.0.1:0')
    host = DataServer('127.0.0.1:0', max_streams=16)
    host.start()
    agents, threads, pipes = dict(), list(), list()

    class Cluster:
        def __init__(self):
            self.registry = registry
            self.host = host
            self.agents = agents

        def agent(self, name, max_streams=8):
            agent = WorkerAgent(
                address,
                name,
                '127.0.0.1:0',
                folder=str(tmp_path / name),
                max_streams=max_streams,
                token=TOKEN,
            )
            agent.connect()
            agents[name] = agent
            thread = threading.Thread(target=agent.serve_forever, daemon=True)
            thread.start()
            threads.append(thread)

            return agent

        def pipeline(self, config):
            pipe = DistributedPipeline(config, registry, host, environ={})
            pipes.append(pipe)

            return pipe

    yield Cluster()

    for pipe in pipes:
        try:
            if pipe.status['self'] == PipelineStatus.RUNNING:
                pipe.kill()

            pipe.destroy()
        except Exception:
            logging.getLogger(__name__).exception('teardown failed')

    for agent in agents.values():
        agent.close()

    host.stop(0)
    registry.stop(0)

    for thread in threads:
        thread.join(5)


def test_distributed_passthrough_loses_nothing(
    tmp_path, wait_for_condition, cluster
):
    cluster.agent('x')
    cluster.agent('y')
    config = _chain(tmp_path)
    pipe = cluster.pipeline(config)

    pipe.warmup()
    pipe.start()
    sink = pipe._local._nodes['k']

    started = wait_for_condition(lambda: len(sink.versions) >= 3, timeout=20)
    assert started, f'Expected 3 messages at k, got {sink.versions}'

    pipe.stop()

    sent = _sent_count(config['pipeline']['folder'])
    assert sink.versions == list(range(sent)), sink.versions
    assert pipe.status['self'] == PipelineStatus.STOPPED
    assert pipe.status['workers'] == {'x': 'alive', 'y': 'alive'}
    assert set(pipe.status['nodes']) == {'s', 'k'}

    pipe.destroy()

    assert pipe.status['self'] == PipelineStatus.DESTROYED
    assert cluster.registry.get('x')._reserved == 0
    assert cluster.registry.get('y')._reserved == 0
    assert cluster.host._reserved == 0
    assert 'dist-1' not in cluster.host._pipes


def test_pipeline_with_no_local_nodes_starts_and_stops(
    tmp_path, wait_for_condition, cluster
):
    agent_x = cluster.agent('x')
    agent_y = cluster.agent('y')
    config = _config(
        tmp_path,
        [
            _node('s', 'DataStreamer', 'x', rate=20),
            _node('k', 'Dumper', 'y'),
        ],
        [('s', 'k')],
    )
    pipe = cluster.pipeline(config)

    pipe.warmup()
    pipe.start()
    sink = agent_y._pipelines['dist-1']._nodes['k']

    started = wait_for_condition(lambda: len(sink.versions) >= 3, timeout=20)
    assert started, f'Expected 3 messages at k, got {sink.versions}'

    pipe.stop()

    sent = _sent_count(agent_x._pipelines['dist-1'].pipe_path)
    assert sink.versions == list(range(sent)), sink.versions
    assert pipe.status['self'] == PipelineStatus.STOPPED
    assert pipe.status['nodes'] == {}
    assert pipe._telemetry is False
    assert pipe._telemetry_manager is None

    pipe.destroy()

    assert 'dist-1' not in agent_x._pipelines
    assert 'dist-1' not in agent_y._pipelines


def test_closed_worker_does_not_block_stop_or_the_other_branch(
    tmp_path, wait_for_condition, cluster, jt_records
):
    cluster.agent('x')
    agent_y = cluster.agent('y')
    config = _config(
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
    pipe = cluster.pipeline(config)
    pipe.warmup()
    pipe.start()
    k1 = pipe._local._nodes['k1']
    k2 = pipe._local._nodes['k2']

    started = wait_for_condition(lambda: len(k2.versions) >= 2, timeout=20)
    assert started, f'Expected 2 messages at k2, got {k2.versions}'

    agent_y.close()
    after_close = len(k1.versions)
    grows = wait_for_condition(
        lambda: len(k1.versions) >= after_close + 5, timeout=20
    )
    assert grows, f'k1 stuck at {len(k1.versions)} after the close'

    lost_seen = wait_for_condition(
        lambda: pipe.status['workers']['y'] == 'lost', timeout=20
    )
    assert lost_seen, pipe.status['workers']

    for step in (pipe.stop, pipe.destroy):
        thread = threading.Thread(target=step, daemon=True)
        thread.start()
        thread.join(timeout=30)
        assert not thread.is_alive(), f'{step.__name__} blocked'

    assert pipe.status['self'] == PipelineStatus.DESTROYED

    lost = [
        r.getMessage()
        for r in jt_records
        if r.levelno == logging.WARNING
        and r.getMessage().startswith('link to')
        and 'lost' in r.getMessage()
    ]
    print(lost)
    # the only link broken under a live sender is s -> b
    assert len(lost) == 1, lost
    assert lost[0].startswith('link to b '), lost


def test_unregistered_worker_fails_warmup(tmp_path, cluster):
    config = _chain(tmp_path)
    cluster.agent('x')
    pipe = cluster.pipeline(config)

    with pytest.raises(DistributionError, match='worker y is not registered'):
        pipe.warmup()

    assert pipe.status['self'] == PipelineStatus.NEW
    assert pipe.status['workers'] == {'x': 'alive', 'y': 'lost'}
    assert cluster.registry.get('x')._reserved == 0
    assert cluster.host._reserved == 0


def test_capacity_exceeded_fails_warmup(tmp_path, cluster):
    agent_x = cluster.agent('x', max_streams=1)
    config = _config(
        tmp_path,
        [
            _node('s', 'DataStreamer', 'main', rate=20),
            _node('a', 'Dumper', 'x'),
            _node('b', 'Dumper', 'x'),
        ],
        [('s', 'a'), ('s', 'b')],
    )
    pipe = cluster.pipeline(config)

    with pytest.raises(
        DistributionError, match='worker x cannot accept 2 more streams'
    ):
        pipe.warmup()

    assert pipe.status['self'] == PipelineStatus.NEW
    assert agent_x._pipelines == {}
    assert cluster.registry.get('x')._reserved == 0


def test_failed_worker_warmup_rolls_back_and_can_be_retried(
    tmp_path, cluster
):
    agent_x = cluster.agent('x')
    agent_y = cluster.agent('y')
    original = agent_y.handlers['warmup']

    def fail(args):
        raise ValueError('warmup refused')

    agent_y.handlers['warmup'] = fail
    pipe = cluster.pipeline(_chain(tmp_path))

    with pytest.raises(RuntimeError, match='warmup refused'):
        pipe.warmup()

    assert pipe.status['self'] == PipelineStatus.NEW
    assert 'dist-1' not in agent_x._pipelines
    assert cluster.registry.get('x')._reserved == 0
    assert cluster.registry.get('y')._reserved == 0
    assert cluster.host._reserved == 0
    assert 'dist-1' not in cluster.host._pipes

    agent_y.handlers['warmup'] = original
    pipe.warmup()

    assert pipe.status['self'] == PipelineStatus.READY
    assert 'dist-1' in agent_x._pipelines
    assert 'dist-1' in agent_y._pipelines
    assert 'dist-1' in cluster.host._pipes


def test_failed_start_leaves_pipeline_ready(tmp_path, cluster):
    agent_x = cluster.agent('x')
    agent_y = cluster.agent('y')
    original = agent_y.handlers['start']

    def fail(args):
        raise ValueError('start refused')

    agent_y.handlers['start'] = fail
    pipe = cluster.pipeline(_chain(tmp_path))
    pipe.warmup()

    with pytest.raises(RuntimeError, match='start refused'):
        pipe.start()

    assert pipe.status['self'] == PipelineStatus.READY
    x_status = agent_x._pipelines['dist-1'].status['self']
    assert x_status == PipelineStatus.READY, x_status

    agent_y.handlers['start'] = original
    pipe.start()

    assert pipe.status['self'] == PipelineStatus.RUNNING

    pipe.stop()


def test_concurrent_warmups_respect_capacity(tmp_path, cluster):
    cluster.agent('x', max_streams=1)
    pipes = [
        cluster.pipeline(
            _config(
                tmp_path,
                [
                    _node('s', 'DataStreamer', 'main', rate=20),
                    _node('k', 'Dumper', 'x'),
                ],
                [('s', 'k')],
                pipe_id=f'dist-{i}',
            )
        )
        for i in range(2)
    ]
    barrier = threading.Barrier(2)
    errors = list()

    def _warmup(pipe):
        barrier.wait(10)

        try:
            pipe.warmup()
        except DistributionError as exc:
            errors.append(exc)

    threads = [
        threading.Thread(target=_warmup, args=(p,), daemon=True) for p in pipes
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(30)

    assert not any(t.is_alive() for t in threads), 'a warmup is stuck'
    assert len(errors) == 1, errors
    assert 'worker x cannot accept 1 more streams' in str(errors[0])
    statuses = sorted(p.status['self'] for p in pipes)
    assert statuses == sorted([PipelineStatus.NEW, PipelineStatus.READY])
