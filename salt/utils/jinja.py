# -*- coding: utf-8 -*-
'''
Jinja loading utils to enable a more powerful backend for jinja templates
'''

# Import python libs
from __future__ import absolute_import
import json
import pprint
import logging
from os import path
from functools import wraps

# Import third party libs
import salt.ext.six as six
from jinja2 import BaseLoader, Markup, TemplateNotFound, nodes
from jinja2.environment import TemplateModule
from jinja2.ext import Extension
from jinja2.exceptions import TemplateRuntimeError
import jinja2
import yaml

# Import salt libs
import salt
import salt.utils
import salt.utils.url
import salt.fileclient
from salt.utils.odict import OrderedDict

log = logging.getLogger(__name__)

__all__ = [
    'SaltCacheLoader',
    'SerializerExtension'
]


# To dump OrderedDict objects as regular dicts. Used by the yaml
# template filter.
class OrderedDictDumper(yaml.Dumper):  # pylint: disable=W0232
    pass


yaml.add_representer(OrderedDict,
                     yaml.representer.SafeRepresenter.represent_dict,
                     Dumper=OrderedDictDumper)


class SaltCacheLoader(BaseLoader):
    '''
    A special jinja Template Loader for salt.
    Requested templates are always fetched from the server
    to guarantee that the file is up to date.
    Templates are cached like regular salt states
    and only loaded once per loader instance.
    '''
    def __init__(self, opts, saltenv='base', encoding='utf-8',
                 pillar_rend=False):
        self.opts = opts
        self.saltenv = saltenv
        self.encoding = encoding
        if self.opts['file_roots'] is self.opts['pillar_roots']:
            self.searchpath = opts['file_roots'][saltenv]
        else:
            self.searchpath = [path.join(opts['cachedir'], 'files', saltenv)]
        log.debug('Jinja search path: %s', self.searchpath)
        self._file_client = None
        self.cached = []
        self.pillar_rend = pillar_rend

    def file_client(self):
        '''
        Return a file client. Instantiates on first call.
        '''
        if not self._file_client:
            self._file_client = salt.fileclient.get_file_client(
                self.opts, self.pillar_rend)
        return self._file_client

    def cache_file(self, template):
        '''
        Cache a file from the salt master
        '''
        saltpath = salt.utils.url.create(template)
        self.file_client().get_file(saltpath, '', True, self.saltenv)

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

        if environment and template:
            tpldir = path.dirname(template).replace('\\', '/')
            tpldata = {
                'tplfile': template,
                'tpldir': '.' if tpldir == '' else tpldir,
                'tpldot': tpldir.replace('/', '.'),
            }
            environment.globals.update(tpldata)

        # pylint: disable=cell-var-from-loop
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
        # pylint: enable=cell-var-from-loop

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
        for key, value in six.iteritems(self):
            if isinstance(value, six.string_types):
                # keeps quotes around strings
                output.append('{0!r}: {1!r}'.format(key, value))  # pylint: disable=repr-flag-used-in-string
            else:
                # let default output
                output.append('{0!r}: {1!s}'.format(key, value))  # pylint: disable=repr-flag-used-in-string
        return '{' + ', '.join(output) + '}'

    def __repr__(self):  # pylint: disable=W0221
        output = []
        for key, value in six.iteritems(self):
            # Raw string formatter required here because this is a repr
            # function.
            output.append('{0!r}: {1!r}'.format(key, value))  # pylint: disable=repr-flag-used-in-string
        return '{' + ', '.join(output) + '}'


def ensure_sequence_filter(data):
    '''
    Ensure sequenced data.

    **sequence**

        ensure that parsed data is a sequence

    .. code-block:: yaml

        {% set my_string = "foo" %}
        {% set my_list = ["bar", ] %}
        {% set my_dict = {"baz": "qux"} %}

        {{ my_string|sequence|first }}
        {{ my_list|sequence|first }}
        {{ my_dict|sequence|first }}


    will be rendered as:

    .. code-block:: yaml

        foo
        bar
        baz
    '''
    if not isinstance(data, (list, tuple, set, dict)):
        return [data]
    return data


@jinja2.contextfunction
def show_full_context(ctx):
    return ctx


class SerializerExtension(Extension, object):
    '''
    Yaml and Json manipulation.

    **Format filters**

    Allows jsonifying or yamlifying any data structure. For example, this dataset:

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
        python = {{ data|python }}

    will be rendered as::

        yaml = {bar: 42, baz: [1, 2, 3], foo: true, qux: 2.0}
        json = {"baz": [1, 2, 3], "foo": true, "bar": 42, "qux": 2.0}
        python = {'bar': 42, 'baz': [1, 2, 3], 'foo': True, 'qux': 2.0}

    The yaml filter takes an optional flow_style parameter to control the
    default-flow-style parameter of the YAML dumper.

    .. code-block:: jinja

        {{ data|yaml(False) }}

    will be rendered as:

    .. code-block:: yaml

        bar: 42
        baz:
          - 1
          - 2
          - 3
        foo: true
        qux: 2.0

    **Load filters**

    Strings and variables can be deserialized with **load_yaml** and
    **load_json** tags and filters. It allows one to manipulate data directly
    in templates, easily:

    .. code-block:: jinja

        {%- set yaml_src = "{foo: it works}"|load_yaml %}
        {%- set json_src = "{'bar': 'for real'}"|load_json %}
        Dude, {{ yaml_src.foo }} {{ json_src.bar }}!

    will be rendered as::

        Dude, it works for real!

    **Load tags**

    Salt implements ``load_yaml`` and ``load_json`` tags. They work like
    the `import tag`_, except that the document is also deserialized.

    Syntaxes are ``{% load_yaml as [VARIABLE] %}[YOUR DATA]{% endload %}``
    and ``{% load_json as [VARIABLE] %}[YOUR DATA]{% endload %}``

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

    will be rendered as::

        Dude, it works for real!

    **Import tags**

    External files can be imported and made available as a Jinja variable.

    .. code-block:: jinja

        {% import_yaml "myfile.yml" as myfile %}
        {% import_json "defaults.json" as defaults %}
        {% import_text "completeworksofshakespeare.txt" as poems %}

    **Catalog**

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

    .. _`import tag`: http://jinja.pocoo.org/docs/templates/#import
    '''

    tags = set(['load_yaml', 'load_json', 'import_yaml', 'import_json',
                'load_text', 'import_text'])

    def __init__(self, environment):
        super(SerializerExtension, self).__init__(environment)
        self.environment.filters.update({
            'yaml': self.format_yaml,
            'json': self.format_json,
            'python': self.format_python,
            'load_yaml': self.load_yaml,
            'load_json': self.load_json,
            'load_text': self.load_text,
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
                return PrintableDict(
                    [(key, explore(value)) for key, value in six.iteritems(data)]
                )
            elif isinstance(data, (list, tuple, set)):
                return data.__class__([explore(value) for value in data])
            return data
        return explore(data)

    def format_json(self, value, sort_keys=True, indent=None):
        return Markup(json.dumps(value, sort_keys=sort_keys, indent=indent).strip())

    def format_yaml(self, value, flow_style=True):
        yaml_txt = yaml.dump(value, default_flow_style=flow_style,
                             Dumper=OrderedDictDumper).strip()
        if yaml_txt.endswith('\n...'):
            yaml_txt = yaml_txt[:len(yaml_txt)-4]
        return Markup(yaml_txt)

    def format_python(self, value):
        return Markup(pprint.pformat(value).strip())

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

    def load_text(self, value):
        if isinstance(value, TemplateModule):
            value = str(value)

        return value

    _load_parsers = set(['load_yaml', 'load_json', 'load_text'])

    def parse(self, parser):
        if parser.stream.current.value == 'import_yaml':
            return self.parse_yaml(parser)
        elif parser.stream.current.value == 'import_json':
            return self.parse_json(parser)
        elif parser.stream.current.value == 'import_text':
            return self.parse_text(parser)
        elif parser.stream.current.value in self._load_parsers:
            return self.parse_load(parser)

        parser.fail('Unknown format ' + parser.stream.current.value,
                    parser.stream.current.lineno)

    # pylint: disable=E1120,E1121
    def parse_load(self, parser):
        filter_name = parser.stream.current.value
        lineno = next(parser.stream).lineno
        if filter_name not in self.environment.filters:
            parser.fail('Unable to parse {0}'.format(filter_name), lineno)

        parser.stream.expect('name:as')
        target = parser.parse_assign_target()
        macro_name = '_' + parser.free_identifier().name
        macro_body = parser.parse_statements(
            ('name:endload',), drop_needle=True)

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

    def parse_text(self, parser):
        import_node = parser.parse_import()
        target = import_node.target
        lineno = import_node.lineno

        return [
            import_node,
            nodes.Assign(
                nodes.Name(target, 'store').set_lineno(lineno),
                nodes.Filter(
                    nodes.Name(target, 'load').set_lineno(lineno),
                    'load_text',
                    [],
                    [],
                    None,
                    None
                )
                .set_lineno(lineno)
            ).set_lineno(lineno)
        ]
    # pylint: enable=E1120,E1121
