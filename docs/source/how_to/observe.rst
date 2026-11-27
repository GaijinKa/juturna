Observe a pipeline
==================

This guide shows how to see what a running pipeline is doing: its logs, the
health of its nodes, telemetry records, and the files it writes.

Logging
-------

Every node has a logger, ``self.logger``, ready to use anywhere in its code:

.. code-block:: python

    class MyAwesomeNode(Node[BasePayload, BasePayload]):
        def update(self, message: Message[BasePayload], **kwargs):
            self.logger.info('node did something awesome!')

The logger of a node is a child of the logger of its pipeline, which is a
child of ``jt``: every entry names the pipeline and the node that wrote it.
Since loggers are named after the components, you can set the level of each
one. Here everything logs at ``DEBUG``, except ``node_1``, which logs errors
only:

.. code-block:: python

    import logging

    import juturna as jt


    jt.log.jt_logger().setLevel(logging.DEBUG)
    jt.log.jt_logger('my_pipe.node_1').setLevel(logging.ERROR)

    pipe = jt.components.Pipeline.from_json('config.json')
    pipe.warmup()

.. code-block:: console

    2026-02-12 15:03:54 | INFO     | jt.my_pipe.node_0       | init sources: []
    2026-02-12 15:03:54 | INFO     | jt.my_pipe.node_0       | trx created, model id 123197287926000
    2026-02-12 15:03:55 | INFO     | jt.my_pipe              | warmed up node node_0
    2026-02-12 15:03:55 | ERROR    | jt.my_pipe.node_1       | model not found, defaulting
    2026-02-12 15:03:55 | INFO     | jt.my_pipe              | warmed up node node_1
    2026-02-12 15:03:55 | INFO     | jt.my_pipe              | warmed up node node_2
    2026-02-12 15:03:55 | INFO     | jt.my_pipe.node_3       | endpoint reached
    2026-02-12 15:03:55 | INFO     | jt.my_pipe              | warmed up node node_3
    2026-02-12 15:03:55 | INFO     | jt.my_pipe              | pipe warmed up!

Formatters and handlers
^^^^^^^^^^^^^^^^^^^^^^^

``jt.log.formatter()`` picks one of the built-in formatters: ``simple``,
``colored``, ``full`` (default), ``compact``, ``development``, ``minimal``
and ``json``. ``jt.log.add_handler()`` adds a handler, such as a file:

.. code-block:: python

    import logging

    import juturna as jt


    jt.log.formatter('minimal')
    jt.log.add_handler(logging.FileHandler('juturna.log'), formatter='development')

Health
------

Every node counts its failures. ``pipeline.status`` returns them, with the
state of the pipeline and of each node:

.. code-block:: python

    >>> pipe.status['nodes']['node_1']['health']
    {'update_failures': 1,
     'worker_failures': 0,
     'source_failures': 0,
     'rejected_items': 0,
     'last_failure_at': 1794437137.17,
     'last_failure': 'ValueError: model not found',
     'stuck_workers': []}

- ``update_failures`` and ``source_failures`` count the exceptions raised by
  ``update()`` and by the source function. The node logs them and goes on.
- ``rejected_items`` counts the things that were not a ``Message`` and were
  refused.
- ``last_failure`` is the most recent error; the traceback is in the log.
- ``stuck_workers`` lists the threads that did not exit when the node was
  killed.

The pipeline service returns the same data from
``GET /pipelines/{id}/status``.

Telemetry
---------

Telemetry records when each node receives and transmits a message. From the
records you can work out latency and throughput of every node, and follow a
message through the pipeline.

Turn it on in the pipeline configuration, choosing where the records go:

.. code-block:: json

    {
      "version": "3.0.0",
      "pipeline": {
        "name": "my_pipe",
        "id": "123456",
        "folder": "./run",
        "telemetry": { "name": "csv", "target": "telemetry.csv" },
        "nodes": [],
        "links": []
      }
    }

With the ``csv`` manager, the file ``./run/telemetry.csv`` fills up while the
pipeline runs:

.. code-block:: text

    ts,evt,node,origin,msg_id,src_id,size,worker
    1794437137.17,rx,A,A,0,,5,main
    1794437137.17,tx,A,A,0,0,5,main
    1794437137.18,rx,B,A,0,0,5,main
    1794437138.18,tx,B,B,1,0,12,main

Reading the four lines: source node ``A`` received its own message 0 and
transmitted it; node ``B`` received it and, a second later, transmitted
message 1, made while processing message 0 (``src_id``).

Use ``{"name": "memory"}`` to keep the records in memory instead. The
pipeline service returns the records of either manager from
``GET /pipelines/{id}/telemetry``.

The managers, their options and the meaning of every field are in
:ref:`reference_configuration`.

Files
-----

Each node has a folder of its own inside the pipeline folder, named after the
node. Its path is ``self.pipe_path``:

.. code-block:: python

    def update(self, message: Message, **kwargs):
        with open(pathlib.Path(self.pipe_path, 'notes.txt'), 'a') as f:
            f.write('saving another entry\n')

``self.dump_json(message, 'file_name.json')`` writes a message there as JSON.
To save every message a node transmits without touching its code, add
``"auto_dump": true`` to the node in the pipeline configuration:

.. code-block:: json

    {
      "name": "node_name",
      "type": "PassthroughIdentity",
      "auto_dump": true,
      "configuration": {}
    }
