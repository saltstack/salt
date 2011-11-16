# -*- coding: utf-8 -*-

import sys, os

docs_basepath = os.path.abspath(os.path.join(os.path.dirname(__file__)))

sys.path.extend([
    os.path.join(docs_basepath, '..'), # salt directory (for autodoc)
    os.path.join(docs_basepath, '_ext'), # Sphinx extensions
])

from salt import __version__

# -- General configuration -----------------------------------------------------

project = u'Salt'
copyright = u'2011, Thomas S. Hatch'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = __version__
# The full version, including alpha/beta/rc tags.
release = version

master_doc = 'contents'
templates_path = ['_templates']
exclude_patterns = ['_build']

extensions = ['saltdocs', 'sphinx.ext.autodoc', 'sphinx.ext.extlinks', 'sphinx.ext.autosummary']

modindex_common_prefix = ['salt.']

autosummary_generate = True

# Define a substitution for linking to the latest release tarball
rst_prolog = """\
.. |saltrepo| replace:: https://github.com/saltstack/salt
.. |latest| replace:: https://github.com/downloads/saltstack/salt/salt-%s.tar.gz
""" % __version__

# A shortcut for linking to tickets on the GitHub issue tracker
extlinks = {
    'blob': ('https://github.com/saltstack/salt/blob/v%s/%%s' % __version__, None),
    'download': ('https://github.com/downloads/saltstack/salt/%s', None),
    'issue': ('https://github.com/saltstack/salt/issues/%s', 'issue '),
}


### HTML options
html_theme = 'default'
html_title = None
html_short_title = 'Salt'

html_static_path = ['_static']
html_logo = 'salt.png'
html_favicon = 'favicon.ico'
html_style = ['base-salt.css']
html_use_smartypants = False

html_additional_pages = {'index': 'index.html'}

html_default_sidebars = [
    'localtoc.html',
    'relations.html',
    'sourcelink.html',
    'searchbox.html']

html_sidebars = {
    'ref/**/all/salt.*': ['autosummarysidebar.html'] + html_default_sidebars,
    'index': ['indexsidebar.html', 'searchbox.html'],
}

html_context = {
    'html_default_sidebars': html_default_sidebars,
    'github_base': 'https://github.com/saltstack/salt',
    'github_issues': 'https://github.com/saltstack/salt/issues',
    'github_downloads': 'https://github.com/saltstack/salt/downloads',
}

html_use_index = False
html_last_updated_fmt = '%b %d, %Y'
html_show_sourcelink = False
html_show_sphinx = True
html_show_copyright = True
#html_use_opensearch = ''


### Latex options
latex_documents = [
  ('contents', 'Salt.tex', u'Salt Documentation',
   u'Thomas Hatch', 'manual'),
]

latex_logo = '_static/salt.png'


### Manpage options
# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
authors = [
    u'Thomas S. Hatch <thatch@gmail.com> and many others, please see the Authors file',
]

man_pages = [
    ('ref/cli/salt', 'salt', u'salt', authors, 1),
    ('contents', 'salt', u'Salt Documentation', authors, 7),
    ('ref/cli/salt-master', 'salt-master', u'salt-master Documentation', authors, 1),
    ('ref/cli/salt-minion', 'salt-minion', u'salt-minion Documentation', authors, 1),
    ('ref/cli/salt-key', 'salt-key', u'salt-key Documentation', authors, 1),
    ('ref/cli/salt-cp', 'salt-cp', u'salt-cp Documentation', authors, 1),
    ('ref/cli/salt-call', 'salt-call', u'salt-call Documentation', authors, 1),
    ('ref/cli/salt-syndic', 'salt-syndic', u'salt-syndic Documentation', authors, 1),
    ('ref/cli/salt-run', 'salt-run', u'salt-run Documentation', authors, 1),
]


### epub options
epub_title = u'Salt Documentation'
epub_author = u'Thomas S. Hatch'
epub_publisher = epub_author
epub_copyright = u'2011, Thomas S. Hatch'

epub_scheme = 'URL'
epub_identifier = 'http://saltstack.org/'

#epub_tocdepth = 3
