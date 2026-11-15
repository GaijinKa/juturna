"""
Copy the pages kept in other repositories into the build.

- Nodes section: the node pages of juturna-nodes (``JUTURNA_NODES_DIR``).
- Browser section: the Markdown docs of juturna-browser
  (``JUTURNA_BROWSER_DIR``).

Both variables point to a checkout; the copies go to folders listed in
``.gitignore``.
"""

import os
import pathlib
import shutil

import juturna
from sphinx.errors import ConfigError


_NODE_SECTIONS = ('nodes', 'contribute')
_NODE_INCLUDE_ROOT = '../../../src/'

_BROWSER_REPO = 'https://github.com/meetecho/juturna-browser'
_DEMOS_URL = 'https://meetecho.github.io/juturna/demos/'

# juturna-browser page -> page in the browser section
_BROWSER_PAGES = {
    'README.md': 'index.md',
    'docs/guide.md': 'guide.md',
    'docs/how-it-works.md': 'how-it-works.md',
    'docs/demos.md': 'demos.md',
    'docs/api.md': 'api.md',
    'docs/development.md': 'development.md',
}


def _checkout(variable: str, what: str) -> pathlib.Path:
    path = os.environ.get(variable)

    if not path:
        raise ConfigError(
            f'set {variable} to a {what} checkout: part of the documentation '
            'is built from its pages'
        )

    return pathlib.Path(path).resolve()


def _fresh(target: pathlib.Path) -> pathlib.Path:
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)

    return target


def _copy_nodes(srcdir: pathlib.Path):
    checkout = _checkout('JUTURNA_NODES_DIR', 'juturna-nodes')
    src = checkout / 'src'
    target = _fresh(srcdir / 'catalog')

    for section in _NODE_SECTIONS:
        for page in (checkout / 'docs' / 'source' / section).glob('*.rst'):
            out = target / section / page.name
            out.parent.mkdir(parents=True, exist_ok=True)
            # the pages include each node's config.toml relative to their repo
            rel = os.path.relpath(src, out.parent)
            out.write_text(
                page.read_text().replace(_NODE_INCLUDE_ROOT, f'{rel}/')
            )

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


def _copy_browser(srcdir: pathlib.Path):
    checkout = _checkout('JUTURNA_BROWSER_DIR', 'juturna-browser')
    target = _fresh(srcdir / 'browser')

    for source, page in _BROWSER_PAGES.items():
        text = (checkout / source).read_text()

        # the README links the other pages under docs/
        if source == 'README.md':
            text = text.replace('](docs/', '](')
            text = text.replace(
                '](LICENSE)', f']({_BROWSER_REPO}/blob/main/LICENSE)'
            )

        # the demos are published with the site (docs/build_demos.sh), under
        # demos/ next to browser/
        text = text.replace('http://localhost:8765/', _DEMOS_URL)
        text = text.replace('href="../examples/', 'href="../demos/examples/')
        (target / page).write_text(text)

    # figures are <picture> elements, which Sphinx does not copy: see setup()
    if (checkout / 'docs' / 'img').is_dir():
        shutil.copytree(checkout / 'docs' / 'img', target / 'img')


def _copy_all(app, config):
    srcdir = pathlib.Path(app.srcdir)
    _copy_nodes(srcdir)
    _copy_browser(srcdir)


def _copy_browser_images(app, exception):
    images = pathlib.Path(app.srcdir) / 'browser' / 'img'

    if exception is None and app.builder.format == 'html' and images.is_dir():
        shutil.copytree(
            images,
            pathlib.Path(app.outdir) / 'browser' / 'img',
            dirs_exist_ok=True,
        )


def setup(app):  # noqa: D103
    app.connect('config-inited', _copy_all)
    app.connect('build-finished', _copy_browser_images)

    return {'parallel_read_safe': True}
