# -*- coding: utf-8 -*-
# pylint: disable=C0103,W0622
'''
Sphinx documentation for salt-api
'''
import os
import sys

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
    def __getattr__(cls, name):
        if name in ('__file__', '__path__'):
            return '/dev/null'
        else:
            return Mock()
# pylint: enable=R0903

MOCK_MODULES = [
    # third-party libs (for netapi modules)
    'flask',
    'flask.globals',
    'flask.views',
    'werkzeug',
    'werkzeug.exceptions',
    'cheroot.ssllib',
    'cheroot.ssllib.ssl_builtin',

    'cheroot',
    'cheroot.wsgi',
    'cherrypy',
    'cherrypy.lib',
    'cherrypy.wsgiserver',
    'cherrypy.wsgiserver.ssl_builtin',

    'tornado',
    'tornado.concurrent',
    'tornado.gen',
    'tornado.httpserver',
    'tornado.ioloop',
    'tornado.web',

    'yaml',
    'zmq',

    # salt libs
    'salt',
    'salt.auth',
    'salt.client',
    'salt.exceptions',
    'salt.log',
    'salt.output',
    'salt.runner',
    'salt.utils',
    'salt.utils.event',
    'salt.wheel',
]

for mod_name in MOCK_MODULES:
    sys.modules[mod_name] = Mock()


# -- Add paths to PYTHONPATH ---------------------------------------------------

docs_basepath = os.path.abspath(os.path.dirname(__file__))
addtl_paths = (
    os.pardir, # salt-api itself (for autodoc/autohttp)
    '_ext', # custom Sphinx extensions
)

for path in addtl_paths:
    sys.path.insert(0, os.path.abspath(os.path.join(docs_basepath, path)))

from saltapi.version import __version__


on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

# -- General configuration -----------------------------------------------------

project = 'salt-api'
copyright = '2012, Thomas S. Hatch'

version = __version__
release = version

master_doc = 'index'
templates_path = ['_templates']
exclude_patterns = ['_build']

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'sphinxcontrib.httpdomain',
    'sphinxcontrib.autohttp.flask',
]

modindex_common_prefix = ['saltapi.']

autosummary_generate = True

intersphinx_mapping = {
    'salt': ('http://docs.saltstack.org/en/latest/', None),
}

### HTML options
html_theme = 'default'

html_title = None
html_short_title = 'salt-api'

html_static_path = ['_static']
html_logo = 'salt-vert.png'
html_favicon = 'favicon.ico'
html_use_smartypants = False

html_use_index = True
html_last_updated_fmt = '%b %d, %Y'
html_show_sourcelink = False
html_show_sphinx = True
html_show_copyright = True
#html_use_opensearch = ''


### Latex options
latex_documents = [
    ('index', 'salt-api.tex', 'salt-api Documentation', 'Thomas Hatch', 'manual'),
]

latex_logo = '_static/salt-vert.png'


### Manpage options
# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
authors = [
    'Thomas S. Hatch <thatch45@gmail.com> and many others, please see the Authors file',
]

man_pages = [
    ('ref/cli/salt-api', 'salt-api', 'salt-api', authors, 1),
    ('index', 'salt-api', 'salt-api Documentation', authors, 7),
]


### epub options
epub_title = 'salt-api Documentation'
epub_author = 'Thomas S. Hatch'
epub_publisher = epub_author
epub_copyright = '2012, Thomas S. Hatch'

epub_scheme = 'URL'
epub_identifier = 'http://saltstack.org/'

#epub_tocdepth = 3

###############################################################################

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
    # Copy ReleasesTree directive from Salt for properly sorting release
    # numbers with glob
    app.add_directive('releasestree', ReleasesTree)
    # Copy crossref types from Salt for master/minion conf files
    app.add_crossref_type(directivename="conf_master", rolename="conf_master",
            indextemplate="pair: %s; conf/master")
    app.add_crossref_type(directivename="conf_minion", rolename="conf_minion",
            indextemplate="pair: %s; conf/minion")
