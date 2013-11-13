# -*- coding: utf-8 -*-
'''
Jinja loading utils to enable a more powerful backend for jinja templates
'''

# Import python libs
from os import path
import logging
import json
from functools import wraps

# Import third party libs
from jinja2 import BaseLoader, Markup, TemplateNotFound, nodes
from jinja2.environment import TemplateModule
from jinja2.ext import Extension
from jinja2.exceptions import TemplateRuntimeError
import yaml

# Import salt libs
import salt
import salt.fileclient
from salt.utils.odict import OrderedDict
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


class PrintableDict(OrderedDict):
    '''
    Ensures that dict str() and repr() are YAML friendly.

    .. code-block:: python
        mapping = OrderedDict([('a', 'b'), ('c', None)])
        print mapping
        # OrderedDict([('a', 'b'), ('c', None)])

        decorated = PrintableDict(mapping)
        print decorated
        # {'a': 'b', 'c': None}

    '''
    def __str__(self):
        output = []
        for key, value in self.items():
            if isinstance(value, string_types):
                # keeps quotes around strings
                output.append('{0!r}: {1!r}'.format(key, value))
            else:
                # let default output
                output.append('{0!r}: {1!s}'.format(key, value))
        return '{' + ', '.join(output) + '}'

    def __repr__(self):  # pylint: disable=W0221
        output = []
        for key, value in self.items():
            output.append('{0!r}: {1!r}'.format(key, value))
        return '{' + ', '.join(output) + '}'


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

    Load tags
    ~~~~~~~~~

    Like the load filters, it parses blocks with the selected serializer,
    and assign it to the relevant variable

    Syntaxe are {% load_yaml as [VARIABLE] %}[YOUR DATA]{% endload %}
    and {% load_json as [VARIABLE] %}[YOUR DATA]{% endload %}

    For example:

    .. code-block:: jinja

        {% load_yaml as yaml_src %}
            foo: it works
        {% endload %}
        {% load_json as json_src %}
            {
                "bar": "for real"
            }
        {% endload %}
        Dude, {{ yaml_src.foo }} {{ json_src.bar }}!

    will be rendered has::

        Dude, it works for real!

    Import tags
    ~~~~~~~~~~~

    You can also import template and decode them automatically.

    Syntaxe are {% import_yaml [TEMPLATE_NAME] as [VARIABLE] %}
    and {% import_json [TEMPLATE_NAME] as [VARIABLE] %}

    .. code-block:: jinja

        {% import_yaml "state2.sls" as state2 %}
        {% import_json "state3.sls" as state3 %}

    Catalog
    ~~~~~~~

    ``import_*`` and ``load_*`` tags will automatically expose their
    target variable to import. This feature makes catalog of data to
    handle.

    for example:

    .. code-block:: jinja
        # doc1.sls
        {% load_yaml as var1 %}
            foo: it works
        {% endload %}
        {% load_yaml as var2 %}
            bar: for real
        {% endload %}

    .. code-block:: jinja
        # doc2.sls
        {% from "doc1.sls" import var1, var2 as local2 %}
        {{ var1.foo }} {{ local2.bar }}

    '''

    tags = set(['load_yaml', 'load_json', 'import_yaml', 'import_json'])

    def __init__(self, environment):
        super(SerializerExtension, self).__init__(environment)
        self.environment.filters.update({
            'yaml': self.format_yaml,
            'json': self.format_json,
            'load_yaml': self.load_yaml,
            'load_json': self.load_json
        })

        if self.environment.finalize is None:
            self.environment.finalize = self.finalizer
        else:
            finalizer = self.environment.finalize

            @wraps(finalizer)
            def wrapper(self, data):
                return finalizer(self.finalizer(data))
            self.environment.finalize = wrapper

    def finalizer(self, data):
        '''
        Ensure that printed mappings are YAML friendly.
        '''
        def explore(data):
            if isinstance(data, (dict, OrderedDict)):
                return PrintableDict([(key, explore(value)) for key, value in data.items()])
            elif isinstance(data, (list, tuple, set)):
                return data.__class__([explore(value) for value in data])
            return data
        return explore(data)

    def format_json(self, value):
        return Markup(json.dumps(value, sort_keys=True).strip())

    def format_yaml(self, value):
        return Markup(yaml.dump(value, default_flow_style=True).strip())

    def load_yaml(self, value):
        if isinstance(value, TemplateModule):
            value = str(value)
        try:
            return yaml.safe_load(value)
        except AttributeError:
            raise TemplateRuntimeError(
                    'Unable to load yaml from {0}'.format(value))

    def load_json(self, value):
        if isinstance(value, TemplateModule):
            value = str(value)
        try:
            return json.loads(value)
        except (ValueError, TypeError, AttributeError):
            raise TemplateRuntimeError(
                    'Unable to load json from {0}'.format(value))

    def parse(self, parser):
        if parser.stream.current.value == 'import_yaml':
            return self.parse_yaml(parser)
        elif parser.stream.current.value == 'import_json':
            return self.parse_json(parser)
        elif parser.stream.current.value in ('load_yaml', 'load_json'):
            return self.parse_load(parser)

        parser.fail('Unknown format ' + parser.stream.current.value,
                    parser.stream.current.lineno)

    def parse_load(self, parser):
        filter_name = parser.stream.current.value
        lineno = next(parser.stream).lineno
        if filter_name not in self.environment.filters:
            parser.fail('Unable to parse {0}'.format(filter_name), lineno)

        parser.stream.expect('name:as')
        target = parser.parse_assign_target()
        macro_name = '_' + parser.free_identifier().name
        macro_body = parser.parse_statements(('name:endload',),
                                          drop_needle=True)

        return [
            nodes.Macro(
                macro_name,
                [],
                [],
                macro_body
            ).set_lineno(lineno),
            nodes.Assign(
                target,
                nodes.Filter(
                    nodes.Call(
                        nodes.Name(macro_name, 'load').set_lineno(lineno),
                        [],
                        [],
                        None,
                        None
                    ).set_lineno(lineno),
                    filter_name,
                    [],
                    [],
                    None,
                    None
                ).set_lineno(lineno)
            ).set_lineno(lineno)
        ]

    def parse_yaml(self, parser):
        import_node = parser.parse_import()
        target = import_node.target
        lineno = import_node.lineno

        return [
            import_node,
            nodes.Assign(
                nodes.Name(target, 'store').set_lineno(lineno),
                nodes.Filter(
                    nodes.Name(target, 'load').set_lineno(lineno),
                    'load_yaml',
                    [],
                    [],
                    None,
                    None
                )
                .set_lineno(lineno)
            ).set_lineno(lineno)
        ]

    def parse_json(self, parser):
        import_node = parser.parse_import()
        target = import_node.target
        lineno = import_node.lineno

        return [
            import_node,
            nodes.Assign(
                nodes.Name(target, 'store').set_lineno(lineno),
                nodes.Filter(
                    nodes.Name(target, 'load').set_lineno(lineno),
                    'load_json',
                    [],
                    [],
                    None,
                    None
                )
                .set_lineno(lineno)
            ).set_lineno(lineno)
        ]
