# Juturna – Agent Instructions

**Juturna** is a real-time data pipeline framework for multimedia and AI workloads.
Pipelines are composed of typed **nodes** (source → proc → sink) wired via JSON configuration files.

Docs: https://meetecho.github.io/juturna/index.html

---

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -U -e ".[dev_full]"

# Install both pre-commit hook types (required for linting + commit-msg validation)
pre-commit install && pre-commit install --hook-type commit-msg
```

Optional feature groups: `httpwrapper` (FastAPI), `pipebuilder` (interactive CLI), `warp` (gRPC remote nodes).

---

## Commands

| Task | Command |
|------|---------|
| Run tests | `pytest` |
| Lint / format | `ruff check . && ruff format .` |
| Launch a pipeline | `python -m juturna launch -c <config.json>` |
| Validate a pipeline config | `python -m juturna validate -c <config.json>` |
| Create node skeleton | `python -m juturna stub -n <name> -t <type> -d ./plugins/nodes` |
| Interactive pipeline builder | `python -m juturna create -p ./plugins/nodes` |

---

## Architecture

### Nodes

Every node inherits from `Node[T_Input, T_Output]` in `juturna/components/_node.py`.

Override these lifecycle methods:

| Method | When |
|--------|------|
| `configure()` | Called once after instantiation |
| `warmup()` | Called before pipeline start; open connections here |
| `start()` | Called to start threads — always call `super().start()` last |
| `stop()` | Called to stop threads — always call `super().stop()` last |
| `destroy()` | Release resources (close connections, files, etc.) |
| `update(message)` | Receives each inbound `Message[T_Input]`; call `self.put_to_destinations(msg)` to forward |
| `set_on_config(prop, value)` | Hot-swap a node property at runtime |

For source nodes, call `self.register_source(callable, sleep_interval)` inside `warmup()` instead of using `update()`.

### Plugin node layout

```
plugins/nodes/<type>/_<node_name>/
    <node_name>.py     # class named CamelCase of node_name
    config.toml        # [arguments] and [meta] sections
    requirements.txt   # pip dependencies
    README.md          # recommended
```

- Folder **must** start with `_` (e.g. `_red_cat_detector`)
- Class name is CamelCase of the folder name without the leading `_`
- `config.toml` `[arguments]` keys become `__init__` kwargs (merged with pipeline JSON config)
- Node types are directories: `source`, `proc`, `sink` (custom types are allowed)

### Pipeline JSON config

```json
{
  "version": "2.1.1",
  "plugins": ["./plugins"],
  "pipeline": {
    "name": "my_pipeline",
    "id": "unique-id",
    "folder": "./running_pipelines",
    "nodes": [
      { "name": "my_node", "type": "proc", "mark": "node_folder_name", "configuration": {} }
    ],
    "links": [
      { "from": "node_a", "to": "node_b" }
    ]
  }
}
```

- `mark` = folder name without `_` prefix (matches `plugins/nodes/<type>/_<mark>/`)
- `configuration` overrides defaults from the node's `config.toml`
- Env vars in config values use the `JT_` prefix; they are resolved at build time

### Key modules

| Path | Purpose |
|------|---------|
| `juturna/components/_node.py` | Base `Node` class |
| `juturna/components/_pipeline.py` | Pipeline lifecycle |
| `juturna/components/_node_builder/` | Node instantiation / discovery |
| `juturna/payloads/_payloads.py` | Built-in payload types |
| `juturna/names/` | `ComponentStatus`, `PipelineStatus` enums |
| `plugins/` | Bundled plugin nodes (source/proc/sink) |
| `tests/test_plugins/` | Minimal nodes used only in tests |

---

## Code conventions

- Python 3.12+ — use `type | None` union syntax, generics with `[]`
- Line length: **80**, indent: **4 spaces**, quotes: **single** (enforced by `ruff.toml`)
- `ruff` rules in scope: `E`, `W`, `F`, `B`, `I`, `N`, `UP`, `SIM`, `PTH`
- Loggers: use `jt_logger('name')` from `juturna.utils.log_utils`
- Commit messages follow **Conventional Commits** (`feat:`, `fix:`, `docs:`, etc.)

---

## Testing

Tests live in `tests/`. Test-only plugin nodes are in `tests/test_plugins/`.

```bash
pytest                  # run all tests
pytest tests/test_node.py   # single file
```

Ruff is excluded from `tests/` by `ruff.toml`.

---

## Docs

Source in `docs/source/`. Key reference pages:
- [Node guide](docs/source/explain/nodes.rst)
- [Pipeline guide](docs/source/explain/pipelines.rst)
- [Create nodes how-to](docs/source/how_to/create_nodes.rst)
- [CLI how-to](docs/source/how_to/use_cli.rst)
- [CONTRIBUTING](CONTRIBUTING.md)
