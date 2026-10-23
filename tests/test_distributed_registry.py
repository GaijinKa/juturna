import enum
import threading

import pytest

pytest.importorskip('grpc')

from juturna.components import Pipeline  # noqa: E402
from juturna.distributed import PROTOCOL_VERSION  # noqa: E402
from juturna.distributed import WorkerAgent  # noqa: E402
from juturna.distributed import WorkerRegistry  # noqa: E402
from juturna.names import PipelineStatus  # noqa: E402

TOKEN = 'registry-token'


@pytest.fixture
def cluster():
    """A registry on a free port, and a factory of agents; all closed after."""
    registry = WorkerRegistry(TOKEN)
    address = registry.start('127.0.0.1:0')
    agents = list()
    threads = list()

    def agent(name, token=TOKEN, serve=True, **kwargs):
        new = WorkerAgent(
            address,
            name,
            '127.0.0.1:0',
            folder='/tmp',
            max_streams=4,
            token=token,
            **kwargs,
        )
        agents.append(new)
        new.connect()

        if serve:
            thread = threading.Thread(target=new.serve_forever, daemon=True)
            thread.start()
            threads.append(thread)
            new.thread = thread

        return new

    yield registry, agent

    for each in agents:
        each.close()

    registry.stop(0)

    for thread in threads:
        thread.join(5)


def test_call_echo_keeps_ints(cluster):
    registry, agent = cluster
    worker = agent('w1')
    worker.handlers['echo'] = lambda args: args

    remote = registry.get('w1')
    answer = remote.call('echo', {'rate': 20}, timeout=10)

    assert answer == {'rate': 20}, f'got {answer}'
    assert type(answer['rate']) is int, f'got {type(answer["rate"])}'
    assert remote.data_address == worker.data_address


def test_unknown_command_and_handler_error(cluster):
    registry, agent = cluster
    worker = agent('w1')

    def fail(args):
        raise ValueError('boom')

    worker.handlers['fail'] = fail
    remote = registry.get('w1')

    with pytest.raises(RuntimeError, match='unknown command nope'):
        remote.call('nope', {}, timeout=10)

    with pytest.raises(RuntimeError, match='boom'):
        remote.call('fail', {}, timeout=10)


@pytest.mark.parametrize(
    'name, token, protocol',
    [
        ('w1', 'wrong', PROTOCOL_VERSION),
        ('w1', TOKEN, PROTOCOL_VERSION + 1),
        ('main', TOKEN, PROTOCOL_VERSION),
    ],
)
def test_registration_refused(cluster, name, token, protocol, monkeypatch):
    registry, agent = cluster
    monkeypatch.setattr(
        'juturna.distributed._agent.PROTOCOL_VERSION', protocol
    )

    with pytest.raises(PermissionError):
        agent(name, token=token, serve=False)

    assert registry.get(name) is None


def test_duplicate_name_refused_while_alive(cluster, wait_for_condition):
    registry, agent = cluster
    first = agent('w1')

    with pytest.raises(PermissionError, match='already registered'):
        agent('w1', serve=False)

    first.close()
    gone = wait_for_condition(lambda: not registry.get('w1').alive, 20)
    assert gone, 'the first worker is still alive after close()'

    second = agent('w1')
    second.handlers['echo'] = lambda args: args

    assert registry.get('w1').call('echo', {'a': 1}, timeout=10) == {'a': 1}


def test_lost_channel_fails_pending_call(cluster, wait_for_condition):
    registry, agent = cluster
    worker = agent('w1')
    release = threading.Event()
    worker.handlers['block'] = lambda args: release.wait(30) and {}

    remote = registry.get('w1')
    outcome = dict()

    def call():
        try:
            outcome['answer'] = remote.call('block', {})
        except Exception as exc:
            outcome['error'] = exc

    caller = threading.Thread(target=call, daemon=True)
    caller.start()

    try:
        worker._channel.close()

        assert wait_for_condition(lambda: not remote.alive, 20), 'still alive'
        caller.join(20)
    finally:
        release.set()

    assert isinstance(outcome.get('error'), ConnectionError), f'{outcome}'

    with pytest.raises(ConnectionError):
        remote.call('block', {}, timeout=5)


def _config(tmp_path, pipe_id):
    return {
        'pipeline': {
            'name': pipe_id,
            'id': pipe_id,
            'folder': str(tmp_path / pipe_id),
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
                },
            ],
            'links': [{'from': 's', 'to': 'k'}],
        },
    }


def test_host_lost_destroys_the_pipelines(cluster, tmp_path):
    registry, agent = cluster
    worker = agent('w1')

    ready = Pipeline(_config(tmp_path, 'ready'))
    ready.warmup()

    stopping = Pipeline(_config(tmp_path, 'stopping'))
    stopping.warmup()
    stopping.start()
    assert stopping.begin_stop()

    pipelines = [ready, stopping]

    try:
        for pipe in pipelines:
            worker._pipelines[pipe.pipe_id] = pipe
            worker._data.register(pipe.pipe_id, dict(pipe._nodes))

        registry.stop(0)
        worker.thread.join(20)
    finally:
        for pipe in pipelines:
            if pipe.status['self'] == PipelineStatus.RUNNING:
                pipe.abort_stop()
                pipe.kill()

    assert not worker.thread.is_alive(), 'serve_forever did not return'
    assert worker._pipelines == {}, f'ids left: {list(worker._pipelines)}'
    assert worker._data._pipes == {}, f'served: {list(worker._data._pipes)}'

    for pipe in pipelines:
        assert pipe._nodes is None, f'{pipe.pipe_id} kept its nodes'
        assert pipe.status['self'] == PipelineStatus.DESTROYED, (
            f'{pipe.pipe_id} is {pipe.status["self"]}'
        )


@pytest.mark.parametrize(
    'result', [{'s': {1, 2}}, {'k': enum.Enum('Colour', 'RED').RED}, [1, 2]]
)
def test_unencodable_answer_is_an_error(cluster, result):
    registry, agent = cluster
    worker = agent('w1')
    worker.handlers['bad'] = lambda args: result

    with pytest.raises(RuntimeError):
        registry.get('w1').call('bad', {}, timeout=10)


def test_keep_refused_after_host_lost(cluster, tmp_path):
    _, agent = cluster
    worker = agent('w1', serve=False)

    pipe = Pipeline(_config(tmp_path, 'late'))
    worker.on_host_lost()
    kept = worker._keep(pipe.pipe_id, pipe)

    assert not kept, 'a pipeline was kept after the host was lost'
    assert worker._pipelines == {}, f'kept: {list(worker._pipelines)}'


def test_unregister_failure_does_not_stop_cleanup(cluster, tmp_path):
    _, agent = cluster
    worker = agent('w1', serve=False)
    pipelines = [Pipeline(_config(tmp_path, f'p{i}')) for i in range(2)]

    for pipe in pipelines:
        pipe.warmup()
        assert worker._keep(pipe.pipe_id, pipe)

    def broken(pipe_id):
        raise RuntimeError('unregister failed')

    worker._data.unregister = broken
    worker.on_host_lost()

    for pipe in pipelines:
        assert pipe.status['self'] == PipelineStatus.DESTROYED, (
            f'{pipe.pipe_id} is {pipe.status["self"]}'
        )
