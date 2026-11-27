# Juturna – Python framework for real-time AI pipelines
<p align="center"><img src="https://raw.githubusercontent.com/meetecho/juturna/main/docs/source/_static/img/juturna_logo.png" width="30%"></p>

<table align="center">
  <tr><th>juturna</th><td>
    <a href="https://pypi.org/project/juturna/"><img alt="PyPI juturna" src="https://img.shields.io/pypi/v/juturna?style=for-the-badge&amp;label=juturna"></a>
    <a href="https://pypi.org/project/juturna/"><img alt="Python versions" src="https://img.shields.io/pypi/pyversions/juturna?style=for-the-badge"></a>
    <a href="https://github.com/meetecho/juturna/actions/workflows/unit-tests.yml"><img alt="Unit tests" src="https://img.shields.io/github/actions/workflow/status/meetecho/juturna/unit-tests.yml?branch=main&amp;style=for-the-badge&amp;label=tests"></a>
    <a href="https://github.com/meetecho/juturna/actions/workflows/gh-pages.yml"><img alt="Docs" src="https://img.shields.io/github/actions/workflow/status/meetecho/juturna/gh-pages.yml?branch=main&amp;style=for-the-badge&amp;label=docs"></a>
    <a href="https://github.com/meetecho/juturna/blob/main/LICENSE"><img alt="License MIT" src="https://img.shields.io/github/license/meetecho/juturna?style=for-the-badge"></a>
    <a href="https://github.com/astral-sh/ruff"><img alt="Ruff" src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&amp;style=for-the-badge"></a>
    <a href="https://www.meetecho.com/en/?utm_source=github-readme&amp;utm_medium=docs&amp;utm_campaign=juturna3"><img alt="By Meetecho" src="https://img.shields.io/badge/by-Meetecho-1a6dad?style=for-the-badge"></a>
  </td></tr>
  <tr><th>juturna-nodes</th><td>
    <a href="https://pypi.org/project/juturna-nodes/"><img alt="PyPI juturna-nodes" src="https://img.shields.io/pypi/v/juturna-nodes?style=for-the-badge&amp;label=juturna-nodes"></a>
  </td></tr>
  <tr><th>juturna-browser</th><td>
    <a href="https://github.com/meetecho/juturna-browser"><img alt="juturna-browser release" src="https://img.shields.io/github/v/tag/meetecho/juturna-browser?style=for-the-badge&amp;label=juturna-browser"></a>
    <a href="https://meetecho.github.io/juturna/browser/demos.html"><img alt="Browser demos" src="https://img.shields.io/badge/browser-demos-1a6dad?style=for-the-badge"></a>
  </td></tr>
</table>

## Stability
Juturna follows [Semantic Versioning](https://semver.org): breaking changes
come only with a new major version, and are listed in the
[changelog](https://github.com/meetecho/juturna/blob/main/CHANGELOG.md). The
versions that get security fixes are in the
[security policy](https://github.com/meetecho/juturna/blob/main/SECURITY.md#2-supported-versions).

## At a glance

**Juturna** is a Python framework for **real-time AI pipelines** on audio,
video and data, built for fast prototyping that doesn't stop at the
prototype: a JSON file and a few Python nodes give you a working pipeline in
minutes, and the same pipeline then runs behind an HTTP service, with its
heaviest nodes on other machines, without rewriting its nodes.

Highlights:

* **Real-Time Streaming:** continuously process audio, video and
  arbitrary data streams
* **Modularity:** create your own nodes and share them as Python packages
* **Composable workloads:** design pipelines to solve complex tasks in
  minutes
* **Concurrency:** every node runs on workers of its own, fed by a bounded
  queue: threads by default, Web Workers in the browser
* **Observability:** a logger and failure counters for every node, and
  optional telemetry of every message received and transmitted

## Quick start

> A minimal example: no GPU, small models, not tuned for quality or latency.
> For production, [work with Meetecho](https://meetecho.github.io/juturna/work_with_meetecho.html).

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

We are glad you want to contribute, whether with a typo fix, a new feature
or more documentation.
[`CONTRIBUTING.md`](https://github.com/meetecho/juturna/blob/main/CONTRIBUTING.md)
covers the branch and PR workflow, code style, commit messages and the checks
CI runs.

Bugs and feature requests have their
[issue templates](https://github.com/meetecho/juturna/tree/main/.github/ISSUE_TEMPLATE),
and pull requests a
[template](https://github.com/meetecho/juturna/blob/main/.github/pull_request_template.md)
of their own. Everyone taking part follows the
[Code of Conduct](https://github.com/meetecho/juturna/blob/main/CODE_OF_CONDUCT.md).
To report a vulnerability, follow the
[security policy](https://github.com/meetecho/juturna/blob/main/SECURITY.md).

If you are not sure where to start, feel free to open an issue to discuss your
ideas first. We’re happy to help guide you through the process!

## License

Distributed under the **MIT License**. See [LICENSE](https://github.com/meetecho/juturna/blob/main/LICENSE) for details.
