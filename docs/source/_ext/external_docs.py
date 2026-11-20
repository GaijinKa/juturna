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
    'docs/write-a-node.md': 'write-a-node.md',
    'docs/how-it-works.md': 'how-it-works.md',
    'docs/demos.md': 'demos.md',
    'docs/api.md': 'api.md',
    'docs/development.md': 'development.md',
}


# meta descriptions of the pages whose first lines make a poor one
_BROWSER_META = {
    'demos.md': 'Juturna pipelines running in a browser tab, on Pyodide: '
    'background blur, noise suppression, live transcription and '
    'translation. The models run in the page, the audio stays on the device.',
}


def _front_matter(description: str) -> str:
    return (
        f'---\nmyst:\n  html_meta:\n    description: "{description}"\n'
        f'og:description: "{description}"\n---\n\n'
    )


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
            text = page.read_text().replace(_NODE_INCLUDE_ROOT, f'{rel}/')
            readme = src / 'juturna' / 'nodes' / f'_{page.stem}' / 'README.md'
            if readme.is_file():
                text = _add_readme_sections(text, readme.read_text(), out)
            out.write_text(text)

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


# README headings that the catalogue page names differently
_README_TITLES = {'Example': 'Pipeline usage', 'License note': 'License'}


def _readme_sections(readme: str) -> list[tuple[str, str]]:
    # the part before the first ## repeats the header of the catalogue page
    chunks = ('\n' + readme).split('\n## ')[1:]
    sections = []
    for chunk in chunks:
        title, _, body = chunk.partition('\n')
        title = title.strip()
        # "Node type: source" and the like are in the page header already
        if title.startswith('Node ') and ':' in title:
            continue
        sections.append((_README_TITLES.get(title, title), body.strip()))

    return sections


def _add_readme_sections(text: str, readme: str, out: pathlib.Path) -> str:
    added = ''
    for i, (title, body) in enumerate(_readme_sections(readme)):
        if not body or f'\n{title}\n---' in text:
            continue
        # .inc is not a source suffix: Sphinx reads it only through include
        snippet = out.with_name(f'{out.stem}.readme{i}.inc')
        snippet.write_text(body + '\n')
        added += (
            f'{title}\n{"-" * len(title)}\n\n'
            f'.. include:: {snippet.name}\n'
            '    :parser: myst_parser.sphinx_\n\n'
        )

    for anchor in ('Configuration\n---', 'Reference\n---'):
        at = text.find(anchor)
        if at >= 0:
            return text[:at] + added + text[at:]

    return text + '\n' + added


def _copy_browser(srcdir: pathlib.Path):
    checkout = _checkout('JUTURNA_BROWSER_DIR', 'juturna-browser')
    target = _fresh(srcdir / 'browser')

    for source, page in _BROWSER_PAGES.items():
        text = (checkout / source).read_text()

        # the README links the other pages under docs/
        if source == 'README.md':
            text = text.replace('](docs/', '](')
            for name in ('LICENSE', 'CONTRIBUTING.md', 'SECURITY.md'):
                text = text.replace(
                    f']({name})', f']({_BROWSER_REPO}/blob/main/{name})'
                )

        # examples/standalone is not a demo of the site: link it on GitHub
        examples = f']({_BROWSER_REPO}/tree/main/examples/'
        for prefix in ('](examples/', '](../examples/'):
            text = text.replace(prefix, examples)

        # the demos are published with the site (docs/build_demos.sh), under
        # demos/ next to browser/
        text = text.replace('http://localhost:8765/', _DEMOS_URL)
        text = text.replace('href="../examples/', 'href="../demos/examples/')
        if page in _BROWSER_META:
            text = _front_matter(_BROWSER_META[page]) + text
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
