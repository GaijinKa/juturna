Build a voice assistant
=======================

This guide builds a small assistant you talk to: press Enter, ask a question
in English, press Enter again, and it answers with a synthetic voice.

.. code-block:: text

    microphone ─► stt ─► llm ─► tts ─► speaker
                   │      │
                   └──────┴──► console

- ``MicSource`` records from the microphone, between two presses of Enter;
- ``TranscriberSherpa`` turns the question into text;
- ``PrompterOllama`` asks a language model served by Ollama;
- ``SynthesizerSherpa`` speaks the answer;
- ``SpeakerSink`` plays it;
- ``NotifierConsole`` prints the question and the answer on the terminal.

Everything runs on the CPU, without PyTorch. Once the models are downloaded,
nothing leaves the machine: speech recognition, the language model and the
voice all run locally.

Before you start
----------------

It is a demo, and it has limits:

- it needs a microphone and a speaker on the machine that runs the pipeline:
  it does not work over SSH or on a server without audio;
- push-to-talk does not work on Windows, as it waits for Enter with
  ``select`` on the standard input;
- speech recognition is not precise, and a small language model gets facts
  wrong;
- the voice skips the words missing from its pronunciation lexicon, which
  includes most names.

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

    $ ollama pull qwen2.5:0.5b

Download the models
-------------------

The sherpa nodes do not download models. Fetch the speech recognition model,
the voice and its pronunciation lexicon into a ``models`` folder:

.. code-block:: console

    $ mkdir models && cd models
    $ curl -LO https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-en-2023-06-26.tar.bz2
    $ tar xjf sherpa-onnx-streaming-zipformer-en-2023-06-26.tar.bz2
    $ curl -LO https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kitten-nano-en-v0_8-int8.tar.bz2
    $ tar xjf kitten-nano-en-v0_8-int8.tar.bz2
    $ curl -LO https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/lexicon-en-us.txt
    $ cd ..

.. list-table::
    :header-rows: 1

    * - Model
      - Used by
      - Size
      - License
    * - English streaming zipformer
      - ``TranscriberSherpa``
      - 68 MB of int8 files
      - Apache-2.0
    * - Kitten nano int8
      - ``SynthesizerSherpa``
      - 29 MB, plus 6 MB of lexicon
      - Apache-2.0
    * - ``qwen2.5:0.5b``
      - ``PrompterOllama``
      - 398 MB
      - Apache-2.0

Write the configuration
-----------------------

Save this as ``assistant.json``, next to the ``models`` folder:

.. code-block:: json

    {
      "version": "3.0.0",
      "pipeline": {
        "name": "voice_assistant",
        "id": "voice_assistant_01",
        "folder": "./run",
        "nodes": [
          {
            "name": "question",
            "type": "MicSource",
            "configuration": { "push_to_talk": true }
          },
          {
            "name": "stt",
            "type": "TranscriberSherpa",
            "configuration": {
              "model_dir": "./models/sherpa-onnx-streaming-zipformer-en-2023-06-26"
            }
          },
          {
            "name": "llm",
            "type": "PrompterOllama",
            "configuration": { "model_name": "qwen2.5:0.5b" }
          },
          {
            "name": "tts",
            "type": "SynthesizerSherpa",
            "configuration": {
              "model_dir": "./models/kitten-nano-en-v0_8-int8",
              "lexicon": "./models/lexicon-en-us.txt"
            }
          },
          {
            "name": "answer",
            "type": "SpeakerSink",
            "configuration": {}
          },
          {
            "name": "console",
            "type": "NotifierConsole",
            "configuration": {}
          }
        ],
        "links": [
          { "from": "question", "to": "stt" },
          { "from": "stt", "to": "llm" },
          { "from": "stt", "to": "console" },
          { "from": "llm", "to": "tts" },
          { "from": "llm", "to": "console" },
          { "from": "tts", "to": "answer" }
        ]
      }
    }

``stt`` and ``llm`` both send their messages to ``console`` as well: a node
can feed any number of others, and each gets the same message without a
copy. ``MicSource`` and ``SpeakerSink`` use the default devices of the
system; ``python -m sounddevice`` lists the others, to pick with their
``device`` argument.

Run it
------

Run the pipeline in a terminal:

.. code-block:: console

    (.venv) $ python -m juturna validate --config assistant.json
    (.venv) $ python -m juturna launch --config assistant.json --auto \
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
stop the pipeline, and the microphone misses the presses meant for it. ``--log-level WARNING``
keeps the pipeline logs out of the way.

The microphone only sends audio between the two presses of Enter, so the
assistant does not hear itself through the speaker. When you stop talking,
it sends a second of silence, and the transcriber closes the sentence at
once. You see the final text of each question only, never partial guesses.

How long it takes
-----------------

After the second Enter, the answer needs the time of the language model and
of the voice. On a laptop CPU (Intel Core i7-10850H), measured on a recorded
question:

- 0.1 to 0.3 seconds for ``qwen2.5:0.5b`` to answer;
- about 1 second to synthesise a one-sentence answer, with the default
  2 threads.

``PrompterOllama`` and ``SynthesizerSherpa`` add their own time to the
``timers`` of each message: set ``"auto_dump": true`` on a node to find them
in the JSON files of its folder.

Choose a model
--------------

Any model served by Ollama works: pull it and change ``model_name``, nothing
else in the pipeline changes. The example uses the smallest download, and it
gets things wrong: in our tests ``qwen2.5:0.5b`` once named Florence as the
capital of Italy. Larger models answer more reliably, and take longer and
more memory for each answer.

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

Sizes and licenses are those listed by the Ollama registry; only
``qwen2.5:0.5b`` has been measured. Check the license of the model you pick
before shipping it in a product.

Each question is sent on its own: the assistant keeps no memory of the
conversation. The ``system_prompt`` argument of ``PrompterOllama`` sets how
it answers, by default in one or two short sentences.

The node pages tell the arguments and the message formats of each node:
:ref:`MicSource <node-mic-source>`,
:ref:`TranscriberSherpa <node-transcriber-sherpa>`,
:ref:`PrompterOllama <node-prompter-ollama>`,
:ref:`SynthesizerSherpa <node-synthesizer-sherpa>`,
:ref:`SpeakerSink <node-speaker-sink>`.
