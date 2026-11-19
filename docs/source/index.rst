:og:title: Juturna · Python framework for real-time AI pipelines
:og:description: Juturna is a Python framework for real-time AI pipelines on audio, video and data, built for fast prototyping that doesn't stop at the prototype: the same pipeline then runs behind an HTTP service or with its heaviest nodes on other machines.

.. meta::
   :description: Juturna is a Python framework for real-time AI pipelines on audio, video and data, built for fast prototyping that doesn't stop at the prototype: the same pipeline then runs behind an HTTP service or with its heaviest nodes on other machines.

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Start

   Home <self>
   how_to/install
   tutorials/first_pipeline
   how_to/migrate_from_2

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Examples

   examples/index
   examples/voice_assistant
   examples/video_detection

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Explanation

   explain/rationale
   explain/entities_overview
   explain/pipelines
   explain/nodes
   explain/messages
   explain/transports
   explain/remote

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Deploy

   how_to/choose_where_it_runs
   how_to/serve_pipelines
   how_to/remotise_node
   how_to/docker

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Guides

   how_to/create_pipelines
   how_to/environment
   how_to/observe
   troubleshooting

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Nodes

   catalog/nodes/overview
   catalog/nodes/sources
   catalog/nodes/processing
   catalog/nodes/sinks
   how_to/create_nodes
   Contribute a node to juturna-nodes <catalog/contribute/new_node>

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
   :maxdepth: 2
   :hidden:
   :caption: Reference

   reference/configuration
   reference/cli
   reference/http_api
   reference/constants
   apis/explore

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Work with Meetecho

   work_with_meetecho

Juturna
=======

.. raw:: html

   <table class="jt-badges">
     <tr><th>juturna</th><td>
       <a href="https://pypi.org/project/juturna/"><img alt="PyPI juturna" src="https://img.shields.io/pypi/v/juturna?style=for-the-badge&amp;label=juturna"></a>
       <a href="https://pypi.org/project/juturna/"><img alt="Python versions" src="https://img.shields.io/pypi/pyversions/juturna?style=for-the-badge"></a>
       <a href="https://github.com/meetecho/juturna/actions/workflows/unit-tests.yml"><img alt="Unit tests" src="https://img.shields.io/github/actions/workflow/status/meetecho/juturna/unit-tests.yml?branch=main&amp;style=for-the-badge&amp;label=tests"></a>
       <a href="https://github.com/meetecho/juturna/actions/workflows/gh-pages.yml"><img alt="Docs" src="https://img.shields.io/github/actions/workflow/status/meetecho/juturna/gh-pages.yml?branch=main&amp;style=for-the-badge&amp;label=docs"></a>
       <a href="https://github.com/meetecho/juturna/blob/main/LICENSE"><img alt="License MIT" src="https://img.shields.io/github/license/meetecho/juturna?style=for-the-badge"></a>
       <a href="https://github.com/astral-sh/ruff"><img alt="Ruff" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&amp;style=for-the-badge"></a>
       <a href="https://www.meetecho.com/en/?utm_source=juturna-docs&amp;utm_medium=docs&amp;utm_campaign=juturna3"><img alt="By Meetecho" src="https://img.shields.io/badge/by-Meetecho-1a6dad?style=for-the-badge"></a>
     </td></tr>
     <tr><th>juturna-nodes</th><td>
       <a href="https://pypi.org/project/juturna-nodes/"><img alt="PyPI juturna-nodes" src="https://img.shields.io/pypi/v/juturna-nodes?style=for-the-badge&amp;label=juturna-nodes"></a>
     </td></tr>
     <tr><th>juturna-browser</th><td>
       <a href="https://github.com/meetecho/juturna-browser"><img alt="juturna-browser release" src="https://img.shields.io/github/v/tag/meetecho/juturna-browser?style=for-the-badge&amp;label=juturna-browser"></a>
       <a href="browser/demos.html"><img alt="Browser demos" src="https://img.shields.io/badge/browser-demos-1a6dad?style=for-the-badge"></a>
     </td></tr>
   </table>

Juturna is a Python framework for real-time AI pipelines on audio, video and
data, built for fast prototyping that doesn't stop at the prototype.
You write the processing steps as nodes, describe how they connect in a JSON
file, and Juturna runs the graph: each node in worker threads of its own,
with messages frozen on the way out so several nodes can read the same
payload without copying it. The pipeline you try out in one process is the
one you deploy: it also runs behind an HTTP service, or with its heaviest
nodes moved to other machines, such as a model on a GPU, without rewriting
its nodes. For now, remote nodes need a trusted network or a VPN: their
connection has no authentication and no encryption yet.

.. container:: jt-figure

   .. raw:: html
      :file: diagrams/what_juturna_is.svg

   .. raw:: html
      :file: diagrams/what_juturna_is_narrow.svg

   **Figure 1.** A pipeline: sources, processing and AI nodes, and destinations, wired in one JSON file. The dashed nodes are yours: write your node or let Meetecho build it for you (:ref:`Write your first nodes <tutorial>`, :doc:`Work with Meetecho <work_with_meetecho>`).

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

Check it and run it. ``--auto`` starts the pipeline without waiting for
enter, and ``--timeout`` stops it after that many seconds: give it a little
longer than your audio file.

.. code-block:: console

    $ python -m juturna validate --config pipeline.json
    $ python -m juturna launch --config pipeline.json --auto --timeout 60

The text comes out as lines like ``[whisper] <the transcribed text>``, one
more each time Whisper transcribes its latest blocks of speech.

The quick start is audio only: for video, see
:doc:`examples/video_detection`.

.. card:: Run it in your browser tab
    :class-card: jt-cta

    Juturna pipelines run on Pyodide, inside the page, with nodes written for
    the browser. Nothing to install: the demos run the models in your tab and
    the audio stays on the device. They need Chrome 137 or later (JSPI).

    .. button-ref:: browser/demos
        :ref-type: doc
        :color: primary

        Try the demos

    :doc:`Read how it works <browser/index>`

For complete pipelines to run and adapt, see the :ref:`examples <examples>`.
To write nodes of your own, follow :ref:`Write your first nodes <tutorial>`:
it builds a pipeline from scratch in about ten minutes.

Explore the documentation
-------------------------

.. grid:: 1 2 2 2
    :gutter: 3

    .. grid-item-card:: ``jt/start``
        :link: how_to/install
        :link-type: doc

        New to Juturna? Install it with the optional groups you need, then
        run the quick start above. Coming from 2.x? The migration guide is
        here too.

    .. grid-item-card:: ``jt/examples``
        :link: examples
        :link-type: ref

        Complete pipelines to run and adapt: a voice assistant, object
        detection on a video. Each one with its install, configuration and
        expected output.

    .. grid-item-card:: ``jt/deploy``
        :link: how_to/choose_where_it_runs
        :link-type: doc

        Run pipelines behind a REST API, move a heavy node to another
        machine, ship it all in a container.

    .. grid-item-card:: ``jt/guides``
        :link: how_to/create_pipelines
        :link-type: doc

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

    .. grid-item-card:: ``jt/browser``
        :link: browser/index
        :link-type: doc

        Juturna pipelines on Pyodide, in the Web Workers of a page, with
        demos to try.

Brewed by Meetecho
------------------

Juturna is brewed by `Meetecho <https://www.meetecho.com/en/?utm_source=juturna-docs&utm_medium=docs&utm_campaign=juturna3>`_, the team behind the Janus® WebRTC server and a 2009 spin-off of the University of Napoli Federico II.
Taking a pipeline to production? We write the nodes you are missing, tune
performance, and offer consulting and support.

.. button-link:: https://www.meetecho.com/en/?utm_source=juturna-docs&utm_medium=docs&utm_campaign=juturna3#contact
    :color: primary

    Talk to the Meetecho team

Juturna is open source under the MIT license: the code is on
`GitHub <https://github.com/meetecho/juturna>`_, and the
`contributing guidelines <https://github.com/meetecho/juturna/blob/main/CONTRIBUTING.md>`_
explain how to propose a change. To report a vulnerability, follow the
`security policy <https://github.com/meetecho/juturna/blob/main/SECURITY.md>`_: it covers private reporting, handling and
coordinated disclosure, under the EU Cyber Resilience Act.
