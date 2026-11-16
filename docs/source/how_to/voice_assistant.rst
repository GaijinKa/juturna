Build a voice assistant
=======================

This guide builds a small assistant that answers spoken questions with a
synthetic voice. You give it a recorded question, ``question.wav``, and it
writes the spoken answer to ``answer.wav``:

.. code-block:: text

    question.wav ─► stt ─► llm ─► tts ─► answer.wav
                     │      │
                     └──────┴──► console

- ``TranscriberSherpa`` turns the question into text;
- ``PrompterOllama`` asks a language model served by Ollama;
- ``SynthesizerSherpa`` speaks the answer;
- ``AudioWriter`` writes it to a WAV file;
- ``NotifierConsole`` prints the question and the answer on the terminal.

Everything runs on the CPU, without PyTorch. Once the models are downloaded,
nothing leaves the machine: speech recognition, the language model and the
voice all run locally.

Install
-------

.. code-block:: console

    (.venv) $ pip install juturna "juturna-nodes[av,sherpa]"

The two groups bring PyAV, to read audio files, and sherpa-onnx, for speech
recognition and synthesis.

The language model is served by `Ollama <https://ollama.com>`_. Install it,
then pull the default model:

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

Words missing from the lexicon are not spoken, and that includes most names.

Write the configuration
-----------------------

Record a question in English and save it as ``question.wav``: any format and
sampling rate PyAV can read will do, telephone audio at 8 kHz included.
Leave a second of silence at the end, because the transcriber closes a
sentence only after 0.8 seconds without speech.

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
            "type": "AudioFile",
            "configuration": { "file_source": "question.wav", "block_size": 1 }
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
            "type": "AudioWriter",
            "configuration": { "file_name": "answer.wav" }
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
copy.

Run it
------

.. code-block:: console

    (.venv) $ python -m juturna validate --config assistant.json
    (.venv) $ python -m juturna launch --config assistant.json --auto --timeout 20 \
                                  --log-level WARNING
    [stt] what is the capital of italy
    [llm] The capital of Italy is Rome.

``--log-level WARNING`` keeps the pipeline logs out of the way. The
transcriber sends one message per sentence, when the speaker stops: you
see the final text only, never partial guesses. The spoken answer is in
``./run/answer/answer.wav``.

The file source stops at the end of the file, but the other nodes keep
waiting for more, so ``--timeout`` is what ends the run: make it longer than
the question plus a few seconds.

How long it takes
-----------------

On a laptop CPU (Intel Core i7-10850H), the answer is ready about 2 seconds
after the question ends:

- 0.8 seconds of silence, before the transcriber closes the sentence;
- 0.1 to 0.3 seconds for ``qwen2.5:0.5b`` to answer;
- about 1 second to synthesise this one-sentence answer, with the default
  2 threads.

``PrompterOllama`` and ``SynthesizerSherpa`` add their own time to the
``timers`` of each message: set ``"auto_dump": true`` on a node to find them
in the JSON files of its folder.

Choose a model
--------------

Any model served by Ollama works: pull it and change ``model_name``, nothing
else in the pipeline changes. The default is the smallest download, and it
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
:ref:`TranscriberSherpa <node-transcriber-sherpa>`,
:ref:`PrompterOllama <node-prompter-ollama>`,
:ref:`SynthesizerSherpa <node-synthesizer-sherpa>`,
:ref:`AudioWriter <node-audio-writer>`.
