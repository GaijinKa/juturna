"""
Run a Juturna worker

Register on a host (`juturna serve --workers HOST:PORT`) under a name, then
build and run the nodes of the pipelines the host places on that name. The
worker receives the messages for its nodes on `--data-address`, which every
other process of the pipeline must be able to reach.

The host's service token is read from the `JUTURNA_SERVICE_TOKEN` environment
variable. When the host is lost the worker drops its pipelines and exits: it
does not register again on its own.

Running a worker requires Juturna to be installed with the `warp` dependency
group.
"""

import os
import time

from juturna.distributed import WorkerAgent
from juturna.utils.log_utils import jt_logger

TOKEN_ENV_VAR = 'JUTURNA_SERVICE_TOKEN'

# the host notices a vanished previous instance by keepalive, ~15 s
_RETRY_INTERVAL = 2
_RETRY_FOR = 30

logger = jt_logger('worker')


def setup_parser(subparsers):  # noqa: D103
    parser = subparsers.add_parser(
        'worker',
        help='run nodes of the pipelines of a juturna serve host',
    )

    parser.add_argument(
        'host',
        metavar='HOST:PORT',
        help='worker address of the host (serve --workers)',
    )

    parser.add_argument(
        '--name',
        '-n',
        required=True,
        help='worker name, the value of the worker key of its nodes',
    )

    parser.add_argument(
        '--folder',
        '-f',
        required=True,
        help='base folder of the pipelines run by the worker',
    )

    parser.add_argument(
        '--data-address',
        '-D',
        required=True,
        metavar='HOST:PORT',
        help='address the other processes send messages for the nodes of '
        'the worker to (port 0: any free port)',
    )

    parser.add_argument(
        '--max-streams',
        type=int,
        default=16,
        help='incoming data streams served at once (default: 16)',
    )

    parser.add_argument(
        '--log-level',
        '-l',
        type=str,
        default='INFO',
        choices=['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='log level of the worker and its nodes (default: INFO)',
    )


def _connect(args) -> WorkerAgent:
    deadline = time.monotonic() + _RETRY_FOR

    while True:
        # a refused agent is closed for good, so every attempt needs a new one
        agent = WorkerAgent(
            args.host,
            args.name,
            args.data_address,
            args.folder,
            args.max_streams,
            os.environ.get(TOKEN_ENV_VAR),
        )

        try:
            agent.connect()

            return agent
        except PermissionError as exc:
            if (
                'already registered' not in str(exc)
                or time.monotonic() + _RETRY_INTERVAL > deadline
            ):
                raise

            logger.info(f'{exc}, retrying in {_RETRY_INTERVAL} s')
            time.sleep(_RETRY_INTERVAL)


def _execute(args) -> int:
    jt_logger().setLevel(args.log_level)

    try:
        agent = _connect(args)
    except (PermissionError, ConnectionError, ValueError) as exc:
        logger.error(f'cannot register on {args.host}: {exc}')

        return 1
    except KeyboardInterrupt:
        return 0

    logger.info(
        f'worker {args.name} registered on {args.host}, data address '
        f'{agent.data_address}'
    )

    try:
        agent.serve_forever()
    except KeyboardInterrupt:
        agent.close()

        return 0

    agent.close()
    logger.error(f'host {args.host} lost, exiting')

    return 1
