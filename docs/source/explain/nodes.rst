.. _explain_nodes:

Nodes
=====

A node is an independent, message-driven unit of a pipeline.

A simple message processor
--------------------------

A node is a typed message transformer: a ``Node[T_Input, T_Output]`` receives
messages with payloads of type ``T_Input`` and transmits messages with
payloads of type ``T_Output``. Whether it generates data, enriches it or
writes it to disk, it has this same shape. A node that mixes inputs of
different types, such as audio and video, receives them one at a time and
tells them apart by their creator (see `Multiple inputs`_).

Sources, processing nodes and sinks (:doc:`entities_overview`) are the same
class: they differ only in how they get their input. Nothing in a node class
or in its configuration says which role it plays: a node is a source if it
sets a source function, and a sink if it transmits nothing.

In a pipeline configuration, a node is its name, the class that implements it,
and the arguments for that class:

.. code-block:: json

  {
    "name": "my_awesome_node",
    "type": "contrib.acme.nodes.MyAwesomeNode",
    "configuration": { }
  }

Threading model
---------------

Every node runs up to two threads, each with one job.

.. container:: jt-figure

   .. raw:: html
      :file: ../diagrams/node.svg

   **Figure 1.** Inside a node. ``put()`` fills the inbound queue, ``_worker()`` hands one message at a time to ``update()``, which keeps what it needs in the state. Only source nodes run ``_source()`` (dashed).

The ``_worker`` thread runs in every node. It waits on the inbound queue and,
for each message, records it in the telemetry and calls ``update()`` with it.
``update()`` is the only place for the logic of the node, so that Juturna
keeps control of threads, errors and lifecycle.

.. admonition:: The inbound queue
   :class: :NOTE:

   Nodes use FIFO (First-In, First-Out) queues. This ensures messages are
   processed in the order they are produced, even when a source node generates
   data faster than its descendants can consume it. While ``update()`` is busy,
   new messages wait in the inbound queue. The queue holds
   ``JUTURNA_MAX_QUEUE_SIZE`` messages, 999 by default
   (:doc:`/reference/constants`), or ``queue_capacity`` in the browser
   (:doc:`transports`). Once it is full, ``transmit()`` in the upstream node
   waits until there is room again, so a slow node slows down the nodes that
   feed it; while the nodes run, no message is dropped. A policy that drops
   the oldest messages instead is an open feature request
   (`issue #268 <https://github.com/meetecho/juturna/issues/268>`_).

In source nodes, the ``_source`` thread runs next to the worker: it calls the
source function (``_source_f``) again and again and puts the messages it
returns in the node's own queue. In *pre* mode the node waits before each
call, to limit the rate; in *post* mode, the default, it waits after the
call, before queueing the message (or before the next call, when the
function returned ``None``).

The threads of all the nodes share one Python interpreter: CPU-bound Python
code in ``update()`` takes turns with the other nodes under the GIL, while
heavy models, which run in native libraries, release it while they compute.
The test suite also runs on free-threaded Python (3.14t) in CI.

Multiple inputs
---------------

A node with several upstream nodes receives their messages one at a time, in
the order they reach its inbound queue. ``message.creator`` tells which node
sent each of them. When a node needs messages from more upstream nodes before
producing an output (matching keys across streams, aggregating windows of data,
enforcing timeouts), it keeps the pending ones in its state, available in
``update()`` as ``kwargs['state']``, and removes them once they are used:

.. code-block:: python

   def update(self, message: Message, **kwargs):
       pending = kwargs['state'].setdefault('pending', {'audio': [], 'video': []})
       pending[message.creator].append(message)

       if not (pending['audio'] and pending['video']):
           return

       audio = pending['audio'].pop(0)
       video = pending['video'].pop(0)

       ...

The state is kept by the pipeline for the whole life of the node, across
``stop()`` and ``start()``, and ``kill()`` does not clear it. A node is
responsible for discarding the messages it no longer needs, so that its state
does not grow forever.

Only messages travel
--------------------

A node accepts ``Message`` objects only. Anything else is refused, wherever it
comes from: returned by the source function, passed to ``put()`` or to
``transmit()``, or found in the inbound queue. A refused item is logged as an
error and counted in the ``health`` of the node under ``rejected_items``; it
never reaches ``update()``, and the node goes on with the next message. A
source function with nothing to deliver returns ``None``, which is not counted.

``transmit()`` offers the message to every destination. When a destination
fails, the others still receive it, then the first error is raised.

Node lifecycle
--------------

The pipeline takes each node through:

.. code-block::

   configure() → warmup() → start() → stop() → destroy()

The ``status`` property (a ``ComponentStatus``) tells where the node is.

``configure()`` and ``warmup()`` prepare the node: the first is called right
after the node is built, the second once all the nodes of the pipeline exist
and are linked. Use ``configure()`` for what depends on the outside world
(ports, connections), and ``warmup()`` for the internal state (loading a
model).

``stop()`` stops the source thread first, then lets the worker thread finish
the messages left in the queue. ``kill()``, used by the pipeline when it is
killed, discards them instead.

When things go wrong
--------------------

An exception raised by ``update()`` or by the source function does not stop
the node: it is logged, counted in the ``health`` of the node, and the node
moves on to the next message. A source function that keeps failing is called
less and less often, up to ``JUTURNA_SOURCE_MAX_BACKOFF`` seconds apart, until
it works again.
