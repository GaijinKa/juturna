import argparse
import json
import logging
import os
import pathlib
import signal
import subprocess
import sys
import threading

import pytest

from tests.conftest import SERVICE_TOKEN

REPO = pathlib.Path(__file__).parent.parent
WORKER_ENV = {
    **os.environ,
    'JUTURNA_SERVICE_TOKEN': SERVICE_TOKEN,
    'PYTHONPATH': os.pathsep.join(
        filter(None, ['tests/_nodes', os.environ.get('PYTHONPATH')])
    ),
}


def _node(name, node_type, worker, **configuration):
    return {
        'name': name,
        'type': f'contrib.jt_test.nodes.{node_type}',
        'configuration': configuration,
        'worker': worker,
    }


def _config(nodes, links):
    return {
        'version': '0.1.0',
        'pipeline': {
            'name': 'dist',
            'id': 'ignored',
            'folder': 'ignored',
            'nodes': nodes,
            'links': [{'from': a, 'to': b} for a, b in links],
        },
    }


def _chain():
    return _config(
        [
            _node('s', 'DataStreamer', 'main', rate=20),
            _node('a', 'PassthroughIdentity', 'x', delay=0.05),
            _node('b', 'PassthroughIdentity', 'y', delay=0.05),
            _node('k', 'Dumper', 'main'),
        ],
        [('s', 'a'), ('a', 'b'), ('b', 'k')],
    )


def _branches():
    return _config(
        [
            _node('s', 'DataStreamer', 'main', rate=20),
            _node('a', 'PassthroughIdentity', 'x', delay=0.05),
            _node('b', 'PassthroughIdentity', 'y', delay=0.05),
            _node('k1', 'Dumper', 'main'),
            _node('k2', 'Dumper', 'main'),
        ],
        [('s', 'a'), ('s', 'b'), ('a', 'k1'), ('b', 'k2')],
    )


def _sent_count(folder):
    # DataStreamer dumps message_<version>.json after transmitting each one
    return len(list(pathlib.Path(folder, 's').glob('message_*.json')))


def _pipeline(pipeline_id):
    from juturna.cli.commands._pipeline_manager import PipelineManager

    return PipelineManager()._get(pipeline_id)


def _post_within(client, path, timeout=30):
    responses = []
    thread = threading.Thread(
        target=lambda: responses.append(client.post(path)), daemon=True
    )
    thread.start()
    thread.join(timeout)

    assert not thread.is_alive(), f'{path} blocked'

    return responses[0]


@pytest.fixture
def cluster(tmp_path, service_app):
    """Distribution on the service: registry, host data server, workers."""
    pytest.importorskip('grpc')

    from juturna.cli.commands._pipeline_manager import PipelineManager
    from juturna.distributed import WorkerAgent
    from juturna.distributed import WorkerRegistry
    from juturna.transport.grpc import DataServer

    registry = WorkerRegistry(SERVICE_TOKEN)
    address = registry.start('127.0.0.1:0')
    host = DataServer('127.0.0.1:0', max_streams=16)
    host.start()
    PipelineManager.set_distribution(registry, host)
    agents, threads, procs = [], [], []

    class Cluster:
        def __init__(self):
            self.registry = registry
            self.address = address
            self.tmp_path = tmp_path

        def agent(self, name):
            agent = WorkerAgent(
                address,
                name,
                '127.0.0.1:0',
                folder=str(tmp_path / name),
                token=SERVICE_TOKEN,
            )
            agent.connect()
            agents.append(agent)
            thread = threading.Thread(target=agent.serve_forever, daemon=True)
            thread.start()
            threads.append(thread)

            return agent

        def process(self, name, token=SERVICE_TOKEN):
            log = open(tmp_path / f'{name}.log', 'w')  # noqa: SIM115
            proc = subprocess.Popen(
                [
                    sys.executable,
                    '-m',
                    'juturna',
                    'worker',
                    address,
                    '--name',
                    name,
                    '--folder',
                    str(tmp_path / name),
                    '--data-address',
                    '127.0.0.1:0',
                ],
                cwd=REPO,
                env={**WORKER_ENV, 'JUTURNA_SERVICE_TOKEN': token},
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            procs.append((proc, log))

            return proc

    yield Cluster()

    PipelineManager().cleanup()

    for agent in agents:
        agent.close()

    for proc, log in procs:
        proc.kill()
        proc.wait(10)
        log.close()

    host.stop(0)
    registry.stop(0)
    PipelineManager.set_distribution(None, None)

    for thread in threads:
        thread.join(5)


def test_service_runs_a_distributed_pipeline(
    cluster, service_client, wait_for_condition
):
    cluster.agent('x')
    cluster.agent('y')

    created = service_client.post('/pipelines/new', json=_chain())
    assert created.status_code == 200, created.text
    pipeline_id = created.json()['data']['pipeline_id']

    for step in ('warmup', 'start'):
        response = service_client.post(f'/pipelines/{pipeline_id}/{step}')
        assert response.status_code == 200, response.text

    pipe = _pipeline(pipeline_id)
    sink = pipe._local._nodes['k']
    started = wait_for_condition(lambda: len(sink.versions) >= 3, timeout=20)
    assert started, f'Expected 3 messages at k, got {sink.versions}'

    response = service_client.post(f'/pipelines/{pipeline_id}/stop')
    assert response.status_code == 200, response.text
    assert response.json()['workers'] == {'x': 'alive', 'y': 'alive'}

    sent = _sent_count(pipe.pipe_path)
    assert sink.versions == list(range(sent)), sink.versions

    response = service_client.post(f'/pipelines/{pipeline_id}/delete')
    assert response.status_code == 200, response.text
    assert service_client.get('/pipelines').json() == {'pipelines': [{}]}


def test_killed_worker_process_does_not_block_the_service(
    cluster, service_client, wait_for_condition, jt_records
):
    cluster.agent('x')
    proc = cluster.process('y')
    registered = wait_for_condition(
        lambda: (w := cluster.registry.get('y')) is not None and w.alive,
        timeout=30,
    )
    assert registered, f'worker y did not register, exit code {proc.poll()}'

    created = service_client.post('/pipelines/new', json=_branches())
    assert created.status_code == 200, created.text
    pipeline_id = created.json()['data']['pipeline_id']

    for step in ('warmup', 'start'):
        response = service_client.post(f'/pipelines/{pipeline_id}/{step}')
        assert response.status_code == 200, response.text

    pipe = _pipeline(pipeline_id)
    k1 = pipe._local._nodes['k1']
    k2 = pipe._local._nodes['k2']
    started = wait_for_condition(lambda: len(k2.versions) >= 2, timeout=20)
    assert started, f'Expected 2 messages at k2, got {k2.versions}'

    proc.kill()
    proc.wait(10)
    after_kill = len(k1.versions)
    grows = wait_for_condition(
        lambda: len(k1.versions) >= after_kill + 5, timeout=30
    )
    assert grows, f'k1 stuck at {len(k1.versions)} after the kill'

    stopped = _post_within(service_client, f'/pipelines/{pipeline_id}/stop')
    assert stopped.status_code == 200, stopped.text
    deleted = _post_within(service_client, f'/pipelines/{pipeline_id}/delete')
    assert deleted.status_code == 200, deleted.text

    lost = [
        r.getMessage()
        for r in jt_records
        if r.levelno == logging.WARNING
        and r.getMessage().startswith('link to')
        and 'lost' in r.getMessage()
    ]
    assert len(lost) == 1, lost
    assert lost[0].startswith('link to b '), lost


@pytest.mark.skipif(os.name != 'posix', reason='needs SIGSTOP')
def test_stopped_worker_process_is_lost_by_keepalive(
    cluster, service_client, wait_for_condition
):
    # a stopped process keeps its sockets open: only keepalive can tell
    cluster.agent('x')
    proc = cluster.process('y')
    registered = wait_for_condition(
        lambda: (w := cluster.registry.get('y')) is not None and w.alive,
        timeout=30,
    )
    assert registered, f'worker y did not register, exit code {proc.poll()}'

    try:
        created = service_client.post('/pipelines/new', json=_branches())
        assert created.status_code == 200, created.text
        pipeline_id = created.json()['data']['pipeline_id']

        for step in ('warmup', 'start'):
            response = service_client.post(f'/pipelines/{pipeline_id}/{step}')
            assert response.status_code == 200, response.text

        k2 = _pipeline(pipeline_id)._local._nodes['k2']
        started = wait_for_condition(lambda: len(k2.versions) >= 2, timeout=20)
        assert started, f'Expected 2 messages at k2, got {k2.versions}'

        os.kill(proc.pid, signal.SIGSTOP)

        stopped = _post_within(
            service_client, f'/pipelines/{pipeline_id}/stop', timeout=40
        )
        assert stopped.status_code == 200, stopped.text
        assert stopped.json()['workers'] == {'x': 'alive', 'y': 'lost'}
        assert not cluster.registry.get('y').alive

        deleted = _post_within(
            service_client, f'/pipelines/{pipeline_id}/delete', timeout=40
        )
        assert deleted.status_code == 200, deleted.text
    finally:
        os.kill(proc.pid, signal.SIGCONT)
        proc.kill()
        proc.wait(10)


def test_worker_with_a_wrong_token_exits(cluster):
    proc = cluster.process('z', token='wrong-token')

    assert proc.wait(30) != 0

    output = (cluster.tmp_path / 'z.log').read_text()
    assert 'invalid service token' in output, output


def _worker_args(cluster, name):
    return argparse.Namespace(
        host=cluster.address,
        name=name,
        data_address='127.0.0.1:0',
        folder=str(cluster.tmp_path / f'{name}-again'),
        max_streams=4,
    )


def test_worker_gives_up_on_a_live_name(cluster, monkeypatch):
    from juturna.cli.commands import worker

    monkeypatch.setenv('JUTURNA_SERVICE_TOKEN', SERVICE_TOKEN)
    monkeypatch.setattr(worker, '_RETRY_FOR', 1)
    monkeypatch.setattr(worker, '_RETRY_INTERVAL', 0.2)
    cluster.agent('w')

    with pytest.raises(PermissionError, match='already registered'):
        worker._connect(_worker_args(cluster, 'w'))


def test_worker_retries_until_the_name_is_free(cluster, monkeypatch):
    from juturna.cli.commands import worker

    monkeypatch.setenv('JUTURNA_SERVICE_TOKEN', SERVICE_TOKEN)
    monkeypatch.setattr(worker, '_RETRY_INTERVAL', 0.2)
    first = cluster.agent('w')
    threading.Timer(0.5, first.close).start()

    agent = worker._connect(_worker_args(cluster, 'w'))

    try:
        assert cluster.registry.get('w').alive
        assert cluster.registry.get('w').data_address == agent.data_address
    finally:
        agent.close()


def test_workers_need_serve_with_workers(service_client):
    response = service_client.post('/pipelines/new', json=_chain())

    assert response.status_code == 409, response.text
    assert response.json() == {
        'message': 'pipeline uses workers x, y, start serve with --workers'
    }


@pytest.mark.parametrize('worker', [None, 3, ['x'], ''])
def test_service_refuses_a_worker_that_is_not_a_name(service_client, worker):
    config = _chain()
    config['pipeline']['nodes'][1]['worker'] = worker
    response = service_client.post('/pipelines/new', json=config)

    assert response.status_code == 422, response.text
    assert 'node a needs a worker name' in response.text


def test_launch_refuses_workers(tmp_path, capsys):
    from juturna.cli.commands import launch

    pipeline = _chain()
    pipeline['pipeline']['folder'] = str(tmp_path / 'p')
    config = tmp_path / 'config.json'
    config.write_text(json.dumps(pipeline))
    args = argparse.Namespace(
        config=str(config),
        log_level='INFO',
        auto=True,
        timeout=0,
        dry_gin=True,
    )

    assert launch._execute(args) == 1
    assert (
        'pipeline uses workers x, y: run it with juturna serve --workers'
        in capsys.readouterr().err
    )


def test_serve_help_does_not_need_grpc():
    script = (
        'import runpy, sys\n'
        "sys.modules['grpc'] = None\n"
        "sys.argv = ['juturna', 'serve', '--help']\n"
        "runpy.run_module('juturna', run_name='__main__')\n"
    )
    result = subprocess.run(
        [sys.executable, '-c', script],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=REPO,
    )

    assert result.returncode == 0, result.stderr
    assert '--workers' in result.stdout, result.stdout
