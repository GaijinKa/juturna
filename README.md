# Juturna – Python framework for real-time AI pipelines
<p align="center"><img src="https://raw.githubusercontent.com/meetecho/juturna/main/docs/source/_static/img/logo_dark_alt.svg" width="30%">
<br>
<a href="https://pypi.org/project/juturna/"><img alt="PyPI juturna" src="https://img.shields.io/pypi/v/juturna?style=for-the-badge&amp;label=juturna"></a>
<a href="https://pypi.org/project/juturna-nodes/"><img alt="PyPI juturna-nodes" src="https://img.shields.io/pypi/v/juturna-nodes?style=for-the-badge&amp;label=juturna-nodes"></a>
<a href="https://pypi.org/project/juturna/"><img alt="Python versions" src="https://img.shields.io/pypi/pyversions/juturna?style=for-the-badge"></a>
<a href="https://github.com/meetecho/juturna/actions/workflows/unit-tests.yml"><img alt="Unit tests" src="https://img.shields.io/github/actions/workflow/status/meetecho/juturna/unit-tests.yml?branch=main&amp;style=for-the-badge&amp;label=tests"></a>
<a href="https://github.com/meetecho/juturna/actions/workflows/gh-pages.yml"><img alt="Docs" src="https://img.shields.io/github/actions/workflow/status/meetecho/juturna/gh-pages.yml?branch=main&amp;style=for-the-badge&amp;label=docs"></a>
<a href="https://github.com/meetecho/juturna/blob/main/LICENSE"><img alt="License MIT" src="https://img.shields.io/github/license/meetecho/juturna?style=for-the-badge"></a>
<a href="https://github.com/astral-sh/ruff"><img alt="Ruff" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&amp;style=for-the-badge"></a>
<a href="https://www.meetecho.com/en/?utm_source=github-readme&amp;utm_medium=docs&amp;utm_campaign=juturna3"><img alt="By Meetecho" src="https://img.shields.io/badge/by-Meetecho-1a6dad?style=for-the-badge"></a>
<br>
<a href="https://github.com/meetecho/juturna-browser"><img alt="juturna-browser on GitHub" src="https://img.shields.io/badge/github-juturna--browser-181717?style=for-the-badge&amp;logo=github"></a>
<a href="https://meetecho.github.io/juturna/browser/demos.html"><img alt="Browser demos" src="https://img.shields.io/badge/browser-demos-1a6dad?style=for-the-badge"></a>
</p>

## Important to know
Juturna is actively evolving with exciting new features and improvements being
added regularly. We're using semantic versioning to clearly communicate any
breaking changes between releases, so you can upgrade with confidence.

## At a glance

**Juturna** is a Python framework for **real-time AI pipelines** on audio,
video and data, built for fast prototyping that doesn't stop at the
prototype: a JSON file and a few Python nodes give you a working pipeline in
minutes, and the same pipeline then runs behind an HTTP service, with its
heaviest nodes on other machines, without rewriting its nodes.

Among its many features, there are a few keypoints to highlight about Juturna:

* **Real-Time Streaming:** continuously process audio, video and
  arbitrary data streams
* **Modularity:** create your own nodes and share them as Python packages
* **Composable workloads:** design pipelines to solve complex tasks in
  minutes
* **Parallelism & Batching:** parallel, non-blocking execution for high
  throughput
* **Observability:** built-in logging and metrics support

## Quick start

> **About this example.** A minimal example: it shows how nodes compose into
> a pipeline that does something real, in a few minutes. Its limits are
> deliberate: it needs no GPU and uses small models, and has no guardrails or
> hardening, so its quality and latency are not those of a tuned deployment.
> To adapt it, follow the [guides](https://meetecho.github.io/juturna/how_to/index.html);
> to extend it, pick nodes from the
> [node catalogue](https://meetecho.github.io/juturna/catalog/nodes/overview.html);
> to take it to production, with tuned performance, hardware sized to the
> workload and scaling,
> [work with Meetecho](https://meetecho.github.io/juturna/work_with_meetecho.html).

Transcribe an audio file: Juturna reads it in blocks, a voice activity
detector cuts it into speech segments, Whisper transcribes them and the
text is printed on the terminal. Juturna needs Python 3.12 or newer.

```bash
pip install juturna "juturna-nodes[av,audio-ml]" \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.org/simple
```

The `audio-ml` group pulls in PyTorch. On Linux, the PyTorch wheels on PyPI
pull in the CUDA libraries: the two index options install the CPU-only build,
and the whole environment takes about 1.4 GB. With uv, add
`--index-strategy unsafe-best-match`:

```bash
uv pip install juturna "juturna-nodes[av,audio-ml]" \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.org/simple \
    --index-strategy unsafe-best-match
```

On macOS and Windows the PyTorch wheels on PyPI carry no CUDA libraries, so
`pip install juturna "juturna-nodes[av,audio-ml]"` is enough.

A pipeline is a JSON file that lists nodes and the links between them. Save
this as `pipeline.json`, and point `file_source` to an audio file in English
(any format PyAV can read):

```json
{
  "version": "3.0.0",
  "pipeline": {
    "name": "transcribe_file",
    "id": "transcribe_file_01",
    "folder": "./run",
    "nodes": [
      { "name": "audio", "type": "AudioFile",
        "configuration": { "file_source": "sample.wav", "block_size": 2 } },
      { "name": "vad", "type": "VadSilero",
        "configuration": { "min_silence_duration_ms": 500 } },
      { "name": "whisper", "type": "TranscriberWhisper",
        "configuration": { "model_name": "tiny", "only_local": false,
                           "device": "cpu" } },
      { "name": "console", "type": "NotifierConsole", "configuration": {} }
    ],
    "links": [
      { "from": "audio", "to": "vad" },
      { "from": "vad", "to": "whisper" },
      { "from": "whisper", "to": "console" }
    ]
  }
}
```

Check it, then run it: press enter to start, and again to stop once the
file is done.

```bash
python -m juturna validate --config pipeline.json
python -m juturna launch --config pipeline.json
```

The text comes out as lines like `[whisper] <the transcribed text>`.
Whisper transcribes its last few blocks of speech every time a new one
arrives, so a sentence grows line after line until a whole block without
speech starts the next one. `only_local: false` lets Whisper download the model on the first run,
and `device: cpu` runs it without a GPU.

The documentation has more examples, a tutorial that writes your first nodes,
and a guide to upgrade from Juturna 2.x.

Documentation: [https://meetecho.github.io/juturna/index.html](https://meetecho.github.io/juturna/index.html)

Contribute: [https://github.com/meetecho/juturna/blob/main/CONTRIBUTING.md](https://github.com/meetecho/juturna/blob/main/CONTRIBUTING.md)

Meetecho: [https://www.meetecho.com/en/](https://www.meetecho.com/en/?utm_source=github-readme&utm_medium=docs&utm_campaign=juturna3)

## Contributing

We are so glad you decided to contribute! We truly value your time and help in
making Juturna better, and look forward to every single PR, whether you are
fixing typos, proposing the next big feature, or extending the documentation.

To make sure we’re all on the same page and to get your changes merged as
quickly as possible, please take a peek at our
[`CONTRIBUTING.md`](https://github.com/meetecho/juturna/blob/main/CONTRIBUTING.md)
guide. It covers the essentials, including:

* branching & PR workflow
* code style & linting
* issue triage (TBD)
* issue & PR templates and a Code of Conduct are provided (TBD)
* signing CRA

If you are not sure where to start, feel free to open an issue to discuss your
ideas first. We’re happy to help guide you through the process!

## Changelog

All notable changes are documented in
[`CHANGELOG.md`](https://github.com/meetecho/juturna/blob/main/CHANGELOG.md) - we
follow [Semantic Versioning](https://semver.org), so you'll always know how
exactly updates affect your setup.

## License

Distributed under the **MIT License**. See [LICENSE](https://github.com/meetecho/juturna/blob/main/LICENSE) for details.
