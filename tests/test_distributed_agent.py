import threading

import pytest

pytest.importorskip('grpc')

from juturna.distributed import WorkerAgent  # noqa: E402
from juturna.distributed import WorkerRegistry  # noqa: E402

TOKEN = 'agent-token'


@pytest.fixture
def worker(tmp_path):
    registry = WorkerRegistry(TOKEN)
    address = registry.start('127.0.0.1:0')
    agent = WorkerAgent(
        address,
        'w1',
        '127.0.0.1:0',
        folder=str(tmp_path / 'worker'),
        max_streams=4,
        token=TOKEN,
    )
    agent.connect()
    thread = threading.Thread(target=agent.serve_forever, daemon=True)
    thread.start()

    yield agent, registry.get('w1')

    agent.close()
    registry.stop(0)
    thread.join(5)


def _config(tmp_path, node_type='contrib.jt_test.nodes.DataStreamer'):
    return {
        'version': '0.1.0',
        'pipeline': {
            'name': 'dist',
            'id': 'p1',
            'folder': str(tmp_path / 'host' / 'dist_p1'),
            'transport': {
                'name': 'grpc',
                'worker': 'w1',
                'pipe_id': 'p1',
                'peers': {'k': '127.0.0.1:1'},
            },
            'nodes': [
                {
                    'name': 's',
                    'type': node_type,
                    'configuration': {'rate': 20},
                    'worker': 'w1',
                },
                {
                    'name': 'k',
                    'type': 'contrib.jt_test.nodes.Dumper',
                    'configuration': {},
                    'worker': 'other',
                },
            ],
            'links': [{'from': 's', 'to': 'k'}],
        },
    }


def _warmup(remote, config, environ=None):
    return remote.call(
        'warmup', {'config': config, 'environ': environ or {}}, timeout=30
    )


def test_warmup_builds_only_own_nodes(worker, tmp_path):
    agent, remote = worker
    _warmup(remote, _config(tmp_path))

    status = remote.call('status', {'pipe_id': 'p1'}, timeout=30)

    assert list(status['nodes']) == ['s'], f'got {list(status["nodes"])}'
    assert status['self'] == 'pipeline_ready'
    assert status['folder'] == str(tmp_path / 'worker' / 'dist_p1')
    assert 'p1' in agent._data._pipes

    with pytest.raises(RuntimeError, match='p1'):
        _warmup(remote, _config(tmp_path))

    remote.call('destroy', {'pipe_id': 'p1'}, timeout=30)
    assert 'p1' not in agent._data._pipes


def test_failed_warmup_can_be_retried(worker, tmp_path):
    agent, remote = worker

    with pytest.raises(RuntimeError):
        _warmup(remote, _config(tmp_path, 'contrib.jt_test.nodes.Nope'))

    assert 'p1' not in agent._pipelines
    assert 'p1' not in agent._data._pipes

    _warmup(remote, _config(tmp_path))
    remote.call('destroy', {'pipe_id': 'p1'}, timeout=30)


def test_lifecycle_and_unknown_pipe(worker, tmp_path):
    _, remote = worker
    _warmup(remote, _config(tmp_path))

    remote.call('start', {'pipe_id': 'p1'}, timeout=30)
    assert remote.call('begin_stop', {'pipe_id': 'p1'}, timeout=30) == {
        'began': True
    }
    remote.call('close_remote', {'pipe_id': 'p1', 'nodes': []}, timeout=30)
    remote.call('stop_nodes', {'pipe_id': 'p1', 'nodes': ['s']}, timeout=30)
    remote.call('end_stop', {'pipe_id': 'p1'}, timeout=30)

    status = remote.call('status', {'pipe_id': 'p1'}, timeout=30)
    assert status['self'] == 'pipeline_stopped'

    remote.call('destroy', {'pipe_id': 'p1'}, timeout=30)

    with pytest.raises(RuntimeError, match='p1'):
        remote.call('status', {'pipe_id': 'p1'}, timeout=30)


def test_kill_after_start(worker, tmp_path):
    _, remote = worker
    _warmup(remote, _config(tmp_path))
    remote.call('start', {'pipe_id': 'p1'}, timeout=30)
    remote.call('kill', {'pipe_id': 'p1'}, timeout=30)
    remote.call('destroy', {'pipe_id': 'p1'}, timeout=30)


def test_destroy_forgets_id_when_node_fails(worker, tmp_path, monkeypatch):
    agent, remote = worker
    _warmup(remote, _config(tmp_path))
    node = agent._pipelines['p1']._nodes['s']

    def boom():
        raise RuntimeError('node destroy failed')

    monkeypatch.setattr(node, 'destroy', boom)

    with pytest.raises(RuntimeError, match='node destroy failed'):
        remote.call('destroy', {'pipe_id': 'p1'}, timeout=30)

    assert 'p1' not in agent._pipelines
    assert 'p1' not in agent._data._pipes


def test_environ_reaches_node(worker, tmp_path):
    agent, remote = worker
    config = _config(tmp_path, 'contrib.jt_test.nodes.PassthroughIdentity')
    config['pipeline']['nodes'][0]['configuration'] = {
        'delay': '$JT_ENV_AGENT_DELAY'
    }
    _warmup(remote, config, {'AGENT_DELAY': '7'})

    delay = agent._pipelines['p1']._nodes['s']._delay

    assert delay == 7, f'got {delay!r}'
    remote.call('destroy', {'pipe_id': 'p1'}, timeout=30)
