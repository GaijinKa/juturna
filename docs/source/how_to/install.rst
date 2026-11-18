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
- ``onnx`` |next-release|: ONNX Runtime, for ``DetectorYolox``
- ``sherpa`` |next-release|: sherpa-onnx, for ``TranscriberSherpa`` and
  ``SynthesizerSherpa``
- ``sound`` |next-release|: sounddevice, for ``MicSource`` and ``SpeakerSink``; on Linux it
  also needs PortAudio from the system (``libportaudio2``)
- ``warp``: the ``warp`` group of Juturna, for the ``Warp`` node
- ``all``: every group above

The groups marked |next-release| come with the next juturna-nodes release:
version 0.1.0, the one on PyPI today, does not have them.

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

Other groups hold the development dependencies:

- ``doc``: Sphinx and what is needed to build this documentation
- ``dev``: pre-commit hooks and security checks
- ``lint``: ``ruff``
- ``test``: ``pytest`` and the testing packages

Three groups collect the others:

- ``full`` installs ``httpwrapper``, ``pipebuilder`` and ``warp``
- ``dev_full`` installs ``doc``, ``dev``, ``lint`` and ``test``
- ``all`` installs ``full`` and ``dev_full``

Build the documentation
-----------------------

Install Juturna with the ``doc`` group, then from the repository folder:

.. code-block:: console

    (.venv) $ cd docs && sphinx-build -b html ./source ./build/html

While writing, ``sphinx-autobuild`` (in the same group) rebuilds the pages
whenever a file in ``source`` changes:

.. code-block:: console

    (.venv) $ cd docs
    (.venv) $ sphinx-autobuild ./source ./build/html

Run the tests
-------------

Install Juturna with the ``test`` and ``full`` groups, then from the
repository folder:

.. code-block:: console

    (.venv) $ pytest
