.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Start

   tutorials/first_pipeline
   how_to/install
   how_to/migrate_from_2

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Deploy

   explain/where_it_runs
   how_to/remotise_node
   how_to/serve_pipelines
   how_to/docker

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Guides

   how_to/index
   how_to/create_pipelines
   how_to/voice_assistant
   how_to/environment
   how_to/observe
   troubleshooting

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Reference

   reference/configuration
   reference/cli
   reference/http_api
   reference/constants
   apis/explore

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Explanation

   explain/rationale
   explain/entities_overview
   explain/pipelines
   explain/nodes
   explain/messages
   explain/remote

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Nodes

   catalog/nodes/overview
   catalog/nodes/sources
   catalog/nodes/processing
   catalog/nodes/sinks
   how_to/create_nodes
   catalog/contribute/new_node

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: In the browser

   browser/index
   browser/guide
   browser/write-a-node
   browser/how-it-works
   browser/demos
   browser/api
   browser/development

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Work with Meetecho

   work_with_meetecho

|version-badge|

Juturna
=======

Juturna is a Python library for real-time pipelines of audio, video and data.
You write the processing steps as nodes, describe how they connect in a JSON
file, and Juturna runs the graph: each node in worker threads of its own,
with messages frozen on the way out so several nodes can read the same
payload without copying it. A pipeline runs in one process, behind an HTTP
service, or with its heaviest nodes moved to other machines, such as a model
on a GPU.

The same pipeline also runs in a browser tab, on Pyodide: see
:doc:`browser/index`.

Quick start
-----------

.. include:: _includes/about_example.rst

Transcribe an audio file: Juturna reads it in blocks, a voice activity
detector cuts it into speech segments, Whisper transcribes them and the text
is printed on the terminal. Install Juturna (Python 3.12 or newer) and the
nodes the pipeline uses:

.. code-block:: console

    $ pip install juturna "juturna-nodes[av,audio-ml]" \
          --index-url https://download.pytorch.org/whl/cpu \
          --extra-index-url https://pypi.org/simple

The ``audio-ml`` group pulls in PyTorch. On Linux, the PyTorch wheels on PyPI
pull in the CUDA libraries: the two index options install the CPU-only build,
and the whole environment takes about 1.4 GB. With uv, add
``--index-strategy unsafe-best-match``:

.. code-block:: console

    $ uv pip install juturna "juturna-nodes[av,audio-ml]" \
          --index-url https://download.pytorch.org/whl/cpu \
          --extra-index-url https://pypi.org/simple \
          --index-strategy unsafe-best-match

On macOS and Windows the PyTorch wheels on PyPI carry no CUDA libraries, so
``pip install juturna "juturna-nodes[av,audio-ml]"`` is enough.

A pipeline is a list of nodes and the links between them. Save this as
``pipeline.json``, and point ``file_source`` to an audio file in English:

.. code-block:: json

    {
      "version": "3.0.0",
      "pipeline": {
        "name": "transcribe_file",
        "id": "transcribe_file_01",
        "folder": "./run",
        "nodes": [
          { "name": "audio", "type": "AudioFile",
            "configuration": { "file_source": "sample.wav", "block_size": 2 } },
          { "name": "vad", "type": "VadSilero",
            "configuration": { "min_silence_duration_ms": 500 } },
          { "name": "whisper", "type": "TranscriberWhisper",
            "configuration": { "model_name": "tiny", "only_local": false,
                               "device": "cpu" } },
          { "name": "console", "type": "NotifierConsole", "configuration": {} }
        ],
        "links": [
          { "from": "audio", "to": "vad" },
          { "from": "vad", "to": "whisper" },
          { "from": "whisper", "to": "console" }
        ]
      }
    }

Check it and run it: press enter to start, and again to stop once the file
is done.

.. code-block:: console

    $ python -m juturna validate --config pipeline.json
    $ python -m juturna launch --config pipeline.json

The text comes out as lines like ``[whisper] <the transcribed text>``, one
more each time Whisper transcribes its latest blocks of speech.

To write nodes of your own, follow the :ref:`tutorial <tutorial>`: it builds
a pipeline from scratch in about ten minutes.

Explore the documentation
-------------------------

.. grid:: 1 2 2 2
    :gutter: 3

    .. grid-item-card:: ``jt/start``
        :link: tutorial
        :link-type: ref

        New to Juturna? Install it and build your first pipeline, one step
        at a time. Coming from 2.x? The migration guide is here too.

    .. grid-item-card:: ``jt/deploy``
        :link: explain/where_it_runs
        :link-type: doc

        Run pipelines behind a REST API, move a heavy node to another
        machine, ship it all in a container.

    .. grid-item-card:: ``jt/guides``
        :link: howto
        :link-type: ref

        Recipes for the tasks you will meet: building pipelines,
        environment variables, observing a running pipeline,
        troubleshooting.

    .. grid-item-card:: ``jt/reference``
        :link: reference/configuration
        :link-type: doc

        The facts: configuration file, CLI, HTTP API, constants and the
        Python API.

    .. grid-item-card:: ``jt/explain``
        :link: rationale
        :link-type: ref

        The ideas behind Juturna: pipelines, nodes, messages, and how they
        work together.

    .. grid-item-card:: ``jt/nodes``
        :link: catalog/nodes/overview
        :link-type: doc

        Nodes ready to use from ``juturna-nodes``: RTP sources,
        transcription, voice activity detection, object detection,
        notifiers. And how to write your own.

.. grid:: 1
    :gutter: 3

    .. grid-item-card:: ``jt/browser``
        :link: browser/index
        :link-type: doc

        The same pipelines on Pyodide, in the Web Workers of a page, with
        demos to try.

Brewed by Meetecho
------------------

Juturna is brewed by `Meetecho <https://www.meetecho.com/>`_, hacking on
real-time media since 2009.
Taking a pipeline to production? We write the nodes you are missing, tune
performance, and offer consulting and support.

.. button-link:: https://www.meetecho.com/
    :color: primary

    Ping the maintainers

Juturna is open source under the MIT license: the code is on
`GitHub <https://github.com/meetecho/juturna>`_, and the
`contributing guidelines <https://github.com/meetecho/juturna/blob/main/CONTRIBUTING.md>`_
explain how to propose a change.
