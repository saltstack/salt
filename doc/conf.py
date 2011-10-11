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

master_doc = 'index'
templates_path = ['_templates']
exclude_patterns = ['_build']

extensions = ['saltdocs', 'sphinx.ext.autodoc', 'sphinx.ext.extlinks']

modindex_common_prefix = ['salt.']

# Define a substitution for linking to the latest release tarball
rst_prolog = """\
.. |latest| replace:: https://github.com/downloads/thatch45/salt/salt-%s.tar.gz
""" % __version__

# A shortcut for linking to tickets on the GitHub issue tracker
extlinks = {
    'blob': ('https://github.com/thatch45/salt/blob/v%s/%%s' % __version__, None),
    'download': ('https://github.com/downloads/thatch45/salt/%s', None),
    'issue': ('https://github.com/thatch45/salt/issues/%s', 'issue '),
}


### HTML options
html_theme = 'agogo'
html_title = None
html_short_title = 'Salt'

html_logo = 'salt.png'
html_favicon = 'salt.ico'
html_static_path = ['_static']

html_sidebars = {'index': ['indexsidebar.html']}

html_last_updated_fmt = '%b %d, %Y'

html_additional_pages = {'index': 'index.html'}

html_show_sourcelink = False
html_show_sphinx = True
html_show_copyright = True
#html_use_opensearch = ''


### Latex options
latex_documents = [
  ('index', 'Salt.tex', u'Salt Documentation',
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
    ('index', 'salt', u'Salt Documentation', authors, 7),
    ('ref/cli/salt-master', 'salt-master', u'salt-master Documentation', authors, 1),
    ('ref/cli/salt-minion', 'salt-minion', u'salt-minion Documentation', authors, 1),
    ('ref/cli/salt-key', 'salt-key', u'salt-key Documentation', authors, 1),
    ('ref/cli/salt-cp', 'salt-cp', u'salt-cp Documentation', authors, 1),
    ('ref/cli/salt-call', 'salt-call', u'salt-call Documentation', authors, 1),
    ('ref/cli/salt-syndic', 'salt-syndic', u'salt-syndic Documentation', authors, 1),
    ('ref/cli/salt-run', 'salt-run', u'salt-run Documentation', authors, 1),
]
