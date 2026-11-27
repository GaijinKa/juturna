Install
=======

Juturna needs Python 3.12 or newer. It is published on the Python Package
Index (`PyPI <https://pypi.org/project/juturna/>`_), so within a virtual
environment:

.. code-block:: console

    $ python3 -m venv .venv
    $ source .venv/bin/activate
    (.venv) $ pip install juturna

This installs the core library: pipelines, the base node class, messages and
the command line tools. Its only dependency is ``numpy``.

To install from the source code instead:

.. code-block:: console

    (.venv) $ git clone https://github.com/meetecho/juturna
    (.venv) $ pip install ./juturna

Ready-made nodes
----------------

The core library ships no nodes. The officially supported ones (audio and
video sources, transcription, detection, notifiers) are in the
`juturna-nodes <https://github.com/meetecho/juturna_nodes>`_ package, which
installs Juturna as a dependency:

.. code-block:: console

    (.venv) $ pip install juturna-nodes

Each node with heavy dependencies has an optional group of
``juturna-nodes`` named after it:

- ``audio-file``, ``audio-rtp``, ``video-rtp``, ``video-capture``: PyAV
- ``mic-source``, ``speaker-sink``: sounddevice; on Linux it also needs
  PortAudio from the system (``libportaudio2``)
- ``transcriber-sherpa``, ``synthesizer-sherpa``: sherpa-onnx
- ``transcriber-whisper``: faster-whisper
- ``vad-silero``: silero-vad, which brings PyTorch
- ``detector-yolo``: ultralytics, which brings PyTorch
- ``detector-yolox``: ONNX Runtime
- ``warp``: the ``warp`` group of Juturna, for the ``Warp`` node

``audio`` and ``video`` install every audio or video node, ``all`` everything:

.. code-block:: console

    (.venv) $ pip install "juturna-nodes[video-capture,detector-yolox]"

Optional groups
---------------

Some features of Juturna need extra packages, collected in optional groups:

- ``httpwrapper``: the pipeline service (``python -m juturna serve``)
- ``pipebuilder``: the interactive pipeline builder (``python -m juturna create``)
- ``warp``: the remote node service (``python -m juturna remotize``)

.. code-block:: console

    # a single group
    (.venv) $ pip install -U 'juturna[httpwrapper]'

    # several groups
    (.venv) $ pip install -U 'juturna[httpwrapper,warp]'

Other groups hold the development dependencies (``doc``, ``dev``, ``lint``,
``test``), and three collect the others: ``full`` installs ``httpwrapper``,
``pipebuilder`` and ``warp``, ``dev_full`` the development groups, ``all``
both. To build this documentation or run the tests, see the
`contributing guide <https://github.com/meetecho/juturna/blob/main/CONTRIBUTING.md>`_.
