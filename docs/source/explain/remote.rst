.. _explain_remote:

Remote components
=================

A pipeline builds all its nodes in the process that runs it. That is what
you want while you write and check nodes on your own machine, but in
production some nodes need resources the machine does not have, such as a
GPU. Juturna can run such a node on another machine and still use it as if it
were local: this is **warping**.

A warped node runs in a remote service, and the pipeline talks to it over the
network with gRPC and `Protocol Buffers
<https://github.com/protocolbuffers/protobuf>`_. The remote service manages
the lifecycle of the node and passes the messages of its input and output
queues.

Warping helps in several deployments. A remote node has its own
dependencies, so they cannot clash with those of the other nodes in the
pipeline. A remote service can also serve several pipelines at once, or run
as several replicas behind a load balancer.

.. admonition:: Remotisation is young
    :class: :WARNING:

    The infrastructure to run Juturna nodes remotely is still under active
    development. The remote service has no authentication and no encryption
    (see `Who can reach the service`_), so it is meant for trusted networks
    or a VPN only. TLS and client authentication are tracked in
    `issue #270 <https://github.com/meetecho/juturna/issues/270>`_.

Warping fundamentals
--------------------

When a node is configured for remote execution, two components work together. On
the local side (the main Juturna process) a node intended for remote
deployment is masked by a **warp node**. A warp node is a simple processing node
acting as local client or proxy for the remote node. Warp nodes are responsible
for managing the communication with the remote service behind which the concrete
node lives. This means, they receive messages from the pipeline normally, turn
them into protocol buffers, send them over the remote service, and then unpack
the responses they receive.

On the remote side runs the **remote service**, a standalone gRPC server that
holds the concrete node doing the actual computation work, acting as a
publish/subscribe broker for its input and output queues. Similarly to the warp
node, the remote service manages the marshalling and unmarshalling of the data
received from the local pipeline.

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

The remote service keeps the state of at most ``--max-clients`` sticky warp
nodes (1024 by default) and refuses new ones with the ``RESOURCE_EXHAUSTED``
status, until a state is dropped after an hour without requests. It accepts
``--max-requests`` requests at once (10 for each worker by default), in
progress or waiting for a worker, and refuses the others with the same
status. A request whose warp node cancels it or disconnects is not processed
if it is still waiting.

``python -m juturna remotize`` exits with status 1 when the node cannot be built or the
address is already in use: two services never share a port.

Developer notes
---------------

Juturna comes with pre-compiled protobuf classes, ready to use out of
the box. However, if you need to modify the .proto definitions or recompile them
for development purposes, two utility scripts are provided:

- ``juturna/remotizer/compile_protos.sh``: Recompiles the .proto files into
  Python classes
- ``juturna/remotizer/expose_protos.sh``: Exports the compiled protobuf classes
  for external use. This requires to install the additional ``protoletariat``
  dependency.

These scripts should only be needed when modifying the protocol definitions or
contributing to the warp node.
