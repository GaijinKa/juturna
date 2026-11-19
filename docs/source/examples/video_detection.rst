Detect objects in a video
=========================

.. note::

    A minimal example: no GPU, small models, not tuned for quality or latency.
    For production, :doc:`work with Meetecho </work_with_meetecho>`.

Read a video, detect the objects in it, and send a JSON event to a webhook
when a class of object shows up:

.. code-block:: text

    video ─► detector ─► events ─► webhook

- :ref:`VideoCapture <node-video-capture>` reads a video file, or a webcam,
  and keeps at most 5 frames per second;
- :ref:`DetectorYolox <node-detector-yolox>` finds the objects in each frame
  with YOLOX nano, one of the 80 COCO classes (people, cars, bicycles, ...);
- :ref:`DetectionEvents <node-detection-events>` turns them into one event
  per class, at most every 2 seconds;
- :ref:`NotifierHTTP <node-notifier-http>` posts each event to a URL.

Install
-------

.. code-block:: console

    $ pip install juturna "juturna-nodes[av,onnx]"

``av`` reads the video with PyAV, ``onnx`` runs the model with ONNX Runtime.
No PyTorch and no GPU are needed.

Get a test video
----------------

`Chinese Signal <https://commons.wikimedia.org/wiki/File:Chinese_Signal.webm>`_,
by XZise on Wikimedia Commons, is a 9 second clip of a road crossing in
1280×720, released under `CC0
<https://creativecommons.org/publicdomain/zero/1.0/>`_:

.. code-block:: console

    $ curl -L -o Chinese_Signal.webm \
          https://upload.wikimedia.org/wikipedia/commons/3/35/Chinese_Signal.webm

The configuration
-----------------

Save this as ``pipeline.json``, next to the video:

.. literalinclude:: ../../../examples/video_detection/pipeline.json
    :language: json

Check it:

.. code-block:: console

    $ python -m juturna validate --config pipeline.json

Run it
------

The events need somewhere to go. This small server prints the body of every
request it receives; save it as ``listener.py`` and start it in a terminal:

.. literalinclude:: ../../../examples/video_detection/listener.py
    :language: python

.. code-block:: console

    $ python listener.py
    listening on http://127.0.0.1:8080

Then, in a second terminal, run the pipeline:

.. code-block:: console

    $ python -m juturna launch --config pipeline.json --auto --timeout 15

On the first run the detector downloads YOLOX nano (3.7 MB) into
``$XDG_CACHE_HOME/juturna/models/`` (``~/.cache/juturna/models/`` by
default). The video lasts 9 seconds, but the end of a
file does not stop the pipeline: ``--timeout 15`` stops it after 15 seconds.

What comes out
--------------

The listener prints one JSON message per event, about 30 for this video.
This is the first one of a real run:

.. code-block:: json

    {"created_at": 1794866962.8509357, "creator": "events", "version": 0, "id": 7, "payload": {"event": "detection", "label": "car", "count": 4, "objects": [{"confidence": 0.872, "bbox": [322, 476, 902, 718]}, {"confidence": 0.854, "bbox": [2, 481, 156, 585]}, {"confidence": 0.546, "bbox": [766, 495, 967, 601]}, {"confidence": 0.481, "bbox": [866, 502, 1198, 713]}], "frame": 0, "timestamp": 1794866962.835211, "width": 1280, "height": 720}, "meta": {"pipe_id": "video_detection_01"}, "timers": {}}

The event is in ``payload``: four cars in the first frame, each with its
score and its box in pixels (``x1, y1, x2, y2``). The other fields are the
message envelope, which ``NotifierHTTP`` sends whole, with the pipeline id
in ``meta``. The same frame also gives events for ``traffic light`` and
``person``, and each class comes back at most every 2 seconds.

What to change
--------------

- **The input.** Point ``source`` to your own video, or to a webcam:
  ``"/dev/video0"`` (Linux only). A webcam has no end: run ``launch``
  without ``--auto --timeout 15``, and it waits for enter to start the
  pipeline and again to stop it.
- **The classes.** Add ``"targets": ["person", "car"]`` to the detector to
  keep only some of the 80 COCO classes, and raise ``confidence`` (0.3 by
  default) to drop the weaker detections.
- **The model.** ``yolox_tiny`` and ``yolox_s`` are larger and more
  accurate; any YOLOX model exported to ONNX works too, given its path.
- **The sink.** Change ``endpoint`` to your service.
  :ref:`NotifierConsole <node-notifier-console>` prints the events on the
  terminal instead, with no listener to run.
  :ref:`NotifierUDP <node-notifier-udp>` sends the same messages over UDP,
  split into chunks and base64 encoded by default: set its ``endpoint`` and
  ``port``, and put the chunks back together on the receiving side. The
  :doc:`catalogue </catalog/nodes/overview>` lists the other sinks.
- **A node of your own.** To count objects across frames, draw boxes or
  write events to a database, create a node with
  ``python -m juturna stub`` (see :doc:`/reference/cli`) and follow
  :doc:`/how_to/create_nodes`.
