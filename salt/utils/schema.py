# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


    salt.utils.schema
    ~~~~~~~~~~~~~~~~~

    Object Oriented Configuration - JSON Schema compatible generator

    This code was inspired by `jsl`__, "A Python DSL for describing JSON
    schemas".

    .. __: http://jsl.readthedocs.org/


    A configuration document or configuration document section is defined using
    the py:class:`Schema`, the configuration items are defined by any of the
    subclasses of py:class:`BaseSchemaItem` as attributes of a subclass of
    py:class:`Schema` class.

    As an example:

    .. code-block:: python

        class HostConfig(Schema):
            title = 'Host Configuration'
            description = 'This is the host configuration'

            host = StringItem(
                'Host',
                'The looong host description',
                default=None,
                minimum=1
            )

            port = NumberItem(
                description='The port number',
                default=80,
                required=False,
                minimum=0,
                inclusiveMinimum=False,
                maximum=65535
            )

    The serialized version of the above configuration definition is:

    .. code-block:: python

        >>> print(HostConfig.serialize())
        OrderedDict([
            ('$schema', 'http://json-schema.org/draft-04/schema#'),
            ('title', 'Host Configuration'),
            ('description', 'This is the host configuration'),
            ('type', 'object'),
            ('properties', OrderedDict([
                ('host', {'minimum': 1,
                          'type': 'string',
                          'description': 'The looong host description',
                          'title': 'Host'}),
                ('port', {'description': 'The port number',
                          'default': 80,
                          'inclusiveMinimum': False,
                          'maximum': 65535,
                          'minimum': 0,
                          'type': 'number'})
            ])),
            ('required', ['host']),
            ('x-ordering', ['host', 'port']),
            ('additionalProperties', True)]
        )
        >>> print(json.dumps(HostConfig.serialize(), indent=2))
        {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "title": "Host Configuration",
            "description": "This is the host configuration",
            "type": "object",
            "properties": {
                "host": {
                    "minimum": 1,
                    "type": "string",
                    "description": "The looong host description",
                    "title": "Host"
                },
                "port": {
                    "description": "The port number",
                    "default": 80,
                    "inclusiveMinimum": false,
                    "maximum": 65535,
                    "minimum": 0,
                    "type": "number"
                }
            },
            "required": [
                "host"
            ],
            "x-ordering": [
                "host",
                "port"
            ],
            "additionalProperties": false
        }


    The serialized version of the configuration block can be used to validate a
    configuration dictionary using the `python jsonschema library`__.

    .. __: https://pypi.python.org/pypi/jsonschema

    .. code-block:: python

        >>> import jsonschema
        >>> jsonschema.validate({'host': 'localhost', 'port': 80}, HostConfig.serialize())
        >>> jsonschema.validate({'host': 'localhost', 'port': -1}, HostConfig.serialize())
        Traceback (most recent call last):
        File "<stdin>", line 1, in <module>
        File "/usr/lib/python2.7/site-packages/jsonschema/validators.py", line 478, in validate
            cls(schema, *args, **kwargs).validate(instance)
        File "/usr/lib/python2.7/site-packages/jsonschema/validators.py", line 123, in validate
            raise error
        jsonschema.exceptions.ValidationError: -1 is less than the minimum of 0

        Failed validating 'minimum' in schema['properties']['port']:
            {'default': 80,
            'description': 'The port number',
            'inclusiveMinimum': False,
            'maximum': 65535,
            'minimum': 0,
            'type': 'number'}

        On instance['port']:
            -1
        >>>


    A configuration document can even be split into configuration sections. Let's reuse the above
    ``HostConfig`` class and include it in a configuration block:

    .. code-block:: python

        class LoggingConfig(Schema):
            title = 'Logging Configuration'
            description = 'This is the logging configuration'

            log_level = StringItem(
                'Logging Level',
                'The logging level',
                default='debug',
                minimum=1
            )

        class MyConfig(Schema):

            title = 'My Config'
            description = 'This my configuration'

            hostconfig = HostConfig()
            logconfig = LoggingConfig()


    The JSON Schema string version of the above is:

    .. code-block:: python

        >>> print json.dumps(MyConfig.serialize(), indent=4)
        {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "title": "My Config",
            "description": "This my configuration",
            "type": "object",
            "properties": {
                "hostconfig": {
                    "id": "https://non-existing.saltstack.com/schemas/hostconfig.json#",
                    "title": "Host Configuration",
                    "description": "This is the host configuration",
                    "type": "object",
                    "properties": {
                        "host": {
                            "minimum": 1,
                            "type": "string",
                            "description": "The looong host description",
                            "title": "Host"
                        },
                        "port": {
                            "description": "The port number",
                            "default": 80,
                            "inclusiveMinimum": false,
                            "maximum": 65535,
                            "minimum": 0,
                            "type": "number"
                        }
                    },
                    "required": [
                        "host"
                    ],
                    "x-ordering": [
                        "host",
                        "port"
                    ],
                    "additionalProperties": false
                },
                "logconfig": {
                    "id": "https://non-existing.saltstack.com/schemas/logconfig.json#",
                    "title": "Logging Configuration",
                    "description": "This is the logging configuration",
                    "type": "object",
                    "properties": {
                        "log_level": {
                            "default": "debug",
                            "minimum": 1,
                            "type": "string",
                            "description": "The logging level",
                            "title": "Logging Level"
                        }
                    },
                    "required": [
                        "log_level"
                    ],
                    "x-ordering": [
                        "log_level"
                    ],
                    "additionalProperties": false
                }
            },
            "additionalProperties": false
        }

        >>> import jsonschema
        >>> jsonschema.validate(
            {'hostconfig': {'host': 'localhost', 'port': 80},
             'logconfig': {'log_level': 'debug'}},
            MyConfig.serialize())
        >>> jsonschema.validate(
            {'hostconfig': {'host': 'localhost', 'port': -1},
             'logconfig': {'log_level': 'debug'}},
            MyConfig.serialize())
        Traceback (most recent call last):
        File "<stdin>", line 1, in <module>
        File "/usr/lib/python2.7/site-packages/jsonschema/validators.py", line 478, in validate
            cls(schema, *args, **kwargs).validate(instance)
        File "/usr/lib/python2.7/site-packages/jsonschema/validators.py", line 123, in validate
            raise error
        jsonschema.exceptions.ValidationError: -1 is less than the minimum of 0

        Failed validating 'minimum' in schema['properties']['hostconfig']['properties']['port']:
            {'default': 80,
            'description': 'The port number',
            'inclusiveMinimum': False,
            'maximum': 65535,
            'minimum': 0,
            'type': 'number'}

        On instance['hostconfig']['port']:
            -1
        >>>

    If however, you just want to use the configuration blocks for readability
    and do not desire the nested dictionaries serialization, you can pass
    ``flatten=True`` when defining a configuration section as a configuration
    subclass attribute:

    .. code-block:: python

        class MyConfig(Schema):

            title = 'My Config'
            description = 'This my configuration'

            hostconfig = HostConfig(flatten=True)
            logconfig = LoggingConfig(flatten=True)


    The JSON Schema string version of the above is:

    .. code-block:: python

        >>> print(json.dumps(MyConfig, indent=4))
        {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "title": "My Config",
            "description": "This my configuration",
            "type": "object",
            "properties": {
                "host": {
                    "minimum": 1,
                    "type": "string",
                    "description": "The looong host description",
                    "title": "Host"
                },
                "port": {
                    "description": "The port number",
                    "default": 80,
                    "inclusiveMinimum": false,
                    "maximum": 65535,
                    "minimum": 0,
                    "type": "number"
                },
                "log_level": {
                    "default": "debug",
                    "minimum": 1,
                    "type": "string",
                    "description": "The logging level",
                    "title": "Logging Level"
                }
            },
            "x-ordering": [
                "host",
                "port",
                "log_level"
            ],
            "additionalProperties": false
        }
'''
# Import python libs
from __future__ import absolute_import, print_function
import sys
import inspect
import textwrap
import functools

# Import salt libs
from salt.utils.odict import OrderedDict

# Import 3rd-party libs
#import yaml
import salt.ext.six as six

BASE_SCHEMA_URL = 'https://non-existing.saltstack.com/schemas'
RENDER_COMMENT_YAML_MAX_LINE_LENGTH = 80


class Prepareable(type):
    '''
    Preserve attributes order for python 2.x
    '''
    # This code was taken from
    # https://github.com/aromanovich/jsl/blob/master/jsl/_compat/prepareable.py
    # which in turn was taken from https://gist.github.com/DasIch/5562625 with minor fixes
    if not six.PY3:
        def __new__(mcs, name, bases, attributes):
            try:
                constructor = attributes["__new__"]
            except KeyError:
                return type.__new__(mcs, name, bases, attributes)

            def preparing_constructor(mcs, name, bases, attributes):
                try:
                    mcs.__prepare__
                except AttributeError:
                    return constructor(mcs, name, bases, attributes)
                namespace = mcs.__prepare__(name, bases)
                defining_frame = sys._getframe(1)
                for constant in reversed(defining_frame.f_code.co_consts):
                    if inspect.iscode(constant) and constant.co_name == name:
                        def get_index(attribute_name, _names=constant.co_names):  # pylint: disable=cell-var-from-loop
                            try:
                                return _names.index(attribute_name)
                            except ValueError:
                                return 0
                        break
                else:
                    return constructor(mcs, name, bases, attributes)

                by_appearance = sorted(
                    attributes.items(), key=lambda item: get_index(item[0])
                )
                for key, value in by_appearance:
                    namespace[key] = value
                return constructor(mcs, name, bases, namespace)
            attributes["__new__"] = functools.wraps(constructor)(preparing_constructor)
            return type.__new__(mcs, name, bases, attributes)


class NullSentinel(object):
    '''
    A class which instance represents a null value.
    Allows specifying fields with a default value of null.
    '''

    def __bool__(self):
        return False

    __nonzero__ = __bool__


Null = NullSentinel()
'''
A special value that can be used to set the default value
of a field to null.
'''


# make sure nobody creates another Null value
def _failing_new(*args, **kwargs):
    raise TypeError('Can\'t create another NullSentinel instance')

NullSentinel.__new__ = staticmethod(_failing_new)
del _failing_new


class SchemaMeta(six.with_metaclass(Prepareable, type)):

    @classmethod
    def __prepare__(mcs, name, bases):
        return OrderedDict()

    def __new__(mcs, name, bases, attrs):
        # Mark the instance as a configuration document/section
        attrs['__config__'] = True
        attrs['__flatten__'] = False
        attrs['__config_name__'] = None

        # Let's record the configuration items/sections
        items = {}
        sections = {}
        order = []
        # items from parent classes
        for base in reversed(bases):
            if hasattr(base, '_items'):
                items.update(base._items)
            if hasattr(base, '_sections'):
                sections.update(base._sections)
            if hasattr(base, '_order'):
                order.extend(base._order)

        # Iterate through attrs to discover items/config sections
        for key, value in six.iteritems(attrs):
            entry_name = None
            if not hasattr(value, '__item__') and not hasattr(value, '__config__'):
                continue
            if hasattr(value, '__item__'):
                # the value is an item instance
                if hasattr(value, 'title') and value.title is None:
                    # It's an item instance without a title, make the title
                    # it's name
                    value.title = key
                entry_name = value.__item_name__ or key
                items[entry_name] = value
            if hasattr(value, '__config__'):
                entry_name = value.__config_name__ or key
                sections[entry_name] = value
            order.append(entry_name)

        attrs['_order'] = order
        attrs['_items'] = items
        attrs['_sections'] = sections
        return type.__new__(mcs, name, bases, attrs)

    def __call__(cls, flatten=False, allow_additional_items=False, **kwargs):
        instance = object.__new__(cls)
        instance.__config_name__ = kwargs.pop('name', None)
        if flatten is True:
            # This configuration block is to be treated as a part of the
            # configuration for which it was defined as an attribute, not as
            # it's own sub configuration
            instance.__flatten__ = True
        if allow_additional_items is True:
            # The configuration block only accepts the configuration items
            # which are defined on the class. On additional items, validation
            # with jsonschema will fail
            instance.__allow_additional_items__ = True
        instance.__init__(**kwargs)
        return instance


class BaseSchemaItemMeta(six.with_metaclass(Prepareable, type)):
    '''
    Config item metaclass to "tag" the class as a configuration item
    '''
    @classmethod
    def __prepare__(mcs, name, bases):
        return OrderedDict()

    def __new__(mcs, name, bases, attrs):
        # Register the class as an item class
        attrs['__item__'] = True
        attrs['__item_name__'] = None
        # Instantiate an empty list to store the config item attribute names
        attributes = []
        for base in reversed(bases):
            try:
                base_attributes = getattr(base, '_attributes', [])
                if base_attributes:
                    attributes.extend(base_attributes)
                # Extend the attributes with the base argspec argument names
                # but skip "self"
                for argname in inspect.getargspec(base.__init__).args:
                    if argname == 'self' or argname in attributes:
                        continue
                    if argname == 'name':
                        continue
                    attributes.append(argname)
            except TypeError:
                # On the base object type, __init__ is just a wrapper which
                # triggers a TypeError when we're trying to find out it's
                # argspec
                continue
        attrs['_attributes'] = attributes
        return type.__new__(mcs, name, bases, attrs)

    def __call__(cls, *args, **kwargs):
        # Create the instance class
        instance = object.__new__(cls)
        if args:
            raise RuntimeError(
                'Please pass all arguments as named arguments. Un-named '
                'arguments are not supported'
            )
        for key in kwargs.keys():
            # Store the kwarg keys as the instance attributes for the
            # serialization step
            if key == 'name':
                # This is the item name to override the class attribute name
                instance.__item_name__ = kwargs.pop(key)
                continue
            if key not in instance._attributes:
                instance._attributes.append(key)
        # Init the class
        instance.__init__(*args, **kwargs)
        # Validate the instance after initialization
        for base in reversed(inspect.getmro(cls)):
            validate_attributes = getattr(base, '__validate_attributes__', None)
            if validate_attributes:
                if instance.__validate_attributes__.__func__.__code__ is not validate_attributes.__code__:
                    # The method was overridden, run base.__validate_attributes__ function
                    base.__validate_attributes__(instance)
        # Finally, run the instance __validate_attributes__ function
        instance.__validate_attributes__()
        # Return the initialized class
        return instance


class Schema(six.with_metaclass(SchemaMeta, object)):
    '''
    Configuration definition class
    '''

    # Define some class level attributes to make PyLint happier
    title = None
    description = None
    _items = _sections = _order = None
    __flatten__ = False
    __allow_additional_items__ = False

    @classmethod
    def serialize(cls, id_=None):
        # The order matters
        serialized = OrderedDict()
        if id_ is not None:
            # This is meant as a configuration section, sub json schema
            serialized['id'] = '{0}/{1}.json#'.format(BASE_SCHEMA_URL, id_)
        else:
            # Main configuration block, json schema
            serialized['$schema'] = 'http://json-schema.org/draft-04/schema#'
        if cls.title is not None:
            serialized['title'] = cls.title
        if cls.description is not None:
            if cls.description == cls.__doc__:
                serialized['description'] = textwrap.dedent(cls.description).strip()
            else:
                serialized['description'] = cls.description

        required = []
        ordering = []
        serialized['type'] = 'object'
        properties = OrderedDict()
        cls.after_items_update = []
        for name in cls._order:
            skip_order = False
            item_name = None
            if name in cls._sections:
                section = cls._sections[name]
                serialized_section = section.serialize(None if section.__flatten__ is True else name)
                if section.__flatten__ is True:
                    # Flatten the configuration section into the parent
                    # configuration
                    properties.update(serialized_section['properties'])
                    if 'x-ordering' in serialized_section:
                        ordering.extend(serialized_section['x-ordering'])
                    if 'required' in serialized_section:
                        required.extend(serialized_section['required'])
                    if hasattr(section, 'after_items_update'):
                        cls.after_items_update.extend(section.after_items_update)
                    skip_order = True
                else:
                    # Store it as a configuration section
                    properties[name] = serialized_section

            if name in cls._items:
                config = cls._items[name]
                item_name = config.__item_name__ or name
                # Handle the configuration items defined in the class instance
                if config.__flatten__ is True:
                    serialized_config = config.serialize()
                    cls.after_items_update.append(serialized_config)
                    skip_order = True
                else:
                    properties[item_name] = config.serialize()

                if config.required:
                    # If it's a required item, add it to the required list
                    required.append(item_name)

            if skip_order is False:
                # Store the order of the item
                if item_name is not None:
                    if item_name not in ordering:
                        ordering.append(item_name)
                else:
                    if name not in ordering:
                        ordering.append(name)

        if properties:
            serialized['properties'] = properties

        # Update the serialized object with any items to include after properties
        if cls.after_items_update:
            after_items_update = {}
            for entry in cls.after_items_update:
                name, data = next(six.iteritems(entry))
                if name in after_items_update:
                    after_items_update[name].extend(data)
                else:
                    after_items_update[name] = data
            serialized.update(after_items_update)

        if required:
            # Only include required if not empty
            serialized['required'] = required
        if ordering:
            # Only include ordering if not empty
            serialized['x-ordering'] = ordering
        serialized['additionalProperties'] = cls.__allow_additional_items__
        return serialized

    @classmethod
    def defaults(cls):
        serialized = cls.serialize()
        defaults = {}
        for name, details in serialized['properties'].items():
            if 'default' in details:
                defaults[name] = details['default']
                continue
            if 'properties' in details:
                for sname, sdetails in details['properties'].items():
                    if 'default' in sdetails:
                        defaults.setdefault(name, {})[sname] = sdetails['default']
                continue
        return defaults

    @classmethod
    def as_requirements_item(cls):
        serialized_schema = cls.serialize()
        required = serialized_schema.get('required', [])
        for name in serialized_schema['properties']:
            if name not in required:
                required.append(name)
        return RequirementsItem(requirements=required)

    #@classmethod
    #def render_as_rst(cls):
    #    '''
    #    Render the configuration block as a restructured text string
    #    '''
    #    # TODO: Implement RST rendering
    #    raise NotImplementedError

    #@classmethod
    #def render_as_yaml(cls):
    #    '''
    #    Render the configuration block as a parseable YAML string including comments
    #    '''
    #    # TODO: Implement YAML rendering
    #    raise NotImplementedError


class SchemaItem(six.with_metaclass(BaseSchemaItemMeta, object)):
    '''
    Base configuration items class.

    All configurations must subclass it
    '''

    # Define some class level attributes to make PyLint happier
    __type__ = None
    __format__ = None
    _attributes = None
    __flatten__ = False

    __serialize_attr_aliases__ = None

    required = False

    def __init__(self, required=None, **extra):
        '''
        :param required: If the configuration item is required. Defaults to ``False``.
        '''
        if required is not None:
            self.required = required
        self.extra = extra

    def __validate_attributes__(self):
        '''
        Run any validation check you need the instance attributes.

        ATTENTION:

        Don't call the parent class when overriding this
        method because it will just duplicate the executions. This class'es
        metaclass will take care of that.
        '''
        if self.required not in (True, False):
            raise RuntimeError(
                '\'required\' can only be True/False'
            )

    def _get_argname_value(self, argname):
        '''
        Return the argname value looking up on all possible attributes
        '''
        # Let's see if there's a private fuction to get the value
        argvalue = getattr(self, '__get_{0}__'.format(argname), None)
        if argvalue is not None and callable(argvalue):
            argvalue = argvalue()
        if argvalue is None:
            # Let's see if the value is defined as a public class variable
            argvalue = getattr(self, argname, None)
        if argvalue is None:
            # Let's see if it's defined as a private class variable
            argvalue = getattr(self, '__{0}__'.format(argname), None)
        if argvalue is None:
            # Let's look for it in the extra dictionary
            argvalue = self.extra.get(argname, None)
        return argvalue

    def serialize(self):
        '''
        Return a serializable form of the config instance
        '''
        raise NotImplementedError


class BaseSchemaItem(SchemaItem):
    '''
    Base configuration items class.

    All configurations must subclass it
    '''

    # Let's define description as a class attribute, this will allow a custom configuration
    # item to do something like:
    #   class MyCustomConfig(StringItem):
    #       '''
    #       This is my custom config, blah, blah, blah
    #       '''
    #       description = __doc__
    #
    description = None
    # The same for all other base arguments
    title = None
    default = None
    enum = None
    enumNames = None

    def __init__(self, title=None, description=None, default=None, enum=None, enumNames=None, **kwargs):
        '''
        :param required:
            If the configuration item is required. Defaults to ``False``.
        :param title:
            A short explanation about the purpose of the data described by this item.
        :param description:
            A detailed explanation about the purpose of the data described by this item.
        :param default:
            The default value for this configuration item. May be :data:`.Null` (a special value
            to set the default value to null).
        :param enum:
            A list(list, tuple, set) of valid choices.
        '''
        if title is not None:
            self.title = title
        if description is not None:
            self.description = description
        if default is not None:
            self.default = default
        if enum is not None:
            self.enum = enum
        if enumNames is not None:
            self.enumNames = enumNames
        super(BaseSchemaItem, self).__init__(**kwargs)

    def __validate_attributes__(self):
        if self.enum is not None:
            if not isinstance(self.enum, (list, tuple, set)):
                raise RuntimeError(
                    'Only the \'list\', \'tuple\' and \'set\' python types can be used '
                    'to define \'enum\''
                )
            if not isinstance(self.enum, list):
                self.enum = list(self.enum)
        if self.enumNames is not None:
            if not isinstance(self.enumNames, (list, tuple, set)):
                raise RuntimeError(
                    'Only the \'list\', \'tuple\' and \'set\' python types can be used '
                    'to define \'enumNames\''
                )
            if len(self.enum) != len(self.enumNames):
                raise RuntimeError(
                    'The size of \'enumNames\' must match the size of \'enum\''
                )
            if not isinstance(self.enumNames, list):
                self.enumNames = list(self.enumNames)

    def serialize(self):
        '''
        Return a serializable form of the config instance
        '''
        serialized = {'type': self.__type__}
        for argname in self._attributes:
            if argname == 'required':
                # This is handled elsewhere
                continue
            argvalue = self._get_argname_value(argname)
            if argvalue is not None:
                if argvalue is Null:
                    argvalue = None
                # None values are not meant to be included in the
                # serialization, since this is not None...
                if self.__serialize_attr_aliases__ and argname in self.__serialize_attr_aliases__:
                    argname = self.__serialize_attr_aliases__[argname]
                serialized[argname] = argvalue
        return serialized

    def __get_description__(self):
        if self.description is not None:
            if self.description == self.__doc__:
                return textwrap.dedent(self.description).strip()
            return self.description

    #def render_as_rst(self, name):
    #    '''
    #    Render the configuration item as a restructured text string
    #    '''
    #    # TODO: Implement YAML rendering
    #    raise NotImplementedError

    #def render_as_yaml(self, name):
    #    '''
    #    Render the configuration item as a parseable YAML string including comments
    #    '''
    #    # TODO: Include the item rules in the output, minimum, maximum, etc...
    #    output = '# ----- '
    #    output += self.title
    #    output += ' '
    #    output += '-' * (RENDER_COMMENT_YAML_MAX_LINE_LENGTH - 7 - len(self.title) - 2)
    #    output += '>\n'
    #    if self.description:
    #        output += '\n'.join(textwrap.wrap(self.description,
    #                                          width=RENDER_COMMENT_YAML_MAX_LINE_LENGTH,
    #                                          initial_indent='# '))
    #        output += '\n'
    #        yamled_default_value = yaml.dump(self.default, default_flow_style=False).split('\n...', 1)[0]
    #        output += '# Default: {0}\n'.format(yamled_default_value)
    #        output += '#{0}: {1}\n'.format(name, yamled_default_value)
    #    output += '# <---- '
    #    output += self.title
    #    output += ' '
    #    output += '-' * (RENDER_COMMENT_YAML_MAX_LINE_LENGTH - 7 - len(self.title) - 1)
    #    return output + '\n'


class NullItem(BaseSchemaItem):

    __type__ = 'null'


class BooleanItem(BaseSchemaItem):
    __type__ = 'boolean'


class StringItem(BaseSchemaItem):
    '''
    A string configuration field
    '''

    __type__ = 'string'

    __serialize_attr_aliases__ = {
        'min_length': 'minLength',
        'max_length': 'maxLength'
    }

    format = None
    pattern = None
    min_length = None
    max_length = None

    def __init__(self,
                 format=None,  # pylint: disable=redefined-builtin
                 pattern=None,
                 min_length=None,
                 max_length=None,
                 **kwargs):
        '''
        :param required:
            If the configuration item is required. Defaults to ``False``.
        :param title:
            A short explanation about the purpose of the data described by this item.
        :param description:
            A detailed explanation about the purpose of the data described by this item.
        :param default:
            The default value for this configuration item. May be :data:`.Null` (a special value
            to set the default value to null).
        :param enum:
            A list(list, tuple, set) of valid choices.
        :param format:
            A semantic format of the string (for example, ``"date-time"``, ``"email"``, or ``"uri"``).
        :param pattern:
            A regular expression (ECMA 262) that a string value must match.
        :param min_length:
            The minimum length
        :param max_length:
            The maximum length
        '''
        if format is not None:  # pylint: disable=redefined-builtin
            self.format = format
        if pattern is not None:
            self.pattern = pattern
        if min_length is not None:
            self.min_length = min_length
        if max_length is not None:
            self.max_length = max_length
        super(StringItem, self).__init__(**kwargs)

    def __validate_attributes__(self):
        if self.format is None and self.__format__ is not None:
            self.format = self.__format__


class EMailItem(StringItem):
    '''
    An internet email address, see `RFC 5322, section 3.4.1`__.

    .. __: http://tools.ietf.org/html/rfc5322
    '''
    __format__ = 'email'


class IPv4Item(StringItem):
    '''
    An IPv4 address configuration field, according to dotted-quad ABNF syntax as defined in
    `RFC 2673, section 3.2`__.

    .. __: http://tools.ietf.org/html/rfc2673
    '''
    __format__ = 'ipv4'


class IPv6Item(StringItem):
    '''
    An IPv6 address configuration field, as defined in `RFC 2373, section 2.2`__.

    .. __: http://tools.ietf.org/html/rfc2373
    '''
    __format__ = 'ipv6'


class HostnameItem(StringItem):
    '''
    An Internet host name configuration field, see `RFC 1034, section 3.1`__.

    .. __: http://tools.ietf.org/html/rfc1034
    '''
    __format__ = 'hostname'


class DateTimeItem(StringItem):
    '''
    An ISO 8601 formatted date-time configuration field, as defined by `RFC 3339, section 5.6`__.

    .. __: http://tools.ietf.org/html/rfc3339
    '''
    __format__ = 'date-time'


class UriItem(StringItem):
    '''
    A universal resource identifier (URI) configuration field, according to `RFC3986`__.

    .. __: http://tools.ietf.org/html/rfc3986
    '''
    __format__ = 'uri'


class SecretItem(StringItem):
    '''
    A string configuration field containing a secret, for example, passwords, API keys, etc
    '''
    __format__ = 'secret'


class NumberItem(BaseSchemaItem):

    __type__ = 'number'

    __serialize_attr_aliases__ = {
        'multiple_of': 'multipleOf',
        'exclusive_minimum': 'exclusiveMinimum',
        'exclusive_maximum': 'exclusiveMaximum',
    }

    multiple_of = None
    minimum = None
    exclusive_minimum = None
    maximum = None
    exclusive_maximum = None

    def __init__(self,
                 multiple_of=None,
                 minimum=None,
                 exclusive_minimum=None,
                 maximum=None,
                 exclusive_maximum=None,
                 **kwargs):
        '''
        :param required:
            If the configuration item is required. Defaults to ``False``.
        :param title:
            A short explanation about the purpose of the data described by this item.
        :param description:
            A detailed explanation about the purpose of the data described by this item.
        :param default:
            The default value for this configuration item. May be :data:`.Null` (a special value
            to set the default value to null).
        :param enum:
            A list(list, tuple, set) of valid choices.
        :param multiple_of:
            A value must be a multiple of this factor.
        :param minimum:
            The minimum allowed value
        :param exclusive_minimum:
            Wether a value is allowed to be exactly equal to the minimum
        :param maximum:
            The maximum allowed value
        :param exclusive_maximum:
            Wether a value is allowed to be exactly equal to the maximum
        '''
        if multiple_of is not None:
            self.multiple_of = multiple_of
        if minimum is not None:
            self.minimum = minimum
        if exclusive_minimum is not None:
            self.exclusive_minimum = exclusive_minimum
        if maximum is not None:
            self.maximum = maximum
        if exclusive_maximum is not None:
            self.exclusive_maximum = exclusive_maximum
        super(NumberItem, self).__init__(**kwargs)


class IntegerItem(NumberItem):
    __type__ = 'integer'


class ArrayItem(BaseSchemaItem):
    __type__ = 'array'

    __serialize_attr_aliases__ = {
        'min_items': 'minItems',
        'max_items': 'maxItems',
        'unique_items': 'uniqueItems',
        'additional_items': 'additionalItems'
    }

    items = None
    min_items = None
    max_items = None
    unique_items = None
    additional_items = None

    def __init__(self,
                 items=None,
                 min_items=None,
                 max_items=None,
                 unique_items=None,
                 additional_items=None,
                 **kwargs):
        '''
        :param required:
            If the configuration item is required. Defaults to ``False``.
        :param title:
            A short explanation about the purpose of the data described by this item.
        :param description:
            A detailed explanation about the purpose of the data described by this item.
        :param default:
            The default value for this configuration item. May be :data:`.Null` (a special value
            to set the default value to null).
        :param enum:
            A list(list, tuple, set) of valid choices.
        :param items:
            Either of the following:
                * :class:`BaseSchemaItem` -- all items of the array must match the field schema;
                * a list or a tuple of :class:`fields <.BaseSchemaItem>` -- all items of the array must be
                  valid according to the field schema at the corresponding index (tuple typing);
        :param min_items:
            Minimum length of the array
        :param max_items:
            Maximum length of the array
        :param unique_items:
            Whether all the values in the array must be distinct.
        :param additional_items:
            If the value of ``items`` is a list or a tuple, and the array length is larger than
            the number of fields in ``items``, then the additional items are described
            by the :class:`.BaseField` passed using this argument.
        :type additional_items: bool or :class:`.BaseSchemaItem`
        '''
        if items is not None:
            self.items = items
        if min_items is not None:
            self.min_items = min_items
        if max_items is not None:
            self.max_items = max_items
        if unique_items is not None:
            self.unique_items = unique_items
        if additional_items is not None:
            self.additional_items = additional_items
        super(ArrayItem, self).__init__(**kwargs)

    def __validate_attributes__(self):
        if not self.items and not self.additional_items:
            raise RuntimeError(
                'One of items or additional_items must be passed.'
            )
        if self.items is not None:
            if isinstance(self.items, (list, tuple)):
                for item in self.items:
                    if not isinstance(item, (Schema, SchemaItem)):
                        raise RuntimeError(
                            'All items passed in the item argument tuple/list must be '
                            'a subclass of Schema, SchemaItem or BaseSchemaItem, '
                            'not {0}'.format(type(item))
                        )
            elif not isinstance(self.items, (Schema, SchemaItem)):
                raise RuntimeError(
                    'The items argument passed must be a subclass of '
                    'Schema, SchemaItem or BaseSchemaItem, not '
                    '{0}'.format(type(self.items))
                )

    def __get_items__(self):
        if isinstance(self.items, (Schema, SchemaItem)):
            # This is either a Schema or a Basetem, return it in it's
            # serialized form
            return self.items.serialize()
        if isinstance(self.items, (tuple, list)):
            items = []
            for item in self.items:
                items.append(item.serialize())
            return items


class DictItem(BaseSchemaItem):

    __type__ = 'object'

    __serialize_attr_aliases__ = {
        'min_properties': 'minProperties',
        'max_properties': 'maxProperties',
        'pattern_properties': 'patternProperties',
        'additional_properties': 'additionalProperties'
    }

    properties = None
    pattern_properties = None
    additional_properties = None
    min_properties = None
    max_properties = None

    def __init__(self,
                 properties=None,
                 pattern_properties=None,
                 additional_properties=None,
                 min_properties=None,
                 max_properties=None,
                 **kwargs):
        '''
        :param required:
            If the configuration item is required. Defaults to ``False``.
        :type required:
            boolean
        :param title:
            A short explanation about the purpose of the data described by this item.
        :type title:
            str
        :param description:
            A detailed explanation about the purpose of the data described by this item.
        :param default:
            The default value for this configuration item. May be :data:`.Null` (a special value
            to set the default value to null).
        :param enum:
            A list(list, tuple, set) of valid choices.
        :param properties:
            A dictionary containing fields
        :param pattern_properties:
            A dictionary whose keys are regular expressions (ECMA 262).
            Properties match against these regular expressions, and for any that match,
            the property is described by the corresponding field schema.
        :type pattern_properties: dict[str -> :class:`.Schema` or
                                       :class:`.SchemaItem` or :class:`.BaseSchemaItem`]
        :param additional_properties:
            Describes properties that are not described by the ``properties`` or ``pattern_properties``.
        :type additional_properties: bool or :class:`.Schema` or :class:`.SchemaItem`
                                     or :class:`.BaseSchemaItem`
        :param min_properties:
            A minimum number of properties.
        :type min_properties: int
        :param max_properties:
            A maximum number of properties
        :type max_properties: int
        '''
        if properties is not None:
            self.properties = properties
        if pattern_properties is not None:
            self.pattern_properties = pattern_properties
        if additional_properties is not None:
            self.additional_properties = additional_properties
        if min_properties is not None:
            self.min_properties = min_properties
        if max_properties is not None:
            self.max_properties = max_properties
        super(DictItem, self).__init__(**kwargs)

    def __validate_attributes__(self):
        if not self.properties and not self.pattern_properties and not self.additional_properties:
            raise RuntimeError(
                'One of properties, pattern_properties or additional_properties must be passed'
            )
        if self.properties is not None:
            if not isinstance(self.properties, (Schema, dict)):
                raise RuntimeError(
                    'The passed properties must be passed as a dict or '
                    ' a Schema not \'{0}\''.format(type(self.properties))
                )
            if not isinstance(self.properties, Schema):
                for key, prop in self.properties.items():
                    if not isinstance(prop, (Schema, SchemaItem)):
                        raise RuntimeError(
                            'The passed property who\'s key is \'{0}\' must be of type '
                            'Schema, SchemaItem or BaseSchemaItem, not '
                            '\'{1}\''.format(key, type(prop))
                        )
        if self.pattern_properties is not None:
            if not isinstance(self.pattern_properties, dict):
                raise RuntimeError(
                    'The passed pattern_properties must be passed as a dict '
                    'not \'{0}\''.format(type(self.pattern_properties))
                )
            for key, prop in self.pattern_properties.items():
                if not isinstance(prop, (Schema, SchemaItem)):
                    raise RuntimeError(
                        'The passed pattern_property who\'s key is \'{0}\' must '
                        'be of type Schema, SchemaItem or BaseSchemaItem, '
                        'not \'{1}\''.format(key, type(prop))
                    )
        if self.additional_properties is not None:
            if not isinstance(self.additional_properties, (bool, Schema, SchemaItem)):
                raise RuntimeError(
                    'The passed additional_properties must be of type bool, '
                    'Schema, SchemaItem or BaseSchemaItem, not \'{0}\''.format(
                        type(self.pattern_properties)
                    )
                )

    def __get_properties__(self):
        if self.properties is None:
            return
        if isinstance(self.properties, Schema):
            return self.properties.serialize()['properties']
        properties = OrderedDict()
        for key, prop in self.properties.items():
            properties[key] = prop.serialize()
        return properties

    def __get_pattern_properties__(self):
        if self.pattern_properties is None:
            return
        pattern_properties = OrderedDict()
        for key, prop in self.pattern_properties.items():
            pattern_properties[key] = prop.serialize()
        return pattern_properties

    def __get_additional_properties__(self):
        if self.additional_properties is None:
            return
        if isinstance(self.additional_properties, bool):
            return self.additional_properties
        return self.additional_properties.serialize()

    def __call__(self, flatten=False):
        self.__flatten__ = flatten
        return self

    def serialize(self):
        result = super(DictItem, self).serialize()
        required = []
        if self.properties is not None:
            if isinstance(self.properties, Schema):
                serialized = self.properties.serialize()
                if 'required' in serialized:
                    required.extend(serialized['required'])
            else:
                for key, prop in self.properties.items():
                    if prop.required:
                        required.append(key)
        if required:
            result['required'] = required
        return result


class RequirementsItem(SchemaItem):
    __type__ = 'object'

    requirements = None

    def __init__(self, requirements=None):
        if requirements is not None:
            self.requirements = requirements
        super(RequirementsItem, self).__init__()

    def __validate_attributes__(self):
        if self.requirements is None:
            raise RuntimeError(
                'The passed requirements must not be empty'
            )
        if not isinstance(self.requirements, (SchemaItem, list, tuple, set)):
            raise RuntimeError(
                'The passed requirements must be passed as a list, tuple, '
                'set SchemaItem or BaseSchemaItem, not \'{0}\''.format(self.requirements)
            )

        if not isinstance(self.requirements, SchemaItem):
            if not isinstance(self.requirements, list):
                self.requirements = list(self.requirements)

            for idx, item in enumerate(self.requirements):
                if not isinstance(item, (six.string_types, SchemaItem)):
                    raise RuntimeError(
                        'The passed requirement at the {0} index must be of type '
                        'str or SchemaItem, not \'{1}\''.format(idx, type(item))
                    )

    def serialize(self):
        if isinstance(self.requirements, SchemaItem):
            requirements = self.requirements.serialize()
        else:
            requirements = []
            for requirement in self.requirements:
                if isinstance(requirement, SchemaItem):
                    requirements.append(requirement.serialize())
                    continue
                requirements.append(requirement)
        return {'required': requirements}


class OneOfItem(SchemaItem):

    __type__ = 'oneOf'

    items = None

    def __init__(self, items=None):
        if items is not None:
            self.items = items
        super(OneOfItem, self).__init__()

    def __validate_attributes__(self):
        if not self.items:
            raise RuntimeError(
                'The passed items must not be empty'
            )
        if not isinstance(self.items, (list, tuple)):
            raise RuntimeError(
                'The passed items must be passed as a list/tuple not '
                '\'{0}\''.format(type(self.items))
            )
        for idx, item in enumerate(self.items):
            if not isinstance(item, (Schema, SchemaItem)):
                raise RuntimeError(
                    'The passed item at the {0} index must be of type '
                    'Schema, SchemaItem or BaseSchemaItem, not '
                    '\'{1}\''.format(idx, type(item))
                )
        if not isinstance(self.items, list):
            self.items = list(self.items)

    def __call__(self, flatten=False):
        self.__flatten__ = flatten
        return self

    def serialize(self):
        return {self.__type__: [i.serialize() for i in self.items]}


class AnyOfItem(OneOfItem):

    __type__ = 'anyOf'


class AllOfItem(OneOfItem):

    __type__ = 'allOf'


class NotItem(SchemaItem):

    __type__ = 'not'

    item = None

    def __init__(self, item=None):
        if item is not None:
            self.item = item
        super(NotItem, self).__init__()

    def __validate_attributes__(self):
        if not self.item:
            raise RuntimeError(
                'An item must be passed'
            )
        if not isinstance(self.item, (Schema, SchemaItem)):
            raise RuntimeError(
                'The passed item be of type Schema, SchemaItem or '
                'BaseSchemaItem, not \'{1}\''.format(type(self.item))
            )

    def serialize(self):
        return {self.__type__: self.item.serialize()}


# ----- Custom Preconfigured Configs -------------------------------------------------------------------------------->
class PortItem(IntegerItem):
    minimum = 0  # yes, 0 is a valid port number
    maximum = 65535
# <---- Custom Preconfigured Configs ---------------------------------------------------------------------------------
