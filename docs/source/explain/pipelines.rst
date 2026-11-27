.. _explain_pipelines:

Pipelines
=========

A pipeline is a configuration interpreter: it builds the nodes described in a
JSON configuration, links them, keeps their state and runs their lifecycle.
It holds no business logic: the pipeline handles the topology, the nodes
process the data.

Configuration
-------------

A pipeline configuration looks like this:

.. code-block:: json

    {
      "version": "3.0.0",
      "pipeline": {
        "name": "my_awesome_pipeline",
        "id": "1234567890",
        "folder": "./running_pipelines",
        "nodes": [ ],
        "links": [ ]
      }
    }

``name`` and ``id`` identify the pipeline: the name is used for logging, the
id by tools that manage several pipelines at once. ``folder`` is where the
pipeline keeps its files: a copy of the configuration, and one folder for each
node, where the node can store data and artifacts. ``nodes`` and ``links``
describe the graph. Every key is described in
:ref:`reference_configuration`. How to create a pipeline from a file or a
dictionary and run it from Python is in :doc:`/how_to/create_pipelines`.

Pipeline lifecycle
------------------

Creating a pipeline object builds no node yet. A pipeline is always in one of
five states:

- ``NEW``: created, its nodes not built yet;
- ``READY``: its nodes are built, linked, and hold the resources they need;
- ``RUNNING``: its nodes consume, process and send data;
- ``STOPPED``: it was running and is not anymore. It cannot be started
  again: destroy it and create a new one from the same configuration;
- ``DESTROYED``: it released everything it held.

.. container:: jt-figure

   .. raw:: html
      :file: ../diagrams/pipeline_lifecycle.svg

   **Figure 1.** Pipeline states and the calls that move between them. ``Pipeline(config)`` creates a ``NEW`` pipeline; a stopped pipeline is final.

These methods move a pipeline through its lifecycle:

``warmup()`` builds and links the nodes, and calls the warm up of each
(:ref:`explain_nodes`), moving the pipeline from ``NEW`` to ``READY``. It can
take a while, when nodes load models or open connections.

``start()`` starts every node, moving the pipeline from ``READY`` to
``RUNNING``.

``stop()`` interrupts the pipeline execution, moving it from ``RUNNING`` to
``STOPPED``. Nodes are stopped from the sources down, and each one processes
the messages it already received before stopping, so nothing is lost.

``destroy()`` releases the nodes and their resources, moving the pipeline to
``DESTROYED``. It can be called in any state; a running pipeline is stopped
first.

``kill()`` stops a running pipeline without processing the messages still in
the queues of its nodes, and without waiting for a node that is busy: every
node thread gets ``JUTURNA_THREAD_JOIN_TIMEOUT`` seconds to exit, then it is
left behind.

Stopping when something goes wrong
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``stop()`` waits for every ``update()`` call in progress, however long it
takes. When a node does not come back, call ``kill()`` from another thread:
it is the only lifecycle method allowed while a ``stop()`` is in progress
(every other one raises ``PipelineBusyError``). The kill reaches every node,
the stop in progress no longer waits and discards the pending messages, and
``kill()`` returns once that stop is over. The same holds for the stop that
``destroy()`` runs on a running pipeline.

.. code-block:: python

   stopper = threading.Thread(target=pipeline.stop)
   stopper.start()
   stopper.join(timeout=30)

   if stopper.is_alive():
       pipeline.kill()

``stop()``, ``kill()`` and ``destroy()`` always go through all the nodes. When
the ``stop()`` or the ``destroy()`` of a node raises, the error is logged, the
threads of that node are stopped all the same, and the other nodes follow. The
pipeline reaches ``STOPPED`` (or ``DESTROYED``), and only then the first error
is raised to the caller: a pipeline with a node that fails to clean up can
still be destroyed.

An interrupt (``ctrl+c``) during ``stop()`` or ``destroy()`` leaves the
pipeline free for another call, which goes on with the nodes that are left.

A node that stops on its own does not hold the others: the messages sent to a
stopped node are discarded, so the nodes before it never wait for it.

``update_node()`` changes a property of a node from the thread of the caller.
It raises ``PipelineNotReadyError`` before the warm up and
``PipelineDestroyedError`` after the destruction.

A call that does not respect these transitions raises an exception that says
why, such as ``PipelineNotReadyError`` for a ``start()`` before the warm up or
``PipelineStoppedError`` for a ``start()`` after a stop. They all derive from
``PipelineStateError``, which is a ``RuntimeError``. Calling a method on a
pipeline that is already where the method leads (``stop()`` on a stopped
pipeline) does nothing.

If a node fails during ``warmup()`` or ``start()``, the pipeline undoes what
it did and goes back to the state it was in, so the call can be tried again.
