.. _rationale:

Why Juturna
===========

Juturna is a Python framework for real-time AI pipelines on audio, video and
data, built for fast prototyping that doesn't stop at the prototype. Data
enters a source node, crosses the processing nodes and leaves through a sink,
while every node works on its own. This page lists the choices behind it,
and where each one is documented.

From spike to production
------------------------

A JSON file and a few nodes give you a working pipeline in minutes: the
:doc:`quick start </index>` transcribes an audio file. The same file then runs
behind an HTTP service with ``python -m juturna serve``
(:doc:`/how_to/serve_pipelines`), and moving its heaviest nodes to other
machines only adds their address to the configuration
(:doc:`/how_to/remotise_node`): the nodes are not rewritten. See
:doc:`where_it_runs`. Releases follow semantic versioning.

.. container:: jt-figure

   .. raw:: html
      :file: ../diagrams/spike_to_production.svg

   **Figure 1.** One ``pipeline.json`` from a laptop to production, each step adding one thing (``launch``, ``serve`` and ``remotize`` run as ``python -m juturna <command>``); the browser edition is a separate path.

Pipelines also run in a browser tab, on Pyodide, between ``BrowserInput`` and
``BrowserOutput`` and with nodes that work there: see :doc:`/browser/index`.

A pipeline is a JSON file
-------------------------

A pipeline is a configuration file that lists nodes and the links between
them. Juturna checks that the links form a directed acyclic graph, builds the
nodes and starts them, sinks first. ``python -m juturna validate`` checks a
file before it runs. See :doc:`pipelines` and :doc:`/reference/configuration`.

A node is a Python class
------------------------

A node is a plain Python class: its logic is one ``update()`` method that
receives a message and transmits new ones. Sources, processing nodes and
sinks are the same type, and a node package is an ordinary Python package
(``python -m juturna stub`` writes the skeleton). See :doc:`nodes` and
:doc:`/how_to/create_nodes`.

Messages are shared, not copied
-------------------------------

A node freezes a message when it transmits it, and every destination gets the
same frozen object: a frame sent to three nodes is not copied three times. A
node that needs a modified version asks for a copy. See :doc:`messages`.

Heavy nodes can run elsewhere
-----------------------------

A node that needs a GPU, or dependencies that clash with the rest of the
pipeline, can run as a remote service started with ``juturna remotize``. The
pipeline marks it as ``warped`` and gives the address of the service; the
other nodes do not change. See :doc:`remote` and :doc:`/how_to/remotise_node`.

A small core
------------

The core library depends on ``numpy`` only, and is released under the MIT
license. Media, models and protocols live in the nodes, and the official
ones are in the ``juturna-nodes`` package, where each heavy dependency sits
behind an optional group: you install what your pipeline uses. See
:doc:`/how_to/install`.
