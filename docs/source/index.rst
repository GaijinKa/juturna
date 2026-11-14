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
   :caption: Where it runs

   explain/where_it_runs
   how_to/remotise_node
   how_to/serve_pipelines
   how_to/docker

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: In the browser

   browser/index
   browser/guide
   browser/how-it-works
   browser/demos
   browser/api
   browser/development

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
   :caption: Guides

   how_to/index
   how_to/create_pipelines
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
   :maxdepth: 1
   :hidden:
   :caption: Work with Meetecho

   work_with_meetecho

|version-badge|

Juturna
=======

Juturna is a Python library for real-time pipelines of audio, video and data.
You write the processing steps as nodes, describe how they connect in a JSON
file, and Juturna runs the graph: every node on its own worker thread,
with messages frozen on the way out so several nodes can read the same
payload without copying it. The same configuration runs in one process, with a node
moved to another machine, behind an HTTP service, or in a browser tab.

Quick start
-----------

Install Juturna (Python 3.12 or newer):

.. code-block:: console

    $ pip install juturna

A pipeline is a list of nodes and the links between them:

.. code-block:: json

    {
      "version": "3.0.0",
      "pipeline": {
        "name": "first_pipeline",
        "id": "first_pipeline_01",
        "folder": "./run",
        "nodes": [
          { "name": "ticker", "type": "contrib.tutorial.nodes.Ticker",
            "configuration": { "text": "juturna says hi" } },
          { "name": "shouter", "type": "contrib.tutorial.nodes.Shouter",
            "configuration": {} },
          { "name": "printer", "type": "contrib.tutorial.nodes.Printer",
            "configuration": {} }
        ],
        "links": [
          { "from": "ticker", "to": "shouter" },
          { "from": "shouter", "to": "printer" }
        ]
      }
    }

Check it and run it:

.. code-block:: console

    $ python -m juturna validate --config pipeline.json
    $ python -m juturna launch --config pipeline.json --auto --timeout 5

The three nodes are yours to write: the :ref:`tutorial <tutorial>` builds
them in about ten minutes.

Where a pipeline runs
---------------------

.. grid:: 1 2 2 2
    :gutter: 3

    .. grid-item-card:: In one process
        :link: tutorial
        :link-type: ref

        Every node runs in a thread of the same Python process. The default,
        and where every pipeline starts.

    .. grid-item-card:: With a node on another machine
        :link: how_to/remotise_node
        :link-type: doc

        Move one heavy node, such as a model on a GPU, to a remote service;
        the rest of the pipeline does not change.

    .. grid-item-card:: Behind an HTTP service
        :link: how_to/serve_pipelines
        :link-type: doc

        Create, start and stop pipelines from other programs through a REST
        API protected by a token.

    .. grid-item-card:: In a browser tab
        :link: browser/index
        :link-type: doc

        Run the pipeline in Pyodide Web Workers, next to the camera and the
        microphone of the page, with nothing installed on the user's machine.

Nodes ready to use, such as RTP audio and video sources, transcription,
voice activity detection, object detection and notifiers, are in the
:doc:`node catalog <catalog/nodes/overview>` and install with
``pip install juturna-nodes``. Coming
from Juturna 2.x? Start from the :ref:`migration guide <migrate_from_2>`.

From the team behind Janus®
---------------------------

Juturna is brewed by `Meetecho <https://www.meetecho.com/>`_, the team
behind the Janus® WebRTC server, hacking on real-time media since 2009.
Taking a pipeline to production? We write the nodes you are missing, tune
performance, and offer consulting and support.

.. button-link:: https://www.meetecho.com/
    :color: primary

    Ping the maintainers

Juturna is open source under the MIT license: the code is on
`GitHub <https://github.com/meetecho/juturna>`_, and the
`contributing guidelines <https://github.com/meetecho/juturna/blob/main/CONTRIBUTING.md>`_
explain how to propose a change.
