# -*- coding: utf-8 -*-
# pylint: disable=C0103,W0622
'''
Sphinx documentation for Salt
'''
import sys
import os
import types

from sphinx.directives import TocTree


# pylint: disable=R0903
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
        else:
            return Mock()
# pylint: enable=R0903

MOCK_MODULES = [
    # salt core
    'Crypto',
    'Crypto.Cipher',
    'Crypto.Hash',
    'Crypto.PublicKey',
    'Crypto.Random',
    'M2Crypto',
    'msgpack',
    'yaml',
    'yaml.constructor',
    'yaml.nodes',
    'zmq',
    # modules, renderers, states, returners, et al
    'django',
    'libvirt',
    'mako',
    'mako.template',
    'MySQLdb',
    'MySQLdb.cursors',
    'psutil',
    'pycassa',
    'pymongo',
    'rabbitmq_server',
    'redis',
    'rpm',
    'rpmUtils',
    'rpmUtils.arch',
    'yum',
    'OpenSSL',
    'zfs'
]

for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = Mock()


# -- Add paths to PYTHONPATH ---------------------------------------------------

docs_basepath = os.path.abspath(os.path.dirname(__file__))
addtl_paths = (
        os.pardir + os.sep + os.pardir, # salt itself (for autodoc)
        '_ext', # custom Sphinx extensions
)

for path in addtl_paths:
    sys.path.insert(0, os.path.abspath(os.path.join(docs_basepath, path)))

import salt.version


on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

# ----- Intersphinx Settings ------------------------------------------------>
intersphinx_mapping = {
        'python2': ('http://docs.python.org/2', None),
        'python3': ('http://docs.python.org/3', None)
}
# <---- Intersphinx Settings -------------------------------------------------

# -- General configuration -----------------------------------------------------

project = 'Salt'
copyright = '2013 SaltStack, Inc.'

version = salt.version.__version__
#release = '.'.join(map(str, salt.version.__version_info__))
release = '0.17.0'

language = 'en'
locale_dirs = [
    '_locale',
]

master_doc = 'contents'
templates_path = ['_templates']
exclude_patterns = ['_build', '_incl/*', 'ref/cli/_includes/*.rst']

extensions = [
    'saltdocs',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.extlinks',
    'sphinx.ext.intersphinx',
    'youtube',
]

modindex_common_prefix = ['salt.']

autosummary_generate = True

# Define a substitution for linking to the latest release tarball
rst_prolog = """\
.. |saltrepo| replace:: https://github.com/saltstack/salt
.. |latest| replace:: https://github.com/downloads/saltstack/salt/salt-%s.tar.gz
""" % salt.version.__version__

# A shortcut for linking to tickets on the GitHub issue tracker
extlinks = {
    'blob': ('https://github.com/saltstack/salt/blob/%s/%%s' % 'develop', None),
    'download': ('https://github.com/downloads/saltstack/salt/%s', None),
    'issue': ('https://github.com/saltstack/salt/issues/%s', 'issue '),
    'formula': ('https://github.com/saltstack-formulas/%s', ''),
}


### HTML options
if on_rtd:
    html_theme = 'default'
else:
    html_theme = 'saltstack'

html_theme_path = ['_themes']
html_title = None
html_short_title = 'Salt'

html_static_path = ['_static']
html_logo = 'saltstack_logo.png'
html_favicon = 'favicon.ico'
html_use_smartypants = False

html_additional_pages = {
    '404': '404.html',
}

html_default_sidebars = [
    'localtoc.html',
    'relations.html',
    'sourcelink.html',
    'searchbox.html',
]
html_sidebars = {
    'ref/**/all/salt.*': [
        'modules-sidebar.html',
        'localtoc.html',
        'relations.html',
        'sourcelink.html',
        'searchbox.html',
    ],
}

html_context = {
    'html_default_sidebars': html_default_sidebars,
    'github_base': 'https://github.com/saltstack/salt',
    'github_issues': 'https://github.com/saltstack/salt/issues',
    'github_downloads': 'https://github.com/saltstack/salt/downloads',
}

html_use_index = True
html_last_updated_fmt = '%b %d, %Y'
html_show_sourcelink = False
html_show_sphinx = True
html_show_copyright = True
#html_use_opensearch = ''


### Latex options
latex_documents = [
  ('contents', 'Salt.tex', 'Salt Documentation', 'SaltStack, Inc.', 'manual'),
]

latex_logo = '_static/saltstack_logo.png'


### Manpage options
# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
authors = [
    'Thomas S. Hatch <thatch45@gmail.com> and many others, please see the Authors file',
]

man_pages = [
    ('contents', 'salt', 'Salt Documentation', authors, 7),
    ('ref/cli/salt', 'salt', 'salt', authors, 1),
    ('ref/cli/salt-master', 'salt-master', 'salt-master Documentation', authors, 1),
    ('ref/cli/salt-minion', 'salt-minion', 'salt-minion Documentation', authors, 1),
    ('ref/cli/salt-key', 'salt-key', 'salt-key Documentation', authors, 1),
    ('ref/cli/salt-cp', 'salt-cp', 'salt-cp Documentation', authors, 1),
    ('ref/cli/salt-call', 'salt-call', 'salt-call Documentation', authors, 1),
    ('ref/cli/salt-syndic', 'salt-syndic', 'salt-syndic Documentation', authors, 1),
    ('ref/cli/salt-run', 'salt-run', 'salt-run Documentation', authors, 1),
    ('ref/cli/salt-ssh', 'salt-ssh', 'salt-ssh Documentation', authors, 1),
]


### epub options
epub_title = 'Salt Documentation'
epub_author = 'SaltStack, Inc.'
epub_publisher = epub_author
epub_copyright = copyright

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
