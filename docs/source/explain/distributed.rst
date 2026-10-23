.. _explain_distributed:

Distributed pipelines
=====================

A single pipeline, described by a single configuration, can run its nodes in
several juturna processes. Each heavy node runs on the machine that has its
model and the right hardware (one machine with Whisper, one with YOLO, one with
a review LLM), while the pipeline is still created, started, stopped and
deleted through the HTTP API of ``juturna serve``.

The same mechanism lets a pipeline with **several heavy nodes written in pure
Python** put each of them in its own process on one machine, so they no longer
share a GIL. It does not help nodes that work in torch, onnx or numpy, which
already release the GIL and run in parallel on threads, nor a single
saturated node: that needs several copies of the same node, which distributed
pipelines do not offer.

Every hop between processes has a cost (serialization, network). Distribute a
pipeline because a node needs another machine or another process, not by
default.

.. admonition:: Distributed pipelines need the ``warp`` extra
    :class: :WARNING:

    Both ``juturna serve --workers`` and ``juturna worker`` need juturna
    installed with the ``warp`` dependency group (gRPC). A pipeline without
    workers does not import gRPC.

Terms
-----

worker
    A juturna process that runs part of a pipeline, identified by a name. Not
    to be confused with the ``_worker`` thread of a node.

host
    The worker called ``main``: the ``juturna serve`` process that receives
    pipelines from the HTTP API, accepts the registration of the other
    workers and coordinates the pipeline lifecycle. Not to be confused with
    the ``--host`` option of ``serve``, the address the HTTP API listens on.

remote link
    A link of the configuration whose two nodes run on different workers.

Placing nodes on workers
------------------------

A node declares the worker it runs on with its ``worker`` key; a node without
it runs on ``main``, the host. Nothing else in the configuration changes:

.. code-block:: json

    {
      "version": "1.0.0",
      "pipeline": {
        "name": "transcribe",
        "id": "transcribe",
        "folder": "./running",
        "nodes": [
          {"name": "src", "type": "AudioRtp", "configuration": {}},
          {"name": "asr", "type": "extensions.nodes.Whisper",
           "configuration": {}, "worker": "whisper"},
          {"name": "out", "type": "NotifierHTTP", "configuration": {}}
        ],
        "links": [
          {"from": "src", "to": "asr"},
          {"from": "asr", "to": "out"}
        ]
      }
    }

Each worker builds only its own nodes. The node code, its dependencies and its
hardware must already be installed on the worker: nothing is copied there.

``juturna launch`` refuses a configuration that uses workers other than
``main``; such a pipeline only runs through ``juturna serve --workers``.

Starting the host and the workers
---------------------------------

The host is ``juturna serve`` with ``--workers``, the address the workers
register on, and ``--data-address``, the address the other processes send the
messages for the host's nodes to:

.. code-block:: console

    host$     export JUTURNA_SERVICE_TOKEN=...
    host$     juturna serve -H 10.0.0.1 -p 8080 -f /data/jt \
                  --workers 10.0.0.1:5678 --data-address 10.0.0.1:5679

    whisper$  export JUTURNA_SERVICE_TOKEN=...
    whisper$  juturna worker 10.0.0.1:5678 --name whisper --folder /data/jt \
                  --data-address 10.0.0.2:5679

    yolo$     export JUTURNA_SERVICE_TOKEN=...
    yolo$     juturna worker 10.0.0.1:5678 --name yolo --folder /data/jt \
                  --data-address 10.0.0.3:5679

- A worker registers with its name, its data address, the protocol version
  and the service token of the host (``JUTURNA_SERVICE_TOKEN``, the same token
  as the HTTP API). The host refuses a wrong token, another protocol version,
  and the name ``main``.
- A name already registered is refused while its previous registration is
  alive. A worker restarted right after a crash may be refused for a few
  seconds, until the host notices the old one is gone; ``juturna worker``
  retries for 30 seconds before giving up.
- The control channel the worker opens at registration stays open: it carries
  the lifecycle commands and tells the host whether the worker is alive.
- A worker outlives the pipelines: two pipelines on the same worker get
  separate nodes. Their folders, telemetry and node files live under the
  worker's ``--folder``, not under the host's.
- When a worker loses the host, it kills and destroys its pipelines and exits
  with a non-zero code. It does not register again by itself.

Data addresses
--------------

Messages on a remote link travel on a gRPC stream **directly** between the
two workers: a message from a node on ``whisper`` to a node on ``yolo`` does
not go through the host. Every process therefore needs a data address that
every other process of the pipeline can reach.

``--data-address HOST:PORT`` is bound on ``HOST`` and advertised as given.
``0.0.0.0`` and ``::`` are refused, because the other processes cannot dial
them: give the address of an interface they can reach. Port ``0`` picks any
free port and advertises the bound one.

A process serves at most ``--max-streams`` incoming streams at once (16 by
default), one per pair of sending worker and destination node. A pipeline
that would need more is refused at warmup.

Messages that a worker does not drain block the nodes that write to it, as a
full queue does between local nodes. There is no write timeout: a live but
stuck worker blocks its writers for as long as it stays connected.

Lifecycle
---------

The host holds the whole configuration and computes the whole graph, remote
links included.

warmup
    The host refuses cycles that cross workers and pipelines whose workers are
    not registered, or have no stream left. It sends the configuration to every
    worker involved, and each one warms up its own nodes. If one fails, the
    workers already warmed up destroy the pipeline and it stays ``NEW``.

start
    Every worker starts its nodes. If one fails, the workers already started
    roll back and the pipeline stays ``READY``, so the start can be retried.

stop
    Stopping is lossless. The host walks the layers of the whole graph and,
    for each layer, asks every worker to close its streams towards the nodes
    of that layer, wait until the receiver has queued everything, and then
    stop its own nodes of that layer. A message in flight between processes
    is delivered before its receiver stops. ``delete`` on a running pipeline
    stops it the same way.

status
    The status of the pipeline on the host lists its workers as ``alive`` or
    ``lost``, and the status of the host's own nodes. It never waits on a
    worker.

Environment variables in node configurations (``$JT_ENV_NAME``) are resolved
with the values of the host and its ``--allow-env`` list: the host sends the
values of the allowed variables the configuration references, and the workers
use them instead of their own environment.

Strict serialization
--------------------

Moving a node to another worker does not change the data it receives, for the
messages that the protobuf format can carry. A message that cannot travel (a
payload type the protobuf mapping does not know, a meta value that cannot be
converted, a message over 100 MB) is dropped whole, with one warning per link,
and never arrives cut down. The sending node gets no exception, and its local
destinations still receive the message.

A received message is frozen, as local messages are, so a node that changes
its input behaves the same wherever it runs.

Failures
--------

- A worker that is not registered at warmup: the pipeline does not start.
- A worker that dies (lost connection, detected by the gRPC keepalive on the
  data and control channels): one warning per broken link, the messages for it
  are dropped, the nodes writing to it are released, and the rest of the
  pipeline keeps running. ``stop`` and ``delete`` skip it and return.
- "Lost" means disconnected, not slow.

Limits of this version
----------------------

- **Trusted network.** There is no TLS: the service token and the data travel
  in cleartext between the processes. Run them on a network you trust, or
  inside a tunnel. With ``serve --no-auth`` the host accepts any worker.
- **No recovery.** A worker that dies is not attached again, even when it
  comes back: its branch stays stopped until the pipeline is created again.
- **No sharding.** Several copies of the same node sharing the messages are
  not supported.
- **No code transfer.** Workers must already have the nodes, their
  dependencies and their hardware.
- **No shared nodes.** A node is never shared between pipelines; use
  :ref:`warp <explain_remote>` for that.
- **No discovery.** A worker is given the host address when it starts.
- **No real-time drop.** Messages are not discarded to keep up.
- **Message ids and clocks.** Message ids are unique only inside a process,
  and timestamps of different machines are not comparable: this only affects
  telemetry.
- **Status.** The host does not report the detailed status of remote nodes.
