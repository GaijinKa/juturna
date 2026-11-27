Write, check and run a pipeline
===============================

This guide shows how to put together a pipeline from nodes that are already
installed, check its configuration, and run it from the command line or from
your own code.

The example transcribes an audio file with four nodes of the
``juturna-nodes`` package: ``AudioFile`` reads the file in blocks,
``VadSilero`` keeps the blocks that hold speech, ``TranscriberWhisper`` turns
them into text, and ``NotifierConsole`` prints the text on the terminal.

Install the nodes
-----------------

.. code-block:: console

    (.venv) $ pip install "juturna-nodes[audio-file,vad-silero,transcriber-whisper]"

Each node with heavy dependencies has an extra named after it:
``vad-silero`` pulls in PyTorch, so it is a large download. The
README of
`juturna-nodes <https://github.com/meetecho/juturna_nodes>`_ lists the
available nodes and the optional groups some of them need. Every node comes
with a ``config.toml`` file holding its arguments and their defaults.

Write the configuration
-----------------------

Save this as ``transcribe.json``, and point ``file_source`` to an audio file
in English:

.. code-block:: json

    {
      "version": "3.0.0",
      "pipeline": {
        "name": "transcribe_file",
        "id": "transcribe_file_01",
        "folder": "./run",
        "nodes": [
          {
            "name": "audio",
            "type": "AudioFile",
            "configuration": { "file_source": "sample.wav", "block_size": 2 }
          },
          {
            "name": "vad",
            "type": "VadSilero",
            "configuration": { "min_silence_duration_ms": 500 }
          },
          {
            "name": "whisper",
            "type": "TranscriberWhisper",
            "configuration": {
              "model_name": "tiny",
              "only_local": false,
              "device": "cpu"
            },
            "auto_dump": true
          },
          {
            "name": "console",
            "type": "NotifierConsole",
            "configuration": {}
          }
        ],
        "links": [
          { "from": "audio", "to": "vad" },
          { "from": "vad", "to": "whisper" },
          { "from": "whisper", "to": "console" }
        ]
      }
    }

What to know when writing one:

- ``type`` is the class name for the nodes of ``juturna-nodes``
  (``AudioFile``), and the full path for the others
  (``contrib.<package>.nodes.<Class>``);
- ``configuration`` only needs the arguments you want to change: here
  Whisper may download its model (``only_local``) and runs on the CPU
  (``device``), as its defaults expect a local model and a GPU;
- ``folder`` is where the pipeline writes its files: a copy of the
  configuration, and one folder per node;
- ``auto_dump`` saves every message a node transmits as a JSON file in its
  folder, handy to see what goes through.

All the keys are described in :ref:`reference_configuration`.

If you prefer to be guided, ``python -m juturna create`` (``pipebuilder``
group) starts an interactive builder: press TAB to pick among the installed
nodes, then use ``.link`` to connect them and ``.save`` to write the file.
``.help`` lists the other commands.

Check it
--------

.. code-block:: console

    (.venv) $ python -m juturna validate --config transcribe.json

The command checks the structure of the file, that every node type is
installed, that links join existing nodes, and that the graph has no cycles.
It exits with status 1 when a check fails, so it fits in a CI job. Warnings
tell about things that are legal but suspicious, such as a configuration key
the node does not know.

Run it from the command line
----------------------------

.. code-block:: console

    (.venv) $ python -m juturna launch --config transcribe.json

The pipeline warms up, then waits for you to press enter to start, and again
to stop. With ``--auto`` it starts on its own and runs until every node has
stopped, or for ``--timeout`` seconds.

While it runs, the transcription comes out on the terminal, as lines like
``[whisper] <the transcribed text>``: Whisper transcribes its last few
blocks of speech every time a new one arrives, so a sentence grows line
after line. Every message Whisper sends is also in ``./run/whisper/``, as a
JSON file.

``AudioFile`` stops at the end of the file but the other nodes keep
waiting, so with ``--auto`` give a ``--timeout`` long enough for the file.

Run it from Python
------------------

A pipeline is a plain object, with one method for each step of its life:

.. code-block:: python

    import time

    import juturna as jt


    pipeline = jt.components.Pipeline.from_json('transcribe.json')

    pipeline.warmup()
    pipeline.start()

    try:
        time.sleep(60)
    finally:
        pipeline.stop()
        pipeline.destroy()

``Pipeline(config)`` takes the configuration as a dictionary instead of a
file path.

``stop()`` lets the nodes finish the messages they already received, and
``kill()`` drops them. A stopped pipeline cannot be started again. The whole
lifecycle is in :ref:`explain_pipelines`.
