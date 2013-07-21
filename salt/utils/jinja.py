'''
Jinja loading utils to enable a more powerful backend for jinja templates
'''

# Import python libs
from os import path
import logging
import json

# Import third party libs
from jinja2 import BaseLoader, Markup, TemplateNotFound, nodes
from jinja2.environment import TemplateModule
from jinja2.ext import Extension
from jinja2.exceptions import TemplateRuntimeError
import yaml

# Import salt libs
import salt
import salt.fileclient
from salt._compat import string_types

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


class SerializerExtension(Extension, object):
    '''
    Yaml and Json manipulation.

    Format filters
    ~~~~~~~~~~~~~~

    Allows to jsonify or yamlify any datastructure. For example, this dataset:

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

    Load filters
    ~~~~~~~~~~~~

    Parse strings variable with the selected serializer:

    .. code-block:: jinja

        {%- set yaml_src = "{foo: it works}"|load_yaml %}
        {%- set json_src = "{'bar': 'for real'}"|load_yaml %}
        Dude, {{ yaml_src.foo }} {{ json_src.bar }}!

    will be rendered has::

        Dude, it works for real!

    Template tags
    ~~~~~~~~~~~~~

    .. code-block:: jinja

        {% import_yaml "state2.sls" as state2 %}
        {% import_json "state3.sls" as state3 %}

    '''

    tags = set(['import_yaml', 'import_json'])

    def __init__(self, environment):
        super(SerializerExtension, self).__init__(environment)
        self.environment.filters.update({
            'yaml': self.format_yaml,
            'json': self.format_json,
            'load_yaml': self.load_yaml,
            'load_json': self.load_json
        })

    def format_json(self, value):
        return Markup(json.dumps(value, sort_keys=True).strip())

    def format_yaml(self, value):
        return Markup(yaml.dump(value, default_flow_style=True).strip())

    def load_yaml(self, value):
        if isinstance(value, TemplateModule):
            value = str(value)
        try:
            return yaml.load(value)
        except AttributeError:
            raise TemplateRuntimeError("Unable to load yaml from {0}".format(value))

    def load_json(self, value):
        if isinstance(value, TemplateModule):
            value = str(value)
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            raise TemplateRuntimeError("Unable to load json from {0}".format(value))

    def parse(self, parser):
        if parser.stream.current.value == "import_yaml":
            return self.parse_yaml(parser)
        elif parser.stream.current.value == "import_json":
            return self.parse_json(parser)

        parser.fail('Unknown format ' + parser.stream.current.value,
                    parser.stream.current.lineno)

    def parse_yaml(self, parser):
        # import the document
        node_import = parser.parse_import()
        target = node_import.target

        # cleanup the remaining nodes
        while parser.stream.current.type != 'block_end':
            parser.stream.next()

        node_filter = nodes.Assign(
                            nodes.Name(target, 'load'),
                            self.call_method(
                                'load_yaml',
                                [nodes.Name(target, 'load')]
                            )
                        ).set_lineno(
                            parser.stream.current.lineno
                        )

        return [
            node_import,
            node_filter
        ]


    def parse_json(self, parser):
        # import the document
        node_import = parser.parse_import()
        target = node_import.target


        node_filter = nodes.Assign(
                            nodes.Name(target, 'load'),
                            self.call_method(
                                'load_yaml',
                                [nodes.Name(target, 'load')]
                            )
                        ).set_lineno(
                            parser.stream.current.lineno
                        )

        # cleanup the remaining nodes
        while parser.stream.current.type != 'block_end':
            parser.stream.next()

        return [
            node_import,
            node_filter,
        ]
