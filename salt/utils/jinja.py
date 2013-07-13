'''
Jinja loading utils to enable a more powerful backend for jinja templates
'''

# Import python libs
from os import path
import logging
from functools import partial
import json

# Import third party libs
from jinja2 import BaseLoader, Markup, TemplateNotFound
from jinja2.ext import Extension
import yaml

# Import salt libs
import salt
import salt.fileclient

log = logging.getLogger(__name__)

__all__ = [
    'SaltCacheLoader',
    'SerializerExtension'
]


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
        if opts.get('file_client', 'remote') == 'local':
            self.searchpath = opts['file_roots'][env]
        else:
            self.searchpath = [path.join(opts['cachedir'], 'files', env)]
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
        for spath in self.searchpath:
            filepath = path.join(spath, template)
            try:
                with salt.utils.fopen(filepath, 'rb') as ifile:
                    contents = ifile.read().decode(self.encoding)
                    mtime = path.getmtime(filepath)

                    def uptodate():
                        try:
                            return path.getmtime(filepath) == mtime
                        except OSError:
                            return False
                    return contents, filepath, uptodate
            except IOError:
                # there is no file under current path
                continue
        # there is no template file within searchpaths
        raise TemplateNotFound(template)


class SerializerExtension(Extension):
    '''
    Serializes variables.

    For example, this dataset:

    .. code-block:: python

        data = {
            'foo': True,
            'bar': 42,
            'baz': [1, 2, 3],
            'qux': 2.0
        }

    .. code-block:: jinja

        yaml = {{ data|yaml }}
        json = {{ data|json }}

    will be rendered has::

        yaml = {bar: 42, baz: [1, 2, 3], foo: true, qux: 2.0}
        json = {"baz": [1, 2, 3], "foo": true, "bar": 42, "qux": 2.0}

    '''

    def __init__(self, environment):
        Extension.__init__(self, environment)
        self.environment.filters.update({
            'yaml': partial(self.format, formatter='yaml'),
            'json': partial(self.format, formatter='json')
        })

    def format(self, value, formatter, *args, **kwargs):
        if formatter == 'json':
            return Markup(json.dumps(value, sort_keys=True))
        elif formatter == 'yaml':
            return Markup(yaml.dump(value, default_flow_style=True))
        raise ValueError('Serializer {0} is not implemented'.format(formatter))

    def parse(self, parser):
        '''
        If called this method would throw ``NotImplementedError``.
        While we don't need to implement this method, we override it so pylint
        does not complain about an abstract method not implemented
        '''
