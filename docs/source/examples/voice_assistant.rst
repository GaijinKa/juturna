Build a voice assistant
=======================

.. note::

    A minimal example: no GPU, small models, not tuned for quality or latency.
    For production, :doc:`work with Meetecho </work_with_meetecho>`.

This example builds a small assistant you talk to: press Enter, ask a question
in English, press Enter again, and it answers with a synthetic voice.

.. container:: jt-figure

   .. raw:: html
      :file: ../diagrams/voice_assistant_pipeline.svg

   .. raw:: html
      :file: ../diagrams/voice_assistant_pipeline_narrow.svg

   **Figure 1.** The pipeline of this example: the question goes from the microphone to the speaker, and the console prints both the question and the answer.

- ``MicSource`` records from the microphone, between two presses of Enter;
- ``TranscriberSherpa`` turns the question into text;
- ``PrompterOllama`` asks a language model served by Ollama;
- ``SynthesizerSherpa`` speaks the answer;
- ``SpeakerSink`` plays it;
- ``NotifierConsole`` prints the question and the answer on the terminal.

Everything runs on the CPU, without PyTorch. Once the models are downloaded,
nothing leaves the machine: speech recognition, the language model and the
voice all run locally.

Limits
------

The demo shows what the pipeline can do, not how well:

- it needs a microphone and a speaker on the machine that runs the pipeline:
  it does not work over SSH or on a server without audio;
- push-to-talk does not work on Windows, as it waits for Enter with
  ``select`` on the standard input;
- the transcriber mishears homophones ("too" for "two", "for" for "four"),
  and a wrong question gets a wrong answer;
- a small language model gets facts wrong;
- the voice skips the words missing from its pronunciation lexicon, which
  leaves out most names, and the lexicon has no digits, so "100" is not
  spoken at all: asking the model for numbers in words helps, but does not
  solve it.

Install
-------

.. code-block:: console

    (.venv) $ pip install juturna "juturna-nodes[sherpa,sound]"

``sherpa`` brings sherpa-onnx, for speech recognition and synthesis, and
``sound`` brings sounddevice, for the microphone and the speaker. On Linux,
sounddevice also needs PortAudio from the system:

.. code-block:: console

    $ sudo apt install libportaudio2

The language model is served by `Ollama <https://ollama.com>`_. Install it,
then pull the model of the example:

.. code-block:: console

    $ ollama pull qwen2.5:1.5b

Models
------

The speech models need no setup: on the first run, ``TranscriberSherpa`` and
``SynthesizerSherpa`` download them, about 107 MB in all, into
``~/.cache/juturna/models/`` (or under ``$XDG_CACHE_HOME``). The two models
come from Hugging Face at a pinned revision, the lexicon from a sherpa-onnx
release; every download is checked against its size and SHA-256, and later
runs reuse the files already there.

.. list-table::
    :header-rows: 1

    * - Model
      - Used by
      - Size
      - License
    * - English streaming zipformer
      - ``TranscriberSherpa``
      - 73 MB
      - Apache-2.0
    * - Kitten nano int8
      - ``SynthesizerSherpa``
      - 28 MB
      - Apache-2.0
    * - Pronunciation lexicon ``lexicon-en-us.txt``
      - ``SynthesizerSherpa``
      - 6.3 MB
      - Not stated upstream, see below
    * - ``qwen2.5:1.5b``
      - ``PrompterOllama``
      - 986 MB
      - Apache-2.0

The lexicon needs a word of caution. sherpa-onnx publishes it without a
license. Its header lists CMUdict (BSD) and ``en_list``, the English word
list of espeak-ng (GPL-3.0), among its sources: the prudent reading is to
treat it as GPL-3.0 if you redistribute it. The node downloads it on your machine, and
Juturna does not ship it.

To use models you already have, point the ``model_dir`` argument of the two
sherpa nodes to their folders, and ``lexicon`` to the lexicon file.

Write the configuration
-----------------------

Save this as ``pipeline.json``:

.. literalinclude:: ../../../examples/voice_assistant/pipeline.json
    :language: json

``stt`` and ``llm`` both send their messages to ``console`` as well: a node
can feed any number of others, and each gets the same message without a
copy. ``MicSource`` and ``SpeakerSink`` use the default devices of the
system; ``python -m sounddevice`` lists the others, to pick with their
``device`` argument.

Run it
------

Run the pipeline in a terminal:

.. code-block:: console

    (.venv) $ python -m juturna validate --config pipeline.json
    (.venv) $ python -m juturna launch --config pipeline.json --auto \
                                       --timeout 120 --log-level WARNING
    [question] press Enter to talk
    [question] listening, press Enter to stop
    [question] stopped, press Enter to talk
    [stt] what is the capital of italy
    [llm] The capital of Italy is Rome.

Press Enter, ask your question, press Enter again: the transcribed question
and the answer appear on the terminal, and the answer plays on the speaker.
Ask as many questions as you like; after ``--timeout`` seconds the pipeline
stops.

``--auto`` matters: without it, the launcher itself reads Enter to start and
stop the pipeline, and the microphone misses the presses meant for it.
``--log-level WARNING`` keeps the pipeline logs out of the way.

The microphone only sends audio between the two presses of Enter, so the
assistant does not hear itself through the speaker. When you stop talking,
it sends a second of silence, and the transcriber closes the sentence at
once. You see the final text of each question only, never partial guesses.

After the second Enter, the answer needs the time of the language model,
which returns the whole answer at once as the node does not stream, and of
the voice. ``PrompterOllama`` and ``SynthesizerSherpa`` add their own time
to the ``timers`` of each message: set ``"auto_dump": true`` on a node to find them
in the JSON files of its folder. For the latency of every node, turn on
telemetry (:doc:`/how_to/observe`).

Choose a model
--------------

Any model served by Ollama works: pull it and change ``model_name``, nothing
else in the pipeline changes. Larger models answer more reliably, and take
longer and more memory for each answer. ``qwen2.5:1.5b`` is the default of
``PrompterOllama``.

.. list-table::
    :header-rows: 1

    * - ``model_name``
      - Download
      - License
    * - ``qwen2.5:0.5b``
      - 398 MB
      - Apache-2.0
    * - ``gemma3:1b``
      - 806 MB
      - Gemma Terms of Use
    * - ``qwen2.5:1.5b``
      - 986 MB
      - Apache-2.0
    * - ``llama3.2:3b``
      - 2.0 GB
      - Llama 3.2 Community License
    * - ``qwen2.5:7b``
      - 4.7 GB
      - Apache-2.0

Sizes and licenses are those listed by the Ollama registry. Check the
license of the model you pick before shipping it in a product.

Each question is sent on its own: the assistant keeps no memory of the
conversation. The ``system_prompt`` argument of ``PrompterOllama`` sets how
it answers: by default in one or two short sentences, with numbers written
as words, because the voice cannot read digits.

The node pages tell the arguments and the message formats of each node:
:ref:`MicSource <node-mic-source>`,
:ref:`TranscriberSherpa <node-transcriber-sherpa>`,
:ref:`PrompterOllama <node-prompter-ollama>`,
:ref:`SynthesizerSherpa <node-synthesizer-sherpa>`,
:ref:`SpeakerSink <node-speaker-sink>`.
