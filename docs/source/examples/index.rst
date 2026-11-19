.. _examples:

Examples
========

Each example is a complete pipeline you can run in a few minutes: an
install command, the configuration file, an input to test it on, and the
output to expect. The configuration files are in the ``examples/`` folder of
the `Juturna repository <https://github.com/meetecho/juturna>`_, and the
pages show them as they are.

.. grid:: 1 2 2 2
    :gutter: 3

    .. grid-item-card:: Build a voice assistant
        :link: voice_assistant
        :link-type: doc

        Ask a question out loud and hear the answer, with speech recognition,
        a language model and a synthetic voice all on your machine.

        .. container:: jt-figure jt-mini

           .. raw:: html
              :file: ../diagrams/voice_assistant_mini.svg

        +++
        CPU · about 1.3 GB · Linux

    .. grid-item-card:: Detect objects in a video
        :link: video_detection
        :link-type: doc

        Find people, cars and 78 more classes in a video, and post an event
        to a webhook when one shows up.

        .. container:: jt-figure jt-mini

           .. raw:: html
              :file: ../diagrams/video_detection_mini.svg

        +++
        CPU · about 280 MB · Linux

What each example needs
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 24 16 26 17 17

   * - Example
     - Extras
     - Download
     - Hardware
     - OS
   * - :doc:`voice_assistant`
     - ``sherpa``, ``sound``; ``av`` for the RTP step
     - about 240 MB of packages, 107 MB of speech models, and the 986 MB
       language model through Ollama
     - CPU, microphone and speaker
     - Linux (tested); no push-to-talk on Windows
   * - :doc:`video_detection`
     - ``av``, ``onnx``
     - about 270 MB of packages, a 3.7 MB model, a 2 MB video
     - CPU
     - Linux (tested)

The download is the size of a fresh virtual environment with the example
installed, plus the model and the test input fetched on the first run.

**Need another pipeline?** Transcribing phone calls from Janus or Asterisk,
reading sensors over MQTT, running on edge devices:
:doc:`work with Meetecho </work_with_meetecho>` and we build it for you.
