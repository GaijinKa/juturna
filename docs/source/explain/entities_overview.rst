Entities overview
=================

Juturna was designed with developers in mind: there are only three entities
to get a good look at, then you are good to go.

- pipelines
- nodes
- messages and payloads

Pipeline
--------

A :ref:`pipeline <explain_pipelines>` builds the nodes, links them and runs
them. The links form a
`DAG <https://en.wikipedia.org/wiki/Directed_acyclic_graph>`_: data enters at
the source nodes, can split into branches and join again, and every branch
ends at a destination of its own.

.. container:: jt-figure

   .. raw:: html
      :file: ../diagrams/pipeline.svg

   **Figure 1.** A pipeline with one source node, highlighted. Data can split into branches and branches can join; each branch ends at its own destination.

A pipeline can have several source nodes, for data that comes from
independent places, such as the audio and the video of the same stream on two
RTP ports.

.. container:: jt-figure

   .. raw:: html
      :file: ../diagrams/pipeline_multisource.svg

   **Figure 2.** Two source nodes in one pipeline. ``stt`` feeds both ``translate`` and ``subtitles``, so the audio branch joins the video branch.

Node
----

A :ref:`node <explain_nodes>` receives data, processes it, and sends the
result to all its downstream nodes. Depending on where it sits, a node is
one of three kinds.

**Source nodes** bring data into the pipeline: they read a stream, a file, a
database or a request, or generate data on their own.

.. container:: jt-figure

   .. raw:: html
      :file: ../diagrams/node_source_overview.svg

   **Figure 3.** A source node: ``_source()`` brings data in, ``update()`` processes it and transmits it to every downstream node.

**Processing nodes** (proc nodes, if you are in a hurry) sit in the middle,
with any number of inputs and outputs: in figure 2, ``stt`` has one input
and two outputs, ``subtitles`` two inputs and one output.

.. container:: jt-figure

   .. raw:: html
      :file: ../diagrams/node_proc_overview.svg

   **Figure 4.** A processing node: messages from every upstream node reach ``update()`` one at a time; what has to wait for another input stays in the node state.

**Sink nodes** deliver what they receive outside the pipeline: an HTTP
endpoint, a websocket, a database, an RTP stream.

.. container:: jt-figure

   .. raw:: html
      :file: ../diagrams/node_sink_overview.svg

   **Figure 5.** A sink node: ``update()`` delivers what it receives to a destination outside the pipeline.

The core library ships no nodes: it finds the ones installed in your
environment. To get the nodes a pipeline needs:

#. use the **official nodes** of the ``juturna-nodes`` package, maintained by
   the Juturna team;
#. use **community nodes**, distributed like any other Python package;
#. write your own **custom nodes** (this is the fun solution!).

Messages and payloads
---------------------

Nodes pass data around in :ref:`messages <explain_messages>`. A message is
an envelope with metadata, and its **payload** is the data, of a declared
type: the payload types of a node tell what it expects as input and what it
produces as output.
