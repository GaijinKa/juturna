import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / '_ext'))

project = 'juturna'
copyright = '2025, Meetecho'
author = 'Antonio Bevilacqua'
version = '3.0.0'  # x-release-please-version
release = version

# the node pages are imported by autodoc: their optional dependencies are mocked
autodoc_mock_imports = [
    'av',
    'faster_whisper',
    'grpc',
    'juturna.remotizer.c_protos',
    'juturna.remotizer.utils',
    'pymongo',
    'requests',
    'silero_vad',
    'torch',
    'ultralytics',
    'watchdog',
    'websockets',
]

# juturna-browser pages are Markdown, with GitHub-style heading anchors
myst_heading_anchors = 3

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.autosummary',
    'sphinx.ext.doctest',
    'sphinx_design',
    'sphinx_new_tab_link',
    'myst_parser',
    'external_docs',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

linkcheck_ignore = [
    # deployed with the site: the build does not see them online yet
    r'https://meetecho\.github\.io/juturna/demos/',
    # answers 403 to every client that is not a browser
    r'https://www\.meetecho\.com/',
]

# open external links in blank targets
new_tab_link_show_external_link_icon = True

# theme configuration
html_theme = 'furo'
html_title = 'Juturna'
html_short_title = 'Juturna docs'
html_favicon = '_static/img/juturna_favicon.png'

show_authors = True
html_show_copyright = True

pygments_style = 'meetecho_pygments.MeetechoStyle'
pygments_dark_style = 'meetecho_pygments.MeetechoDarkStyle'

html_static_path = ['_static']

html_css_files = ['css/meetecho_style.css']

# colours and fonts from the Meetecho design system tokens
_font_stack = (
    '"Ubuntu derivative Juturna", system-ui, -apple-system, "Segoe UI", '
    'Roboto, "Helvetica Neue", Arial, sans-serif'
)
_font_stack_mono = (
    '"Ubuntu Mono derivative Juturna", ui-monospace, SFMono-Regular, Menlo, '
    'Consolas, monospace'
)

_light_css_variables = {
    'font-stack': _font_stack,
    'font-stack--monospace': _font_stack_mono,
    'font-stack--headings': _font_stack,
    'color-foreground-primary': '#0f1d26',
    'color-foreground-secondary': '#4b5d6b',
    'color-foreground-muted': '#4b5d6b',
    'color-foreground-border': '#7d8f9d',
    'color-background-primary': '#ffffff',
    'color-background-secondary': '#f5f8fb',
    'color-background-hover': '#eef6fd',
    'color-background-hover--transparent': '#eef6fd00',
    'color-background-border': '#e2e9ef',
    'color-background-item': '#cdd8e1',
    'color-brand-primary': '#1a6dad',
    'color-brand-content': '#1a6dad',
    'color-brand-visited': '#1a6dad',
    'color-highlighted-background': '#eef6fd',
    'color-highlight-on-target': '#fdf3e0',
    'color-sidebar-link-text--top-level': '#4b5d6b',
    'color-sidebar-link-text': '#4b5d6b',
    'color-sidebar-caption-text': '#4b5d6b',
    'color-card-border': '#e2e9ef',
}

_dark_css_variables = {
    'color-foreground-primary': '#e4edf3',
    'color-foreground-secondary': '#a9bccb',
    'color-foreground-muted': '#a9bccb',
    'color-foreground-border': '#5f7a8d',
    'color-background-primary': '#08161f',
    'color-background-secondary': '#0c1e2a',
    'color-background-hover': '#0f2433',
    'color-background-hover--transparent': '#0f243300',
    'color-background-border': '#1f3a4d',
    'color-background-item': '#1f3a4d',
    'color-brand-primary': '#6cb6f0',
    'color-brand-content': '#6cb6f0',
    'color-brand-visited': '#6cb6f0',
    'color-highlighted-background': '#0f2433',
    'color-highlight-on-target': '#0f2433',
    'color-card-background': '#0f2433',
    'color-card-border': '#1f3a4d',
    'color-admonition-background': 'transparent',
    'color-sidebar-link-text--top-level': '#a9bccb',
    'color-sidebar-link-text': '#a9bccb',
    'color-sidebar-caption-text': '#a9bccb',
}

html_theme_options = {
    'globaltoc_collapse': False,
    'light_logo': 'img/juturna_logo.png',
    'dark_logo': 'img/juturna_logo_dark.png',
    'sidebar_hide_name': True,
    'light_css_variables': _light_css_variables,
    'dark_css_variables': _dark_css_variables,
    'footer_icons': [
        {
            'name': 'GitHub',
            'url': 'https://github.com/meetecho/juturna',
            'html': """
                <svg fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 .5a11.5 11.5 0 00-3.6 22.4c.6.1.8-.3.8-.6v-2c-3.2.7-3.9-1.5-3.9-1.5-.5-1.3-1.3-1.7-1.3-1.7-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.6-.3-5.3-1.3-5.3-5.7 0-1.3.5-2.3 1.2-3.1-.1-.3-.5-1.5.1-3.1 0 0 1-.3 3.2 1.2a11 11 0 015.8 0c2.2-1.5 3.2-1.2 3.2-1.2.6 1.6.2 2.8.1 3.1.8.8 1.2 1.8 1.2 3.1 0 4.4-2.7 5.4-5.3 5.7.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A11.5 11.5 0 0012 .5z"></path>
                </svg>
            """,
            'class': '',
        },
        {
            'name': 'Meetecho',
            'url': 'https://meetecho.com',
            'html': """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 24 24">
                    <path fill-rule="evenodd" d="M4.44,15.54 C4.44,15.54 4.44,21.60 4.44,21.60 4.44,21.60 6.42,21.60 6.42,21.60 6.42,21.60 8.40,21.60 8.40,21.60 8.40,21.60 8.42,18.44 8.42,18.44 8.46,15.54 8.47,15.30 8.66,15.34 8.87,15.37 11.22,16.72 11.70,17.08 11.92,17.24 11.99,17.22 12.60,16.80 13.34,16.30 15.17,15.24 15.28,15.24 15.32,15.24 15.36,16.67 15.36,18.42 15.36,18.42 15.36,21.60 15.36,21.60 15.36,21.60 17.34,21.60 17.34,21.60 17.34,21.60 19.32,21.60 19.32,21.60 19.32,21.60 19.32,15.54 19.32,15.54 19.32,15.54 19.32,9.48 19.32,9.48 19.32,9.48 17.34,9.48 17.34,9.48 17.34,9.48 15.36,9.48 15.36,9.48 15.36,9.48 15.36,10.18 15.36,10.18 15.36,10.18 15.36,10.88 15.36,10.88 15.36,10.88 13.63,12.04 13.63,12.04 13.63,12.04 11.92,13.18 11.92,13.18 11.92,13.18 10.16,12.02 10.16,12.02 10.16,12.02 8.41,10.86 8.41,10.86 8.41,10.86 8.40,10.16 8.40,10.16 8.40,10.16 8.40,9.48 8.40,9.48 8.40,9.48 6.42,9.48 6.42,9.48 6.42,9.48 4.44,9.48 4.44,9.48 4.44,9.48 4.44,15.54 4.44,15.54 Z M16.25,2.81 C15.20,3.26 14.52,4.32 14.52,5.46 14.52,6.26 14.71,6.76 15.25,7.38 15.79,7.98 16.45,8.28 17.32,8.28 18.49,8.28 19.45,7.68 19.93,6.66 20.22,6.02 20.23,4.90 19.93,4.26 19.69,3.71 18.98,3.05 18.41,2.81 17.90,2.59 16.74,2.60 16.25,2.81 Z M5.15,2.99 C3.12,4.07 3.11,6.89 5.15,7.94 7.60,9.22 10.25,6.65 9.01,4.21 8.26,2.75 6.59,2.22 5.15,2.99Z"></path>
                </svg>
            """,
            'class': '',
        },
    ],
}

rst_prolog = f"""
.. |version-badge| replace:: :bdg-secondary-line:`version {version}`
"""
