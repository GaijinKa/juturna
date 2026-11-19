.. _transports:

Transports
==========

A pipeline runs on the threads of one Python process, or in Web Workers
inside a browser tab (:doc:`../how_to/choose_where_it_runs` lists the options
and how to pick one). The configuration format and the node model are the
same, but the nodes are not: a browser pipeline runs nodes written for
Pyodide, joined to the page by ``BrowserInput`` and ``BrowserOutput``, and a
server pipeline runs the nodes of ``juturna-nodes``. Nodes and the pipeline
never use ``threading`` or ``queue`` directly: they ask a **transport** for queues, events, locks and workers, and the transport
decides what those are.

.. container:: jt-figure

   .. raw:: html
      :file: ../diagrams/transport_layers.svg

   **Figure 1.** Nodes and the pipeline depend only on the transport
   protocols; the backend chosen in the configuration provides them.

The transport
-------------

``juturna/transport/_base.py`` defines the contract as protocols:
``Queue``, ``Event``, ``Lock``, ``Condition``, ``WorkerHandle`` and
``TransportBackend``, the factory of all the others. A node builds its
inbound queue with ``new_queue()``, its stop events with ``new_event()`` and
its workers with ``spawn()``; the pipeline uses ``node_scope()`` and
``remote_destination()`` while it links the nodes.

The ``transport`` key of the pipeline picks the backend, by name or as an
object with its options:

.. code-block:: json

    "transport": { "name": "browser", "max_payload_bytes": 4000000 }

Without the key the pipeline uses ``threading``. An unknown name, or an
option the backend does not accept, raises ``ValueError`` when the
``Pipeline`` is created.

Threads in one process
----------------------

``ThreadingTransport`` is the default: every worker is an OS thread, every
queue a ``queue.Queue`` bounded by ``JUTURNA_MAX_QUEUE_SIZE``. All the nodes
share one process and one file system. It cannot reach another worker: a
link towards a node of another worker raises ``ValueError`` at warmup.

In a browser tab
----------------

``BrowserTransport`` runs the pipeline in Pyodide, the Python interpreter
compiled to WebAssembly. Workers are made concurrent by JSPI (JavaScript
Promise Integration), and queues that cross Web Workers are rings on a
``SharedArrayBuffer``. It differs from the threading backend in a few
places:

- a queue slot has a fixed size (``max_payload_bytes``, 2,000,000 bytes by
  default): ``put()`` raises ``ValueError`` for a message that does not fit;
- a queue holds ``queue_capacity`` messages (8 by default), not
  ``JUTURNA_MAX_QUEUE_SIZE``;
- image, audio and bytes payloads cross Workers on a binary path, other
  payloads are pickled;
- a queue that nothing in another Worker writes to stays local, and its
  messages stay Python objects.

Pipelines across workers
------------------------

A node runs in the worker named by its ``worker`` key, ``main`` when the key
is missing. ``Pipeline(config, worker=...)`` builds only the nodes of that
worker. A link towards a node of another worker delivers to the object
returned by ``transport.remote_destination(name)``; a link from a node of
another worker only records it among the origins of the local node. Cycles
are checked on the local graph only.

Every worker loads the same configuration, so the nodes and links are
written once. Today ``BrowserTransport`` is the backend that can reach other
workers: each Web Worker runs the pipeline with its own ``worker`` name.

Telemetry and capabilities
--------------------------

Each backend declares what it offers in ``capabilities``, and each telemetry
manager declares what it needs in ``requires``. A pipeline whose telemetry
needs something the transport does not offer fails with ``ValueError``.

.. list-table::
   :header-rows: 1
   :widths: 20 30 50

   * - Telemetry
     - Requires
     - Available with
   * - ``csv``
     - ``shared_fs``
     - ``threading``
   * - ``memory``
     - nothing
     - every transport
   * - ``browser``
     - ``page_channel``
     - ``browser``

A node on another machine
-------------------------

Moving one node to another machine does not need a different transport. A
node marked ``warped`` is replaced at warmup by a warp node, which sends
each message over gRPC to a remote Juturna service and passes on the
answer; the rest of the pipeline runs as before. :doc:`remote` explains the
mechanism, and :doc:`../how_to/remotise_node` shows the steps.
