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
from salt.utils.yamlutil import anchored_dump
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


    YAML filter accepts an anchored param, in order to anchors
    the whole document. For example:

    .. code-block:: jinja

        defaults: {{ data|yaml(anchored("FOO")) }}
        development:
            <<: *FOO
            is it nice?: yes

    will be rendered has::

        defaults = &FOO {bar: 42, baz: &FOO__baz [1, 2, 3]}
        development:
            <<: *FOO
            is it nice?: yes

    and exposed to salt machinery as:

    .. code-block:: python
        states = {
            'defaults': {
                'foo': True,
                'bar': 42,
                'baz': [1, 2, 3],
                'qux': 2.0
            },
            'development': {
                'foo': True,
                'bar': 42,
                'baz': [1, 2, 3],
                'qux': 2.0,
                'is it nice?': yes
            },
        }

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

        {% load "state1.sls" as state1 %}
        {% load_yaml "state2.sls" as state2 %}
        {% load_json "state3.sls" as state3 %}

    '''

    tags = set(['load', 'load_yaml', 'load_json'])

    def __init__(self, environment):
        super(SerializerExtension, self).__init__(environment)
        self.environment.filters.update({
            'yaml': self.format_yaml,
            'json': self.format_json,
            'load_yaml': self.load_yaml,
            'load_json': self.load_json
        })

    def format_json(self, value, *args, **kwargs):
        return Markup(json.dumps(value, sort_keys=True).strip())

    def format_yaml(self, value, anchored=False, *args, **kwargs):
        if anchored:
            if isinstance(anchored, string_types):
                top_anchor = anchored
            else:
                top_anchor = None
            dumped = anchored_dump(value, top_anchor=top_anchor, include_document=True, default_flow_style=True).strip()
        else:
            dumped = yaml.dump(value, default_flow_style=True).strip()
        return Markup(dumped)

    def load_yaml(self, value):
        if isinstance(value, TemplateModule):
            value = str(value)
        try:
            return yaml.load(value)
        except AttributeError:
            raise TemplateRuntimeError("Unable to load yaml from {}".format(value))

    def load_json(self, value):
        if isinstance(value, TemplateModule):
            value = str(value)
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            raise TemplateRuntimeError("Unable to load json from {}".format(value))

    def parse(self, parser):
        if parser.stream.current.value in ("load", "load_yaml"):
            return self.parse_yaml(parser)
        elif parser.stream.current.value == "load_json":
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
