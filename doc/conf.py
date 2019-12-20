# -*- coding: utf-8 -*-
# pylint: disable=C0103,W0622
'''
Sphinx documentation for Salt
'''
import sys
import os
import re
import types
import time

from sphinx.directives import TocTree


class Mock(object):
    '''
    Mock out specified imports.

    This allows autodoc to do its thing without having oodles of req'd
    installed libs. This doesn't work with ``import *`` imports.

    This Mock class can be configured to return a specific values at specific names, if required.

    http://read-the-docs.readthedocs.org/en/latest/faq.html#i-get-import-errors-on-libraries-that-depend-on-c-modules
    '''
    def __init__(self, mapping=None, *args, **kwargs):  # pylint: disable=unused-argument
        """
        Mapping allows autodoc to bypass the Mock object, but actually assign
        a specific value, expected by a specific attribute returned.
        """
        self.__mapping = mapping or {}

    __all__ = []

    def __call__(self, *args, **kwargs):
        # If mocked function is used as a decorator, expose decorated function.
        # if args and callable(args[-1]):
        #     functools.update_wrapper(ret, args[0])
        return Mock(mapping=self.__mapping)

    def __getattr__(self, name):
        if name in self.__mapping:
            data = self.__mapping.get(name)
        elif name in ('__file__', '__path__'):
            data = '/dev/null'
        elif name in ('__mro_entries__', '__qualname__'):
            raise AttributeError("'Mock' object has no attribute '%s'" % (name))
        else:
            data = Mock(mapping=self.__mapping)
        return data

    def __iter__(self):
        return self

    @staticmethod
    def __next__():
        raise StopIteration

    # For Python 2
    next = __next__


def mock_decorator_with_params(*oargs, **okwargs):  # pylint: disable=unused-argument
    '''
    Optionally mock a decorator that takes parameters

    E.g.:

    @blah(stuff=True)
    def things():
        pass
    '''
    def inner(fn, *iargs, **ikwargs):  # pylint: disable=unused-argument
        if hasattr(fn, '__call__'):
            return fn
        return Mock()
    return inner


MOCK_MODULES = [
    # Python stdlib
    'user',

    # salt core
    'concurrent',
    'Crypto',
    'Crypto.Signature',
    'Crypto.Cipher',
    'Crypto.Hash',
    'Crypto.PublicKey',
    'Crypto.Random',
    'Crypto.Signature',
    'Crypto.Signature.PKCS1_v1_5',
    'M2Crypto',
    'msgpack',
    'yaml',
    'yaml.constructor',
    'yaml.nodes',
    'yaml.parser',
    'yaml.scanner',
    'zmq',
    'zmq.eventloop',
    'zmq.eventloop.ioloop',

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
    'tornado.escape',
    'tornado.gen',
    'tornado.httpclient',
    'tornado.httpserver',
    'tornado.httputil',
    'tornado.ioloop',
    'tornado.iostream',
    'tornado.netutil',
    'tornado.simple_httpclient',
    'tornado.stack_context',
    'tornado.web',
    'tornado.websocket',
    'tornado.locks',

    'ws4py',
    'ws4py.server',
    'ws4py.server.cherrypyserver',
    'ws4py.websocket',

    # modules, renderers, states, returners, et al
    'ClusterShell',
    'ClusterShell.NodeSet',
    'MySQLdb',
    'MySQLdb.cursors',
    'OpenSSL',
    'avahi',
    'boto.regioninfo',
    'concurrent',
    'dbus',
    'django',
    'dns',
    'dns.resolver',
    'dson',
    'hjson',
    'jnpr',
    'jnpr.junos',
    'jnpr.junos.utils',
    'jnpr.junos.utils.config',
    'jnpr.junos.utils.sw',
    'keyring',
    'libvirt',
    'lxml',
    'lxml.etree',
    'msgpack',
    'nagios_json',
    'napalm',
    'netaddr',
    'netaddr.IPAddress',
    'netaddr.core',
    'netaddr.core.AddrFormatError',
    'ntsecuritycon',
    'psutil',
    'pycassa',
    'pyconnman',
    'pyiface',
    'pymongo',
    'pyroute2',
    'pyroute2.ipdb',
    'rabbitmq_server',
    'redis',
    'rpm',
    'rpmUtils',
    'rpmUtils.arch',
    'salt.ext.six.moves.winreg',
    'twisted',
    'twisted.internet',
    'twisted.internet.protocol',
    'twisted.internet.protocol.DatagramProtocol',
    'win32security',
    'yum',
    'zfs',
]

MOCK_MODULES_MAPPING = {
    'cherrypy': {'config': mock_decorator_with_params},
    'ntsecuritycon': {
        'STANDARD_RIGHTS_REQUIRED': 0,
        'SYNCHRONIZE': 0,
    },
    'psutil': {'total': 0},  # Otherwise it will crash Sphinx
}

for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = Mock(mapping=MOCK_MODULES_MAPPING.get(mod_name))

# Define a fake version attribute for the following libs.
sys.modules['libcloud'].__version__ = '0.0.0'
sys.modules['msgpack'].version = (1, 0, 0)
sys.modules['psutil'].version_info = (3, 0, 0)
sys.modules['pymongo'].version = '0.0.0'
sys.modules['tornado'].version_info = (0, 0, 0)
sys.modules['boto.regioninfo']._load_json_file = {'endpoints': None}


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

for addtl_path in addtl_paths:
    sys.path.insert(0, os.path.abspath(os.path.join(docs_basepath, addtl_path)))


# We're now able to import salt
import salt.version


formulas_dir = os.path.join(os.pardir, docs_basepath, 'formulas')

# ----- Intersphinx Settings ------------------------------------------------>
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None)
}
# <---- Intersphinx Settings -------------------------------------------------

# -- General Configuration -----------------------------------------------------

# Set a var if we're building docs for the live site or not
on_saltstack = 'SALT_ON_SALTSTACK' in os.environ

project = 'Salt'
repo_primary_branch = 'master'  # This is the default branch on GitHub for the Salt project
version = salt.version.__version__
latest_release = '2019.2.2'  # latest release
previous_release = '2018.3.4'  # latest release from previous branch
previous_release_dir = '2018.3'  # path on web server for previous branch
next_release = ''  # next release
next_release_dir = ''  # path on web server for next release branch

today = ''
copyright = ''
if on_saltstack:
    today = "Generated on " + time.strftime("%B %d, %Y") + " at " + time.strftime("%X %Z") + "."
    copyright = time.strftime("%Y")

# < --- START do not merge these settings to other branches START ---> #
build_type = repo_primary_branch # latest, previous, master, next
# < --- END do not merge these settings to other branches END ---> #

# Set google custom search engine

if build_type == repo_primary_branch:
    release = latest_release
    search_cx = '011515552685726825874:v1had6i279q' # master
    #search_cx = '011515552685726825874:x17j5zl74g8' # develop
elif build_type == 'next':
    release = next_release
    search_cx = '011515552685726825874:ht0p8miksrm' # latest
elif build_type == 'previous':
    release = previous_release
    if release.startswith('2018.3'):
        search_cx = '011515552685726825874:vadptdpvyyu' # 2018.3
    elif release.startswith('2017.7'):
        search_cx = '011515552685726825874:w-hxmnbcpou' # 2017.7
    elif release.startswith('2016.11'):
        search_cx = '011515552685726825874:dlsj745pvhq' # 2016.11
    else:
        search_cx = '011515552685726825874:ht0p8miksrm' # latest
else: # latest or something else
    release = latest_release
    search_cx = '011515552685726825874:ht0p8miksrm' # latest

needs_sphinx = '1.3'

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
    'sphinx.ext.napoleon',
    'sphinx.ext.autosummary',
    'sphinx.ext.extlinks',
    'sphinx.ext.intersphinx',
    'httpdomain',
    'youtube',
    'saltrepo'
    #'saltautodoc', # Must be AFTER autodoc
    #'shorturls',
]

try:
    import sphinxcontrib.spelling  # false positive, pylint: disable=unused-import
except ImportError:
    pass
else:
    extensions += ['sphinxcontrib.spelling']

modindex_common_prefix = ['salt.']

autosummary_generate = True

# strip git rev as there won't necessarily be a release based on it
stripped_release = re.sub(r'-\d+-g[0-9a-f]+$', '', release)

# Define a substitution for linking to the latest release tarball
rst_prolog = """\
.. |current_release_doc| replace:: :doc:`/topics/releases/{release}`
.. |saltrepo| replace:: https://github.com/saltstack/salt
.. _`salt-users`: https://groups.google.com/forum/#!forum/salt-users
.. _`salt-announce`: https://groups.google.com/forum/#!forum/salt-announce
.. _`salt-packagers`: https://groups.google.com/forum/#!forum/salt-packagers
.. _`salt-slack`: https://saltstackcommunity.herokuapp.com/
.. |windownload| raw:: html

     <p>Python2 x86: <a
     href="https://repo.saltstack.com/windows/Salt-Minion-{release}-Py2-x86-Setup.exe"><strong>Salt-Minion-{release}-x86-Setup.exe</strong></a>
      | <a href="https://repo.saltstack.com/windows/Salt-Minion-{release}-Py2-x86-Setup.exe.md5"><strong>md5</strong></a></p>

     <p>Python2 AMD64: <a
     href="https://repo.saltstack.com/windows/Salt-Minion-{release}-Py2-AMD64-Setup.exe"><strong>Salt-Minion-{release}-AMD64-Setup.exe</strong></a>
      | <a href="https://repo.saltstack.com/windows/Salt-Minion-{release}-Py2-AMD64-Setup.exe.md5"><strong>md5</strong></a></p>
     <p>Python3 x86: <a
     href="https://repo.saltstack.com/windows/Salt-Minion-{release}-Py3-x86-Setup.exe"><strong>Salt-Minion-{release}-x86-Setup.exe</strong></a>
      | <a href="https://repo.saltstack.com/windows/Salt-Minion-{release}-Py3-x86-Setup.exe.md5"><strong>md5</strong></a></p>

     <p>Python3 AMD64: <a
     href="https://repo.saltstack.com/windows/Salt-Minion-{release}-Py3-AMD64-Setup.exe"><strong>Salt-Minion-{release}-AMD64-Setup.exe</strong></a>
      | <a href="https://repo.saltstack.com/windows/Salt-Minion-{release}-Py3-AMD64-Setup.exe.md5"><strong>md5</strong></a></p>


.. |osxdownloadpy2| raw:: html

     <p>x86_64: <a href="https://repo.saltstack.com/osx/salt-{release}-py2-x86_64.pkg"><strong>salt-{release}-py2-x86_64.pkg</strong></a>
      | <a href="https://repo.saltstack.com/osx/salt-{release}-py2-x86_64.pkg.md5"><strong>md5</strong></a></p>

.. |osxdownloadpy3| raw:: html

     <p>x86_64: <a href="https://repo.saltstack.com/osx/salt-{release}-py3-x86_64.pkg"><strong>salt-{release}-py3-x86_64.pkg</strong></a>
      | <a href="https://repo.saltstack.com/osx/salt-{release}-py3-x86_64.pkg.md5"><strong>md5</strong></a></p>

""".format(release=stripped_release)

# A shortcut for linking to tickets on the GitHub issue tracker
extlinks = {
    'blob': ('https://github.com/saltstack/salt/blob/%s/%%s' % repo_primary_branch, None),
    'issue': ('https://github.com/saltstack/salt/issues/%s', 'issue #'),
    'pull': ('https://github.com/saltstack/salt/pull/%s', 'PR #'),
    'formula_url': ('https://github.com/saltstack-formulas/%s', ''),
}


# ----- Localization -------------------------------------------------------->
locale_dirs = ['locale/']
gettext_compact = False
# <---- Localization ---------------------------------------------------------


### HTML options
# set 'HTML_THEME=saltstack' to use previous theme
html_theme = os.environ.get('HTML_THEME', 'saltstack2')
html_theme_path = ['_themes']
html_title = u''
html_short_title = 'Salt'

html_static_path = ['_static']
html_logo = None # specified in the theme layout.html
html_favicon = 'favicon.ico'
smartquotes = False

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
    'latest_release': latest_release,
    'previous_release': previous_release,
    'previous_release_dir': previous_release_dir,
    'next_release': next_release,
    'next_release_dir': next_release_dir,
    'search_cx': search_cx,
    'build_type': build_type,
    'today': today,
    'copyright': copyright,
    'repo_primary_branch': repo_primary_branch
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

latex_logo = '_static/salt-logo.png'

latex_elements = {
    'inputenc': '',     # use XeTeX instead of the inputenc LaTeX package.
    'utf8extra': '',
    'preamble': r'''
    \usepackage{fontspec}
    \setsansfont{Linux Biolinum O}
    \setromanfont{Linux Libertine O}
    \setmonofont{Source Code Pro}
''',
}
### Linux Biolinum, Linux Libertine: http://www.linuxlibertine.org/
### Source Code Pro: https://github.com/adobe-fonts/source-code-pro/releases


### Linkcheck options
linkcheck_ignore = [
    r'http://127.0.0.1',
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
    r'https://raven.readthedocs.io',
    r'https://getsentry.com',
    r'https://salt-cloud.readthedocs.io',
    r'https://salt.readthedocs.io',
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
    r'dash-feed://https%3A//media.readthedocs.org/dash/salt/latest/salt.xml',
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
    ('ref/cli/salt-proxy', 'salt-proxy', 'salt-proxy Documentation', authors, 1),
    ('ref/cli/salt-syndic', 'salt-syndic', 'salt-syndic Documentation', authors, 1),
    ('ref/cli/salt-run', 'salt-run', 'salt-run Documentation', authors, 1),
    ('ref/cli/salt-ssh', 'salt-ssh', 'salt-ssh Documentation', authors, 1),
    ('ref/cli/salt-cloud', 'salt-cloud', 'Salt Cloud Command', authors, 1),
    ('ref/cli/salt-api', 'salt-api', 'salt-api Command', authors, 1),
    ('ref/cli/salt-unity', 'salt-unity', 'salt-unity Command', authors, 1),
    ('ref/cli/spm', 'spm', 'Salt Package Manager Command', authors, 1),
]


### epub options
epub_title = 'Salt Documentation'
epub_author = 'SaltStack, Inc.'
epub_publisher = epub_author
epub_copyright = copyright

epub_scheme = 'URL'
epub_identifier = 'http://saltstack.com/'

epub_tocdup = False
#epub_tocdepth = 3


def skip_mod_init_member(app, what, name, obj, skip, options):
    # pylint: disable=too-many-arguments,unused-argument
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
