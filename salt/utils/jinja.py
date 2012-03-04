'''
Jinja loading utils to enable a more powerful backend for jinja templates
'''
# Import python libs
from os import path

# Import third-party libs
from jinja2 import Template, BaseLoader, Environment
from jinja2.loaders import split_template_path
from jinja2.exceptions import TemplateNotFound

# Import Salt libs
import salt
import salt.fileclient


def get_template(filename, opts, env):
    loader = SaltCacheLoader(opts, env)
    if filename.startswith(loader.searchpath):
        jinja = Environment(loader=loader)
        relpath = path.relpath(filename, loader.searchpath)
        # the template was already fetched
        loader.cached.append(relpath)
        return jinja.get_template(relpath)
    else:
        # fallback for templates outside the state tree
        with open(filename, 'r') as f:
            return Template(f.read())


class SaltCacheLoader(BaseLoader):
    '''
    A special jinja Template Loader for salt.
    Requested templates are always fetched from the server
    to guarantee that the file is up to date.
    Templates are cached like regular salt states
    and only loaded once per loader instance.
    '''
    def __init__(self, opts, env='base', encoding='utf-8'):
        self.opts = opts
        self.env = env
        self.encoding = encoding
        self.searchpath = path.join(opts['cachedir'], 'files', env)
        self._file_client = None
        self.cached = []

    def file_client(self):
        '''
        Return a file client. Instantiates on first call.
        '''
        if not self._file_client:
            self._file_client = salt.fileclient.get_file_client(self.opts)
        return self._file_client

    def cache_file(self, template):
        '''
        Cache a file from the salt master
        '''
        saltpath = path.join('salt://', template)
        self.file_client().get_file(saltpath, '', True, self.env)

    def check_cache(self, template):
        '''
        Cache a file only once
        '''
        if template not in self.cached:
            self.cache_file(template)
            self.cached.append(template)

    def get_source(self, environment, template):
        # checks for relative '..' paths
        template = path.join(*split_template_path(template))
        self.check_cache(template)
        filepath = path.join(self.searchpath, template)
        with open(filepath, 'rb') as f:
            try:
                contents = f.read().decode(self.encoding)
            except IOError:
                raise TemplateNotFound(template)
        mtime = path.getmtime(filepath)

        def uptodate():
            try:
                return path.getmtime(filepath) == mtime
            except OSError:
                return False
        return contents, filepath, uptodate
