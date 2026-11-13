"""Copy the node pages of juturna-nodes into the build (the Nodes section)."""

import os
import pathlib
import shutil

import juturna
from sphinx.errors import ConfigError


_SECTIONS = ('nodes', 'contribute')
_INCLUDE_ROOT = '../../../src/'


def _copy_catalog(app, config):
    checkout = os.environ.get('JUTURNA_NODES_DIR')

    if not checkout:
        raise ConfigError(
            'set JUTURNA_NODES_DIR to a juturna-nodes checkout: the node '
            'catalog is built from its pages'
        )

    checkout = pathlib.Path(checkout).resolve()
    src = checkout / 'src'
    target = pathlib.Path(app.srcdir) / 'catalog'
    shutil.rmtree(target, ignore_errors=True)

    for section in _SECTIONS:
        for page in (checkout / 'docs' / 'source' / section).glob('*.rst'):
            out = target / section / page.name
            out.parent.mkdir(parents=True, exist_ok=True)
            # the pages include each node's config.toml relative to their repo
            rel = os.path.relpath(src, out.parent)
            out.write_text(page.read_text().replace(_INCLUDE_ROOT, f'{rel}/'))

    missing = sorted(
        d.name[1:]
        for d in (src / 'juturna' / 'nodes').glob('_*')
        if d.is_dir()
        and not d.name.startswith('__')
        and not (target / 'nodes' / f'{d.name[1:]}.rst').exists()
    )

    if missing:
        raise ConfigError(f'nodes without a catalog page: {missing}')

    # juturna is a pkgutil namespace: the nodes join it for autodoc
    juturna.__path__.append(str(src / 'juturna'))


def setup(app):  # noqa: D103
    app.connect('config-inited', _copy_catalog)

    return {'parallel_read_safe': True}
