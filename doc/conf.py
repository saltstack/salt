# -*- coding: utf-8 -*-
# pylint: disable=C0103,W0622
'''
Sphinx documentation for Salt
'''
import functools
import sys
import os
import types

from sphinx.directives import TocTree


# pylint: disable=R0903
class Mock(object):
    '''
    Mock out specified imports

    This allows autodoc to do its thing without having oodles of req'd
    installed libs. This doesn't work with ``import *`` imports.

    http://read-the-docs.readthedocs.org/en/latest/faq.html#i-get-import-errors-on-libraries-that-depend-on-c-modules
    '''
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        ret = Mock()
        # If mocked function is used as a decorator, expose decorated function.
        # if args and callable(args[-1]):
        #     functools.update_wrapper(ret, args[0])
        return ret

    @classmethod
    def __getattr__(cls, name):
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
    'yaml.scanner',
    'zmq',

    # third-party libs for cloud modules
    'libcloud',
    'libcloud.compute',
    'libcloud.compute.base',
    'libcloud.compute.deployment',
    'libcloud.compute.providers',
    'libcloud.compute.types',
    'libcloud.loadbalancer',
    'libcloud.loadbalancer.types',
    'libcloud.loadbalancer.providers',
    'libcloud.common',
    'libcloud.common.google',

    # third-party libs for netapi modules
    'cherrypy',
    'cherrypy.lib',
    'cherrypy.process',
    'cherrypy.wsgiserver',
    'cherrypy.wsgiserver.ssl_builtin',

    'tornado',
    'tornado.concurrent',
    'tornado.gen',
    'tornado.httpserver',
    'tornado.ioloop',
    'tornado.web',
    'tornado.websocket',

    'ws4py',
    'ws4py.server',
    'ws4py.server.cherrypyserver',
    'ws4py.websocket',

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
    'requests',
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
try:
    docs_basepath = os.path.abspath(os.path.dirname(__file__))
except NameError:
    # sphinx-intl and six execute some code which will raise this NameError
    # assume we're in the doc/ directory
    docs_basepath = os.path.abspath(os.path.dirname('.'))

addtl_paths = (
        os.pardir,  # salt itself (for autodoc)
        '_ext',  # custom Sphinx extensions
)

for path in addtl_paths:
    sys.path.insert(0, os.path.abspath(os.path.join(docs_basepath, path)))


# We're now able to import salt
import salt.version


formulas_dir = os.path.join(os.pardir, docs_basepath, 'formulas')

# ----- Intersphinx Settings ------------------------------------------------>
intersphinx_mapping = {
        'python2': ('http://docs.python.org/2', None),
        'python3': ('http://docs.python.org/3', None)
}
# <---- Intersphinx Settings -------------------------------------------------

# -- General Configuration -----------------------------------------------------

project = 'Salt'
copyright = '2014 SaltStack, Inc.'

version = salt.version.__version__
#release = '.'.join(map(str, salt.version.__version_info__))
release = '2014.1.10'

spelling_lang = 'en_US'
language = 'en'
locale_dirs = [
    '_locale',
]

master_doc = 'contents'
templates_path = ['_templates']
exclude_patterns = ['_build', '_incl/*', 'ref/cli/_includes/*.rst']

extensions = [
    'saltdomain', # Must come early
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.extlinks',
    'sphinx.ext.intersphinx',
    'httpdomain',
    'youtube',
    'saltautodoc', # Must be AFTER autodoc
    'shorturls',
]

try:
    import sphinxcontrib.spelling
except ImportError:
    pass
else:
    extensions += ['sphinxcontrib.spelling']

modindex_common_prefix = ['salt.']

autosummary_generate = True

# Define a substitution for linking to the latest release tarball
rst_prolog = """\
.. |saltrepo| replace:: https://github.com/saltstack/salt
.. _`salt-users`: https://groups.google.com/forum/#!forum/salt-users
.. _`salt-announce`: https://groups.google.com/forum/#!forum/salt-announce
.. _`salt-packagers`: https://groups.google.com/forum/#!forum/salt-packagers
"""

# A shortcut for linking to tickets on the GitHub issue tracker
extlinks = {
    'blob': ('https://github.com/saltstack/salt/blob/%s/%%s' % 'develop', None),
    'download': ('https://cloud.github.com/downloads/saltstack/salt/%s', None),
    'issue': ('https://github.com/saltstack/salt/issues/%s', 'issue '),
    'formula': ('https://github.com/saltstack-formulas/%s', ''),
}


# ----- Localization -------------------------------------------------------->
locale_dirs = ['locale/']
gettext_compact = False
# <---- Localization ---------------------------------------------------------


### HTML options
html_theme = 'saltstack'
html_theme_path = ['_themes']
html_title = None
html_short_title = 'Salt'

html_static_path = ['_static']
html_logo = None # specfied in the theme layout.html
html_favicon = 'favicon.ico'
html_use_smartypants = False

# Set a var if we're building docs for the live site or not
on_saltstack = 'SALT_ON_SALTSTACK' in os.environ

# Use Google customized search or use Sphinx built-in JavaScript search
if on_saltstack:
    html_search_template = 'googlesearch.html'
else:
    html_search_template = 'searchbox.html'

html_additional_pages = {
    '404': '404.html',
}

html_default_sidebars = [
    html_search_template,
    'version.html',
    'localtoc.html',
    'relations.html',
    'sourcelink.html',
    'saltstack.html',
]
html_sidebars = {
    'ref/**/all/salt.*': [
        html_search_template,
        'version.html',
        'modules-sidebar.html',
        'localtoc.html',
        'relations.html',
        'sourcelink.html',
        'saltstack.html',
    ],
    'ref/formula/all/*': [
    ],
}

html_context = {
    'on_saltstack': on_saltstack,
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

### Latex options
latex_documents = [
  ('contents', 'Salt.tex', 'Salt Documentation', 'SaltStack, Inc.', 'manual'),
]

latex_logo = '_static/salt-logo.pdf'

latex_elements = {
    'inputenc': '',     # use XeTeX instead of the inputenc LaTeX package.
    'utf8extra': '',
    'preamble': '''

\usepackage{fontspec}
\setsansfont{DejaVu Sans}
\setromanfont{DejaVu Serif}
\setmonofont{DejaVu Sans Mono}
''',
}

### Linkcheck options
linkcheck_ignore = [r'http://127.0.0.1',
                    r'http://salt:\d+',
                    r'http://local:\d+',
                    r'https://console.aws.amazon.com',
                    r'http://192.168.33.10',
                    r'http://domain:\d+',
                    r'http://123.456.789.012:\d+',
                    r'http://localhost',
                    r'https://groups.google.com/forum/#!forum/salt-users',
                    r'http://logstash.net/docs/latest/inputs/udp',
                    r'http://logstash.net/docs/latest/inputs/zeromq',
                    r'http://www.youtube.com/saltstack',
                    r'http://raven.readthedocs.org',
                    r'https://getsentry.com',
                    r'http://salt-cloud.readthedocs.org',
                    r'http://salt.readthedocs.org',
                    r'http://www.pip-installer.org/',
                    r'http://www.windowsazure.com/',
                    r'https://github.com/watching',
                    r'dash-feed://',
                    r'https://github.com/saltstack/salt/',
                    r'http://bootstrap.saltstack.org',
                    r'https://bootstrap.saltstack.com',
                    r'https://raw.githubusercontent.com/saltstack/salt-bootstrap/stable/bootstrap-salt.sh',
                    r'media.readthedocs.org/dash/salt/latest/salt.xml',
                    r'https://portal.aws.amazon.com/gp/aws/securityCredentials',
                    r'https://help.github.com/articles/fork-a-repo',
                    r'dash-feed://https%3A//media.readthedocs.org/dash/salt/latest/salt.xml'
                    ]

linkcheck_anchors = False

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
    ('ref/cli/salt-cloud', 'salt-cloud', 'Salt Cloud Command', authors, 1),
    ('ref/cli/salt-api', 'salt-api', 'salt-api Command', authors, 1),
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
