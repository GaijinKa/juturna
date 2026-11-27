.. _explain_remote:

Remote components
=================

A pipeline builds all its nodes in the process that runs it. Some nodes need
resources that machine does not have, such as a GPU: Juturna can run such a
node on another machine and still use it as if it were local. This is
**warping**. A remote node also has its own dependencies, which cannot clash
with those of the other nodes, and a remote service can serve several
pipelines at once or run as replicas behind a load balancer.

.. warning::

    The remote service has no authentication and no encryption yet: use it on
    trusted networks only (see `Who can reach the service`_).

Warping fundamentals
--------------------

On the local side, the node is replaced by a **warp node**, a processing node
that acts as a client: it turns each message into `Protocol Buffers
<https://github.com/protocolbuffers/protobuf>`_, sends it over gRPC and
transmits the answer downstream. On the remote side, the **remote service**,
a standalone gRPC server, runs the concrete node and its lifecycle.

.. container:: jt-figure

   .. raw:: html
      :file: ../diagrams/remote_structure.svg

   **Figure 1.** A warped node. The warp node stands in the local pipeline and sends each message to the remote service, which runs the concrete node; with ``sticky`` the service keeps the node state.

State and replicas
------------------

The concrete node keeps its state between messages, like a local one. Each warp
node gets its own state on the remote side, even when one remote service serves
several pipelines, and the ``sticky`` flag of the warped node tells where that
state lives:

.. container:: jt-figure

   .. raw:: html
      :file: ../diagrams/warp_state.svg

   **Figure 2.** ``sticky`` (the default) keeps the state on one remote service; without it the state travels with every request, and any replica can answer.

A sticky service answers that it does not know a state after a restart, or
once it dropped an idle one: the warp node then sends its copy, and the
service starts again from it. Without ``sticky``, a replica going down loses
no state.

A sticky state is kept under the pipeline id, the name of the warp node and a
random **session** that the warp node makes at every warmup, so another client
gets a state of its own and a pipeline started again does not continue from
its previous run. A sticky warp node that is destroyed tells the service,
which drops its state at once.

In both cases the remote service answers when ``update()`` returns. A message
that the node keeps in its state without transmitting anything gets an empty
response at once, and the warp node transmits nothing downstream.

What cannot reach the client
----------------------------

Messages and states keep their exact types on the wire: ``None``, booleans,
ints, floats, strings, bytes, lists, tuples, frozensets, dictionaries, numpy
arrays and scalars, and messages. Some things still cannot reach the warp node:

- a value of another type (a set, an open file, a model) in the ``meta`` of a
  message, in an ``ObjectPayload`` or in the state, as well as an integer
  outside the 64-bit range and a string that is not valid Unicode;
- a second message transmitted by the same ``update()``: only the first one is
  sent back;
- a message transmitted after ``update()`` returned, or by a thread of the
  node other than the one running ``update()``: it never answers a request,
  since the request being processed at that moment may belong to another
  pipeline.

By default the remote service leaves them out and logs a warning, once for
each client and for each kind of loss: a dictionary loses the entry, a list or
a tuple the item, and everything else is sent. A state that loses an entry
loses it for good, in the copy kept by a sticky warp node as well, so keep
such objects in the node rather than in its state. The warp node does the same
with the messages it sends.

Started with ``--strict``, the remote service fails the request with the
``DATA_LOSS`` gRPC status instead, every time. A message transmitted late fails
the next request of its warp node, which is not processed. The warp node
counts the failure in its health, and the pipeline goes on with the next
message.

The remote service can only tell which warp node a late message was meant for
while the node is idle. A message transmitted by another thread while the node
processes a message is logged as an error instead, in both modes, and fails no
request. A node meant to run remotely transmits from ``update()`` only.

Who can reach the service
-------------------------

The remote service has **no authentication and no encryption**. Whoever can
connect to it can send messages to the node and read what comes back, and
whoever can read the traffic sees everything, sessions included. The session
keeps well-behaved clients apart; it is not a password.

For this reason ``python -m juturna remotize`` listens on ``127.0.0.1`` by default,
reachable from the same machine only. To serve pipelines on other machines,
pass the address to listen on with ``--host`` (``0.0.0.0`` for every
interface), and do it **on trusted networks only**: a private network between
your own machines, or behind a proxy or a tunnel that authenticates and
encrypts. The service logs a warning when it listens on anything but the
loopback address. TLS and client authentication are tracked in
`issue #270 <https://github.com/meetecho/juturna/issues/270>`_.

Protocol version
----------------

The warp node and the remote service must speak the same version of the remote
protocol, which is version 1 in Juturna 3.0. Every request and response carries
it. The service refuses a request of another version with the
``UNIMPLEMENTED`` status, and the warp node refuses a response of another
version, so two sides that do not match fail on the first message with an
error that says so. A message whose payload is of a type the receiver does not
know is refused too, on both sides.

The version changes whenever an older peer would not understand the new one.
Install matching versions of Juturna on both sides: on the local side that is
the version ``juturna-nodes`` was installed with.

Limits
------

Past ``--max-clients`` sticky states, or ``--max-requests`` requests at once
(defaults in :ref:`reference_cli`), the service refuses new ones with the
``RESOURCE_EXHAUSTED`` status. A sticky state is dropped after an hour
without requests. A request whose warp node cancels it or disconnects is not
processed if it is still waiting.

The protobuf classes come compiled with Juturna. To change the ``.proto``
definitions, recompile them with ``juturna/remotizer/compile_protos.sh``.
