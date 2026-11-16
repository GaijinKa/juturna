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

.. include:: /_includes/about_example.rst

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

Save this as ``assistant.json``:

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
            "configuration": {}
          },
          {
            "name": "llm",
            "type": "PrompterOllama",
            "configuration": { "model_name": "qwen2.5:1.5b" }
          },
          {
            "name": "tts",
            "type": "SynthesizerSherpa",
            "configuration": {}
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
stop the pipeline, and the microphone misses the presses meant for it.
``--log-level WARNING`` keeps the pipeline logs out of the way.

The microphone only sends audio between the two presses of Enter, so the
assistant does not hear itself through the speaker. When you stop talking,
it sends a second of silence, and the transcriber closes the sentence at
once. You see the final text of each question only, never partial guesses.

How long it takes
-----------------

After the second Enter, the answer needs the time of the language model and
of the voice. On a laptop CPU, measured on recorded questions:

- about 0.5 seconds for ``qwen2.5:1.5b`` to answer (0.46 s median over 60
  questions);
- about 1 second to synthesise a one-sentence answer, with the default
  2 threads.

``PrompterOllama`` and ``SynthesizerSherpa`` add their own time to the
``timers`` of each message: set ``"auto_dump": true`` on a node to find them
in the JSON files of its folder.

Choose a model
--------------

Any model served by Ollama works: pull it and change ``model_name``, nothing
else in the pipeline changes. Larger models answer more reliably, and take
longer and more memory for each answer. On 20 short questions asked three
times each, on CPU:

- ``qwen2.5:0.5b`` answered 44 of 60 correctly, in 0.28 s (median);
- ``qwen2.5:1.5b``, the default of ``PrompterOllama``, answered 55 of 60
  correctly, in 0.46 s (median).

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

Sizes and licenses are those listed by the Ollama registry; only the two
``qwen2.5`` models above have been measured. Check the license of the model you pick
before shipping it in a product.

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

Plug it into a real audio stream
--------------------------------

The microphone is for trying the assistant on your desk. On a server there is
no microphone and no speaker, but there is audio coming over the network: a
media server such as Janus or Asterisk can send the audio of a call as an RTP
stream. The pipeline stays the same, you change two nodes in the JSON:
``MicSource`` becomes ``AudioRtp``, which receives the stream, and
``SpeakerSink`` becomes ``AudioWriter``, which writes the answers to a file.

``AudioRtp`` reads the stream with PyAV, so add the ``av`` group:

.. code-block:: console

    (.venv) $ pip install "juturna-nodes[av]"

Replace the ``question`` and ``answer`` nodes of ``assistant.json`` with
these two:

.. code-block:: json

    [
      {
        "name": "question",
        "type": "AudioRtp",
        "configuration": {
          "port": 5004,
          "payload_type": 0,
          "encoding_clock_chan": "PCMU/8000",
          "resampler_format": "flt",
          "block_size": 1
        }
      },
      {
        "name": "answer",
        "type": "AudioWriter",
        "configuration": { "file_name": "answer.wav" }
      }
    ]

The node listens on ``127.0.0.1:5004`` (``host`` and ``port``) for G.711
μ-law audio at 8 kHz, payload type 0: the codec of telephone calls. It hands
the transcriber blocks of 1 second. The node pages tell the arguments and the
message formats of the two nodes: :ref:`AudioRtp <node-audio-rtp>`,
:ref:`AudioWriter <node-audio-writer>`.

Start the pipeline first, this time with the logs on, and wait for the line
that says it is running:

.. code-block:: console

    (.venv) $ python -m juturna launch --config assistant.json --auto \
                                       --timeout 60 --log-level INFO
    ...
    ... | INFO     | jt.voice_assistant      | pipe started

If the stream starts before the pipeline, its first packets are lost without
an error. If the log repeats ``source unavailable`` every 2 seconds, another
process holds port 5004: find it with ``ss -lunp | grep 5004``, or pick
another port, both in ``port`` and in the ``rtp://`` address of the ffmpeg
command below. The node keeps trying, and starts receiving as soon as the
port is free. From another terminal, send a recorded question as an RTP stream,
in real time, with ffmpeg:

.. code-block:: console

    $ ffmpeg -i question.wav -af "apad=pad_dur=2,arealtime" \
             -ac 1 -ar 8000 -c:a pcm_mulaw -f rtp rtp://127.0.0.1:5004

The question is transcribed and answered as before, and the answer is in
``./run/answer/answer.wav``.

``apad`` adds 2 seconds of silence at the end. The transcriber closes a
sentence only after 0.8 seconds of silence, and a stream that just ends, like
a call that hangs up, does not reliably give it that much: without the
padding, the last sentence waits until the pipeline stops, and is answered
only then. Juturna does not yet tell the
nodes that a stream has ended; it is on the roadmap.

From demo to production: guardrails
-----------------------------------

The demo shows what the pipeline can do, not how well. On a laptop, with 20
synthetic questions asked three times each:

- the transcriber misheard 6 questions out of 20, mostly as homophones
  ("too" for "two", "for" for "four", "heart" for "hot"), and most of the
  wrong answers start there;
- ``qwen2.5:0.5b`` got simple facts wrong (Florence as the capital of Italy,
  Mercury as the red planet); ``qwen2.5:1.5b``, with a system prompt that
  asks for numbers in words, answered 55 of 60 correctly;
- the lexicon of the Kitten voice has no digits, so "100" is not spoken at
  all; asking the model for numbers in words halves the problem, but does not
  solve it.

Each fix is a node you put between two others, or on a new branch, without
touching the rest of the pipeline. None of the nodes below exists yet: they
are the steps a production assistant would add.

.. list-table::
    :header-rows: 1
    :widths: 30 40 30

    * - Guardrail
      - What it solves
      - Where it goes
    * - Text normalisation
      - Numbers, acronyms and symbols the voice cannot read
      - Between ``llm`` and ``tts``
    * - Transcript check
      - Empty, very short or unlikely questions: ask to repeat instead of
        answering (the transcriber gives no confidence score today)
      - Between ``stt`` and ``llm``, with a branch to ``tts`` for the
        "please repeat"
    * - Answer filter
      - Answers that are too long, unsafe or off topic
      - Between ``llm`` and ``tts``
    * - Grounding on your data
      - Answers from your documents instead of what the model remembers
        (retrieval-augmented generation)
      - Between ``stt`` and ``llm``, adding the retrieved text to the
        question
    * - Fallback answer
      - Ollama slow or down: today ``PrompterOllama`` logs the error and
        drops the question, so the user hears nothing
      - Between ``llm`` and ``tts``, also fed by ``stt``: it passes the
        answer on, or says "sorry, try again" when the answer is late
    * - Echo cancellation and barge-in
      - Hands-free use without push-to-talk: the microphone hears the
        speaker, and the user wants to interrupt a long answer
      - Between ``question`` and ``stt``. The speaker signal it needs comes
        from the audio device: a link from ``tts`` would close a loop, and
        ``validate`` rejects graphs with cycles

To see where the time goes before and after each change, turn on telemetry:
it records when each node receives and transmits a message, which gives the
latency of every node. :doc:`observe` shows how to turn it on and what the
records hold.
