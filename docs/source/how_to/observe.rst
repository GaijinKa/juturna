Observability in Juturna
========================

Logging
-------

Nodes have a built-in logger that can be used straight out of the box. A node
logger is created as a sublogger of its containing pipeline, which in turn is
a sublogger of the juturna process. Nothing special is required to use the
juturna logger within a node, and it can be used anywhere in its class code:

.. code-block:: python

    from juturna.components import Node
    from juturna.components import Message
    from juturna.payloads import BasePayload


    class MyAwesomeNode(Node[BasePayload, BasePayload]):
        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

            # initialisation code

            self.logger.info('awesome node created!')

        def update(self, message: Message[BasePayload]):
            # run the node update logic

            self.logger.info('node did something awesome!')

Logging messages will carry useful pieces of informatio so that, once printed,
it will be easy to understand which entry is printed by which node. As an
example, consider the script below, loading a pipe called ``my_pipe``:

.. code-block:: python

    import logging

    import juturna as jt


    logging.basicConfig(level=logging.DEBUG)

    pipe = jt.components.Pipeline.from_json('config.json')
    pipe.warmup()

This will generate logging entries split by node:

.. code-block:: console

    2026-02-12 15:05:20 | INFO     | jt.my_pipe.node_0       | init sources: []
    2026-02-12 15:03:54 | INFO     | jt.my_pipe.node_0       | trx created, model id 123197287926000
    2026-02-12 15:03:55 | INFO     | jt.my_pipe.node_1       | audio loaded
    2026-02-12 15:03:55 | INFO     | jt.my_pipe.node_1       | duration: 149.942875
    2026-02-12 15:03:55 | INFO     | jt.my_pipe              | warmed up node node_0
    2026-02-12 15:03:55 | ERROR    | jt.my_pipe.node_1       | model not found, defaulting
    2026-02-12 15:03:55 | INFO     | jt.my_pipe              | warmed up node node_1
    2026-02-12 15:03:55 | INFO     | jt.my_pipe              | warmed up node node_2
    2026-02-12 15:03:55 | INFO     | jt.my_pipe.node_3       | endpoint reached
    2026-02-12 15:03:55 | INFO     | jt.my_pipe              | warmed up node node_3
    2026-02-12 15:03:55 | INFO     | jt.my_pipe              | pipe warmed up!

Here we can see that each entry tells us the node that generated it, the pipe it
belongs to, and lastly the logging message.

Thanks to their hierarchical structure, loggers can be selectivel enabled or
disable only through the names of their corresponding components. Looking again
at the pipe above, we can tell the loggers to raise the level to ``ERROR`` only
for ``node_1``:

.. code-block:: python

    import logging

    import juturna as jt

    logging.basicConfig(level=logging.DEBUG)
    jt.log.jt_logger('my_pipe.node_1').setLevel(logging.ERROR)

    pipe = jt.components.Pipeline.from_json('config.json')
    pipe.warmup()

This time, the logs will look like:

.. code-block:: console

    2026-02-12 15:05:20 | INFO     | jt.my_pipe.node_0       | init sources: []
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

Logs in juturna can be formatted using built-in formatters: ``simple``,
``colored``, ``full`` (default), ``compact``, ``development``, ``minimal`` and
``json``. To change it, run:

.. code-block:: python

    import logging

    import juturna as jt


    logging.basicConfig(level=logging.DEBUG)
    jt.log.formatter('minimal')

    pipe = jt.components.Pipeline.from_json('config.json')
    pipe.warmup()

.. code-block:: console

    INFO: init sources: []
    INFO: trx created, model id 123197287926000
    INFO: audio loaded
    INFO: duration: 149.942875
    INFO: warmed up node node_0
    ERROR: model not found, defaulting
    INFO: warmed up node node_1
    INFO: warmed up node node_2
    INFO: endpoint reached
    INFO: warmed up node node_3
    INFO: pipe warmed up!

New handlers can also be added to the juturna logger. As an example, a file
handler can be added, to store the logs into a file:

.. code-block:: python

    import logging

    import juturna as jt


    logging.basicConfig(level=logging.DEBUG)
    handler = logging.FileHandler('juturna.log')

    jt.log.add_handler(handler, formatter='development')

Telemetry
---------

In juturna, it is possible to collect low-level data about basic events such as
receptions and transmissions. Such data can be used to compute useful metrics
about nodes latency, bandwidth and throughput.

Telemetry can be activated on a pipeline level. To do so, add the ``telemetry``
entry in the pipe configuration file, with the ``name`` of the manager that
collects the telemetry data and the options of that manager. Without a
``telemetry`` entry, no telemetry is collected.

.. code-block:: json

    {
      "version": "1.0.2",
      "plugins": ["./plugins"],
      "pipeline": {
        "name": "my_pipe",
        "id": "123456",
        "folder": "./run",
        "telemetry": {"name": "csv", "target": "tele.csv"},
        "nodes": [],
        "links": []
      }
    }

Once the pipe is started and running, the file ``./run/my_pipe/tele.csv`` will
be incrementally filled with telemetry entries. Each node records a telemetry
entry:

- every time it receives a message,
- every time it transmits a message.

Each entry is formatted as follows:

.. code-block:: text

    time, event, node, origin, msg_id, src_id, size, worker

Generally speaking then, a telemetry record is a collection of basic information
related to a particular event.

- ``time`` is the timestamp at which the event was recorded (this is taken when
  the telemetry record is built within the node)
- ``event`` is the event being metered (``rx`` for a reception event, ``tx`` for
  a transmission event)
- ``node`` is the name of the node recording the event
- ``origin`` is the name of the node that produced the message related to the
  recorded event (for a reception event, this is the node that generated the
  received message; for a transmission message, this will be the same as
  ``node``)
- ``msg_id`` is the id of the message that triggered the event
- ``src_id`` is the id of the **previous** message that triggered the last
  recorded event
- ``size`` is the size in bytes of the message that triggered the event
- ``worker`` is the name of the worker the pipeline runs in (``main`` unless
  the pipeline is split across several workers)

Imagine a pipeline with a source node A, a processing node B, and a sink node C.
In its implementation, node A has a function that writes messages on its own
internal queue, triggering the ``update`` function. When the first message is
*received* by the node (so, generated and read by the worker thread), the first
telemetry event will be recorder, and it will look something like this:

.. code-block:: text

    t_0,rx,A,A,0,,s_0,main

Here, node A both generated and received the message, so ``node`` and ``origin``
are the same. Also, being this the first message processed by the node, there is
no id stored of previous events, so ``src_id`` is none.

When this message is transmitted, another telemetry entry will be recorded:

.. code-block:: text

    t_1,tx,A,A,0,0,s_0,main

At this point, node B receives the message, and produces its own telemetry
read:

.. code-block:: text

    t_2,rx,B,A,0,,s_0,main

This entry tells us that at time ``t_2`` node B received message with id 0
generated by node A, and no previous message passed through it. B chruns the
message content and sends a new message to C:

.. code-block:: text

    t_3,tx,B,B,1,0,s_1,main

Telemetry managers
^^^^^^^^^^^^^^^^^^

The ``name`` of the ``telemetry`` entry selects the manager that collects the
records. Every other key of the entry is an option of that manager.

.. list-table::
   :header-rows: 1
   :widths: 12 30 58

   * - ``name``
     - Requires
     - Behaviour and options
   * - ``csv``
     - a file system shared by the pipeline (the threading transport)
     - Writes the records on a CSV file from a worker of its own. ``target``
       (required) is a plain file name (up to 128 letters, digits, ``_``, ``-``
       and ``.``, no folders), written in the pipeline folder.
       ``max_pending`` (default 10000) is how many batches can wait to be
       written: when the writer cannot keep up, the new batches are dropped,
       so that the nodes never wait for the telemetry. The number of dropped
       records is logged when the pipeline stops.
   * - ``memory``
     - nothing
     - Keeps the latest records in memory. ``max_records`` (default 10000) is
       how many are kept: the oldest are dropped first.
   * - ``browser``
     - the browser transport
     - Like ``memory``, and every batch of records is also posted to the web
       page that hosts the pipeline.

A ``telemetry`` entry that cannot be honoured (an unknown ``name``, an option
the manager does not accept, a manager the transport cannot support, such as
``csv`` with the browser transport) raises a ``ValueError`` when the pipeline
is warmed up. ``python -m juturna validate`` reports it beforehand.

When a pipeline is served through the HTTP service, the records are available
at ``GET /pipelines/{pipeline_id}/telemetry``. The response is
``{"pipeline": <id>, "telemetry": [...]}``, with one record per entry of the
list and the fields in the order described above (the ``worker`` last).

Migrating from version 2
^^^^^^^^^^^^^^^^^^^^^^^^

- The ``telemetry`` entry was a file name (``"telemetry": "tele.csv"``). It is
  now a dictionary: ``"telemetry": {"name": "csv", "target": "tele.csv"}``.
  The old form raises a ``ValueError`` when the pipeline is warmed up.
- Every record has a new, last field: ``worker``. The CSV file has a matching
  ``worker`` column.
- The telemetry endpoint of the HTTP service returns the list of records
  instead of the text of the CSV file.
- The browser transport used to switch the telemetry off with a warning. Ask
  for ``{"name": "browser"}`` to collect it.
- Only a missing or ``null`` ``telemetry`` entry switches the telemetry off.
  Any other value that is not a dictionary, such as ``""`` or ``false``, which
  used to be ignored, now raises a ``ValueError``.
- ``TelemetryManager`` is no longer the CSV writer of
  ``juturna.components._telemetry_manager``, which is removed: it is now the
  protocol that every manager follows, in ``juturna.telemetry``. The CSV writer
  is ``juturna.telemetry.csv.CsvTelemetry``.
- A CSV file written by version 2 has no ``worker`` column: its rows are not
  returned by ``records()`` or by the telemetry endpoint, and new rows are
  appended after them.
- The ``csv`` manager no longer queues without a limit: when it cannot write
  fast enough, the newest batches are dropped (``max_pending``). Its start now
  fails if the file cannot be written, where the writer used to die silently.
  ``target`` cannot be ``config.json``, which the pipeline writes in the same
  folder.
- A transport must declare ``capabilities`` (a new attribute of
  ``TransportBackend``) to be used with the telemetry: the ``supports_telemetry``
  attribute is gone.
- ``juturna validate`` has two new checks, for the transport and for the
  telemetry. A configuration with an unknown transport, or with options the
  transport or the telemetry manager does not accept, is now reported.
- A transport specification that is neither a name nor a dictionary raises a
  ``ValueError``.

Interact with the filesystem
----------------------------

A pipeline can be configured with its own folder on the filesystem. Here,
each node will be assigned a directory where it can store data, artifacts, or
anything else the node developer might need to. The following pipe:

.. code-block:: json

    {
      "version": "0.1.0",
      "plugins": ["./plugins"],
      "pipeline": {
        "id": "quality",
        "name": "quality",
        "folder": "./pipeline",
        "nodes": [],
        "links": []
    }

will create the ``./pipeline`` folder, local to where the juturna process was
launched, and as many subfolders are there are nodes in the pipe.

The node class offers useful tools to access the filesystem. Assuming we want to
save some text to file during an ``update`` call, we can simply do:

.. code-block:: python

    def update(self, message: Message):
        # do update stuff

        with open(pathlib.Path(self.pipe_path, 'file_dump.txt'), 'a') as f:
            f.write('saving another entry')

So, ``self.pipe_path`` points to the folder on the filesystem assigned to this
node.

Similarly, calling ``dump_json(message, f_name)`` will write a json version of a
message in a node folder. This can be triggered at any time in the node
execution, however, every transmitted message by the node can be automatically
dumped to disk by adding the ``"auto_dump": true`` flag in the node
configuration.

.. code-block:: json

    {
      "name": "node_name",
      "type": "<NODE_TYPE>"
      "mark": "<NODE_MARK>"
      "auto_dump": true
      "configuration": {}
    }
