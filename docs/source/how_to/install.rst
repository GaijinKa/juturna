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

Nodes with heavy dependencies sit behind optional groups of
``juturna-nodes``:

- ``av``: PyAV, for ``AudioFile``, ``AudioRtp``, ``VideoCapture`` and
  ``VideoRtp``
- ``audio-ml``: faster-whisper and silero-vad (which brings PyTorch), for
  ``TranscriberWhisper`` and ``VadSilero``
- ``vision``: ultralytics, for ``DetectorYolo``
- ``onnx``: ONNX Runtime, for ``DetectorYolox``
- ``sherpa``: sherpa-onnx, for ``TranscriberSherpa`` and
  ``SynthesizerSherpa``
- ``sound``: sounddevice, for ``MicSource`` and ``SpeakerSink``; on Linux it
  also needs PortAudio from the system (``libportaudio2``)
- ``warp``: the ``warp`` group of Juturna, for the ``Warp`` node
- ``all``: every group above

.. code-block:: console

    (.venv) $ pip install "juturna-nodes[av,onnx]"

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
