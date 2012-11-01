'''
Jinja loading utils to enable a more powerful backend for jinja templates
'''
# Import python libs
from os import path
import logging

# Import third-party libs
from jinja2 import (BaseLoader, Environment, StrictUndefined,
                    FileSystemLoader)
from jinja2.exceptions import TemplateNotFound

# Import Salt libs
import salt
import salt.fileclient


log = logging.getLogger(__name__)


def get_template(filename, opts, env):
    loader = SaltCacheLoader(opts, env)
    if filename.startswith(loader.searchpath):
        if opts.get('allow_undefined', False):
            jinja = Environment(loader=loader)
        else:
            jinja = Environment(loader=loader, undefined=StrictUndefined)
        relpath = path.relpath(filename, loader.searchpath)
        # the template was already fetched
        loader.cached.append(relpath)
        return jinja.get_template(relpath)
    else:
        # fallback for templates outside the state tree
        loader = FileSystemLoader(path.dirname(filename))
        if opts.get('allow_undefined', False):
            jinja = Environment(loader=loader)
        else:
            jinja = Environment(loader=loader, undefined=StrictUndefined)
        relpath = path.relpath(filename, path.dirname(filename))
        return jinja.get_template(relpath)


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
        log.debug('Jinja search path: \'{0}\''.format(self.searchpath))
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
        if '..' in template:
            log.warning(
                'Discarded template path \'{0}\', relative paths are '
                'prohibited'.format(template)
            )
            raise TemplateNotFound(template)
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
