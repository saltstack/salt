# -*- coding: utf-8 -*-

import sys
import os
import types

from sphinx.directives import TocTree


class Mock(object):
    '''
    Mock out specified imports

    This allows autodoc to do it's thing without having oodles of req'd
    installed libs. This doesn't work with ``import *`` imports.

    http://read-the-docs.readthedocs.org/en/latest/faq.html#i-get-import-errors-on-libraries-that-depend-on-c-modules
    '''
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return Mock()

    @classmethod
    def __getattr__(self, name):
        if name in ('__file__', '__path__'):
            return '/dev/null'
        elif name[0] == name[0].upper():
            return type(name, (), {})
        else:
            return Mock()

MOCK_MODULES = [
    # salt core
    'yaml',
    'yaml.nodes',
    'yaml.constructor',
    'msgpack',
    'zmq',
    'Crypto',
    'Crypto.Cipher',
    'Crypto.Hash',
    'Crypto.PublicKey',
    'Crypto.Random',
    'M2Crypto',
    # modules, renderers, states, returners, et al
    'MySQLdb',
    'MySQLdb.cursors',
    'psutil',
    'libvirt',
    'yum',
    'mako',
    'mako.template',
    'pymongo',
    'redis',
    'rpm',
    'rpmUtils',
    'rpmUtils.arch',
    'pycassa',
]

for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = Mock()


# -- Add paths to PYTHONPATH ---------------------------------------------------

docs_basepath = os.path.abspath(os.path.dirname(__file__))
addtl_paths = (
        os.pardir, # salt itself (for autodoc)
        '_ext', # custom Sphinx extensions
)

for path in addtl_paths:
    sys.path.insert(0, os.path.abspath(os.path.join(docs_basepath, path)))

from salt.version import __version__


on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

# -- General configuration -----------------------------------------------------

project = 'Salt'
copyright = '2012, Thomas S. Hatch'

version = __version__
release = version

master_doc = 'contents'
templates_path = ['_templates']
exclude_patterns = ['_build']

extensions = ['saltdocs', 'sphinx.ext.autodoc', 'sphinx.ext.extlinks',
    'sphinx.ext.autosummary']

modindex_common_prefix = ['salt.']

autosummary_generate = True

# Define a substitution for linking to the latest release tarball
rst_prolog = """\
.. _`installation`: http://saltstack.org/install/
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
html_logo = 'salt-vert.png'
html_favicon = 'favicon.ico'
html_use_smartypants = False

html_additional_pages = {
    '404': '404.html',
}

html_sidebars = {
    'ref/**/all/salt.*': [
        'autosummarysidebar.html',
        'localtoc.html',
        'relations.html',
        'sourcelink.html',
        'searchbox.html',
    ],
}

html_context = {
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
  ('contents', 'Salt.tex', 'Salt Documentation', 'Thomas Hatch', 'manual'),
]

latex_logo = '_static/salt-vert.png'


### Manpage options
# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
authors = [
    'Thomas S. Hatch <thatch@gmail.com> and many others, please see the Authors file',
]

man_pages = [
    ('ref/cli/salt', 'salt', 'salt', authors, 1),
    ('contents', 'salt', 'Salt Documentation', authors, 7),
    ('ref/cli/salt-master', 'salt-master', 'salt-master Documentation', authors, 1),
    ('ref/cli/salt-minion', 'salt-minion', 'salt-minion Documentation', authors, 1),
    ('ref/cli/salt-key', 'salt-key', 'salt-key Documentation', authors, 1),
    ('ref/cli/salt-cp', 'salt-cp', 'salt-cp Documentation', authors, 1),
    ('ref/cli/salt-call', 'salt-call', 'salt-call Documentation', authors, 1),
    ('ref/cli/salt-syndic', 'salt-syndic', 'salt-syndic Documentation', authors, 1),
    ('ref/cli/salt-run', 'salt-run', 'salt-run Documentation', authors, 1),
]


### epub options
epub_title = 'Salt Documentation'
epub_author = 'Thomas S. Hatch'
epub_publisher = epub_author
epub_copyright = '2012, Thomas S. Hatch'

epub_scheme = 'URL'
epub_identifier = 'http://saltstack.org/'

#epub_tocdepth = 3


def skip_mod_init_member(app, what, name, obj, skip, options):
    if name.startswith('_'):
        return True
    if isinstance(obj, types.FunctionType) and obj.__name__ == 'mod_init':
        return True
    return False


def _normalize_version(args):
    _, path = args
    return '.'.join([x.zfill(4) for x in (path.split('/')[-1].split('.'))])


class ReleasesTree(TocTree):
    option_spec = dict(TocTree.option_spec)

    def run(self):
        rst = super(ReleasesTree, self).run()
        entries = rst[0][0]['entries'][:]
        entries.sort(key=_normalize_version, reverse=True)
        rst[0][0]['entries'][:] = entries
        return rst


def setup(app):
    app.add_directive('releasestree', ReleasesTree)
    app.connect('autodoc-skip-member', skip_mod_init_member)
