# -*- coding: utf-8 -*-
# pylint: disable=function-redefined
# TODO: Remove the following PyLint disable as soon as we support YAML and RST rendering
# pylint: disable=abstract-method

# Import python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.utils import config

# Import 3rd-party libs
try:
    import jsonschema
    import jsonschema.exceptions
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


# pylint: disable=unused-import
try:
    import rfc3987
    HAS_RFC3987 = True
except ImportError:
    HAS_RFC3987 = False

try:
    import strict_rfc3339
    HAS_STRICT_RFC3339 = True
except ImportError:
    HAS_STRICT_RFC3339 = False

try:
    import isodate
    HAS_ISODATE = True
except ImportError:
    HAS_ISODATE = False
# pylint: enable=unused-import


class ConfigTestCase(TestCase):
    '''
    TestCase for salt.utils.config module
    '''

    def test_boolean_config(self):
        item = config.BooleanConfig(title='Hungry', description='Are you hungry?')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'boolean',
                'title': item.title,
                'description': item.description
            }
        )

        item = config.BooleanConfig(title='Hungry',
                                    description='Are you hungry?',
                                    default=False)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'boolean',
                'title': item.title,
                'description': item.description,
                'default': item.default
            }
        )

        item = config.BooleanConfig(title='Hungry',
                                    description='Are you hungry?',
                                    default=config.Null)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'boolean',
                'title': item.title,
                'description': item.description,
                'default': None
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_boolean_config_validation(self):
        class TestConf(config.Configuration):
            item = config.BooleanConfig(title='Hungry', description='Are you hungry?')

        try:
            jsonschema.validate({'item': False}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 1}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

    def test_string_config(self):
        item = config.StringConfig(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description
            }
        )

        item = config.StringConfig(title='Foo', description='Foo Item', min_length=1, max_length=3)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'minLength': item.min_length,
                'maxLength': item.max_length
            }
        )

        item = config.StringConfig(title='Foo',
                                   description='Foo Item',
                                   min_length=1,
                                   max_length=3,
                                   default='foo')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'minLength': item.min_length,
                'maxLength': item.max_length,
                'default': 'foo'
            }
        )

        item = config.StringConfig(title='Foo',
                                   description='Foo Item',
                                   min_length=1,
                                   max_length=3,
                                   enum=('foo', 'bar'))
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'minLength': item.min_length,
                'maxLength': item.max_length,
                'enum': ['foo', 'bar']
            }
        )

        item = config.StringConfig(title='Foo',
                                   description='Foo Item',
                                   min_length=1,
                                   max_length=3,
                                   enum=('foo', 'bar'),
                                   enumNames=('Foo', 'Bar'))
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'minLength': item.min_length,
                'maxLength': item.max_length,
                'enum': ['foo', 'bar'],
                'enumNames': ['Foo', 'Bar']
            }
        )

        item = config.StringConfig(title='Foo',
                                   description='Foo Item',
                                   pattern=r'^([\w_-]+)$')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'pattern': item.pattern
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_string_config_validation(self):
        class TestConf(config.Configuration):
            item = config.StringConfig(title='Foo', description='Foo Item')

        try:
            jsonschema.validate({'item': 'the item'}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        class TestConf(config.Configuration):
            item = config.StringConfig(title='Foo', description='Foo Item',
                                       min_length=1, max_length=10)

        try:
            jsonschema.validate({'item': 'the item'}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 'the item the item'}, TestConf.serialize())
        self.assertIn('is too long', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.StringConfig(title='Foo', description='Foo Item',
                                       min_length=10, max_length=100)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 'the item'}, TestConf.serialize())
        self.assertIn('is too short', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.StringConfig(title='Foo',
                                       description='Foo Item',
                                       enum=('foo', 'bar'))

        try:
            jsonschema.validate({'item': 'foo'}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        class TestConf(config.Configuration):
            item = config.StringConfig(title='Foo',
                                       description='Foo Item',
                                       enum=('foo', 'bar'))
        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 'bin'}, TestConf.serialize())
        self.assertIn('is not one of', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.StringConfig(title='Foo', description='Foo Item',
                                       pattern=r'^([\w_-]+)$')

        try:
            jsonschema.validate({'item': 'the-item'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 'the item'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('does not match', excinfo.exception.message)

    def test_email_config(self):
        item = config.EMailConfig(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_email_config_validation(self):
        class TestConf(config.Configuration):
            item = config.EMailConfig(title='Item', description='Item description')

        try:
            jsonschema.validate({'item': 'nobody@nowhere.com'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not a', excinfo.exception.message)

    def test_ipv4_config(self):
        item = config.IPv4Config(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_ipv4_config_validation(self):
        class TestConf(config.Configuration):
            item = config.IPv4Config(title='Item', description='Item description')

        try:
            jsonschema.validate({'item': '127.0.0.1'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not a', excinfo.exception.message)

    def test_ipv6_config(self):
        item = config.IPv6Config(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_ipv6_config_validation(self):
        class TestConf(config.Configuration):
            item = config.IPv6Config(title='Item', description='Item description')

        try:
            jsonschema.validate({'item': '::1'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not a', excinfo.exception.message)

    def test_hostname_config(self):
        item = config.HostnameConfig(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_hostname_config_validation(self):
        class TestConf(config.Configuration):
            item = config.HostnameConfig(title='Item', description='Item description')

        try:
            jsonschema.validate({'item': 'localhost'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not a', excinfo.exception.message)

    def test_datetime_config(self):
        item = config.DateTimeConfig(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    @skipIf(any([HAS_ISODATE, HAS_STRICT_RFC3339]) is False, 'The \'strict_rfc3339\' or \'isodate\' library is missing')
    def test_datetime_config_validation(self):
        class TestConf(config.Configuration):
            item = config.DateTimeConfig(title='Item', description='Item description')

        try:
            jsonschema.validate({'item': '2015-07-01T18:05:27+01:00'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not a', excinfo.exception.message)

    def test_secret_config(self):
        item = config.SecretConfig(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    def test_uri_config(self):
        item = config.UriConfig(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    @skipIf(HAS_RFC3987 is False, 'The \'rfc3987\' library is missing')
    def test_uri_config_validation(self):
        class TestConf(config.Configuration):
            item = config.UriConfig(title='Item', description='Item description')

        try:
            jsonschema.validate({'item': 'ssh://localhost'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not a', excinfo.exception.message)

    def test_number_config(self):
        item = config.NumberConfig(title='How many dogs', description='Question')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'number',
                'title': item.title,
                'description': item.description
            }
        )

        item = config.NumberConfig(title='How many dogs',
                                   description='Question',
                                   minimum=0,
                                   maximum=10)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'number',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum
            }
        )

        item = config.NumberConfig(title='How many dogs',
                                   description='Question',
                                   multiple_of=2)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'number',
                'title': item.title,
                'description': item.description,
                'multipleOf': item.multiple_of
            }
        )

        item = config.NumberConfig(title='How many dogs',
                                   description='Question',
                                   minimum=0,
                                   exclusive_minimum=True,
                                   maximum=10,
                                   exclusive_maximum=True)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'number',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum,
                'exclusiveMinimum': True,
                'exclusiveMaximum': True
            }
        )

        item = config.NumberConfig(title='How many dogs',
                                   description='Question',
                                   minimum=0,
                                   maximum=10,
                                   default=0)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'number',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum,
                'default': 0
            }
        )

        item = config.NumberConfig(title='How many dogs',
                                   description='Question',
                                   minimum=0,
                                   maximum=10,
                                   default=0,
                                   enum=(0, 2, 4, 6))
        self.assertDictEqual(
            item.serialize(), {
                'type': 'number',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum,
                'default': 0,
                'enum': [0, 2, 4, 6]
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_number_config_validation(self):
        class TestConf(config.Configuration):
            item = config.NumberConfig(title='How many dogs', description='Question')

        try:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.NumberConfig(title='How many dogs',
                                       description='Question',
                                       multiple_of=2.2)

        try:
            jsonschema.validate({'item': 4.4}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 4}, TestConf.serialize())
        self.assertIn('is not a multiple of', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.NumberConfig(title='Foo', description='Foo Item',
                                       minimum=1, maximum=10)

        try:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 11}, TestConf.serialize())
        self.assertIn('is greater than the maximum of', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.NumberConfig(title='Foo', description='Foo Item',
                                       minimum=10, maximum=100)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is less than the minimum of', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.NumberConfig(title='How many dogs',
                                       description='Question',
                                       minimum=0,
                                       exclusive_minimum=True,
                                       maximum=10,
                                       exclusive_maximum=True)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 0}, TestConf.serialize())
        self.assertIn('is less than or equal to the minimum of', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 10}, TestConf.serialize())
        self.assertIn('is greater than or equal to the maximum of', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.NumberConfig(title='Foo',
                                       description='Foo Item',
                                       enum=(0, 2, 4, 6))

        try:
            jsonschema.validate({'item': 4}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        class TestConf(config.Configuration):
            item = config.NumberConfig(title='Foo',
                                       description='Foo Item',
                                       enum=(0, 2, 4, 6))
        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is not one of', excinfo.exception.message)

    def test_integer_config(self):
        item = config.IntegerConfig(title='How many dogs', description='Question')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'integer',
                'title': item.title,
                'description': item.description
            }
        )

        item = config.IntegerConfig(title='How many dogs',
                                    description='Question',
                                    minimum=0,
                                    maximum=10)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'integer',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum
            }
        )

        item = config.IntegerConfig(title='How many dogs',
                                    description='Question',
                                    multiple_of=2)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'integer',
                'title': item.title,
                'description': item.description,
                'multipleOf': item.multiple_of
            }
        )

        item = config.IntegerConfig(title='How many dogs',
                                    description='Question',
                                    minimum=0,
                                    exclusive_minimum=True,
                                    maximum=10,
                                    exclusive_maximum=True)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'integer',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum,
                'exclusiveMinimum': True,
                'exclusiveMaximum': True
            }
        )

        item = config.IntegerConfig(title='How many dogs',
                                    description='Question',
                                    minimum=0,
                                    maximum=10,
                                    default=0)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'integer',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum,
                'default': 0
            }
        )

        item = config.IntegerConfig(title='How many dogs',
                                    description='Question',
                                    minimum=0,
                                    maximum=10,
                                    default=0,
                                    enum=(0, 2, 4, 6))
        self.assertDictEqual(
            item.serialize(), {
                'type': 'integer',
                'title': item.title,
                'description': item.description,
                'minimum': item.minimum,
                'maximum': item.maximum,
                'default': 0,
                'enum': [0, 2, 4, 6]
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_integer_config_validation(self):
        class TestConf(config.Configuration):
            item = config.IntegerConfig(title='How many dogs', description='Question')

        try:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3.1}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.IntegerConfig(title='How many dogs',
                                        description='Question',
                                        multiple_of=2)

        try:
            jsonschema.validate({'item': 4}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is not a multiple of', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.IntegerConfig(title='Foo', description='Foo Item',
                                        minimum=1, maximum=10)

        try:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 11}, TestConf.serialize())
        self.assertIn('is greater than the maximum of', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.IntegerConfig(title='Foo', description='Foo Item',
                                        minimum=10, maximum=100)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is less than the minimum of', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.IntegerConfig(title='How many dogs',
                                        description='Question',
                                        minimum=0,
                                        exclusive_minimum=True,
                                        maximum=10,
                                        exclusive_maximum=True)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 0}, TestConf.serialize())
        self.assertIn('is less than or equal to the minimum of', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 10}, TestConf.serialize())
        self.assertIn('is greater than or equal to the maximum of', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.IntegerConfig(title='Foo',
                                        description='Foo Item',
                                        enum=(0, 2, 4, 6))

        try:
            jsonschema.validate({'item': 4}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        class TestConf(config.Configuration):
            item = config.IntegerConfig(title='Foo',
                                        description='Foo Item',
                                        enum=(0, 2, 4, 6))
        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is not one of', excinfo.exception.message)

    def test_array_config(self):
        item = config.ArrayConfig(title='Dog Names', description='Name your dogs')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'array',
                'title': item.title,
                'description': item.description
            }
        )

        string_item = config.StringConfig(title='Dog Name',
                                          description='The dog name')
        item = config.ArrayConfig(title='Dog Names',
                                  description='Name your dogs',
                                  items=string_item)

        self.assertDictEqual(
            item.serialize(), {
                'type': 'array',
                'title': item.title,
                'description': item.description,
                'items': {
                    'type': 'string',
                    'title': string_item.title,
                    'description': string_item.description
                }
            }
        )

        integer_item = config.IntegerConfig(title='Dog Age',
                                            description='The dog age')
        item = config.ArrayConfig(title='Dog Names',
                                  description='Name your dogs',
                                  items=(string_item, integer_item))

        self.assertDictEqual(
            item.serialize(), {
                'type': 'array',
                'title': item.title,
                'description': item.description,
                'items': [
                    {
                        'type': 'string',
                        'title': string_item.title,
                        'description': string_item.description
                    },
                    {
                        'type': 'integer',
                        'title': integer_item.title,
                        'description': integer_item.description
                    }
                ]
            }
        )

        item = config.ArrayConfig(title='Dog Names',
                                  description='Name your dogs',
                                  items=(config.StringConfig(),
                                         config.IntegerConfig()),
                                  min_items=1,
                                  max_items=3,
                                  additional_items=False,
                                  unique_items=True)

        self.assertDictEqual(
            item.serialize(), {
                'type': 'array',
                'title': item.title,
                'description': item.description,
                'minItems': item.min_items,
                'maxItems': item.max_items,
                'uniqueItems': item.unique_items,
                'additionalItems': item.additional_items,
                'items': [
                    {
                        'type': 'string',
                    },
                    {
                        'type': 'integer',
                    }
                ]
            }
        )

        class HowManyConfig(config.Configuration):
            item = config.IntegerConfig(title='How many dogs', description='Question')

        item = config.ArrayConfig(title='Dog Names',
                                  description='Name your dogs',
                                  items=HowManyConfig())
        self.assertDictEqual(
            item.serialize(), {
                'type': 'array',
                'title': item.title,
                'description': item.description,
                'items': HowManyConfig.serialize()
            }
        )

        class AgesConfig(config.Configuration):
            item = config.IntegerConfig()

        item = config.ArrayConfig(title='Dog Names',
                                  description='Name your dogs',
                                  items=(HowManyConfig(), AgesConfig()))
        self.assertDictEqual(
            item.serialize(), {
                'type': 'array',
                'title': item.title,
                'description': item.description,
                'items': [
                    HowManyConfig.serialize(),
                    AgesConfig.serialize()
                ]
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_array_config_validation(self):
        class TestConf(config.Configuration):
            item = config.ArrayConfig(title='Dog Names', description='Name your dogs')

        try:
            jsonschema.validate({'item': ['Tobias', 'Óscar']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 1}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.ArrayConfig(title='Dog Names',
                                      description='Name your dogs',
                                      items=config.StringConfig())

        try:
            jsonschema.validate({'item': ['Tobias', 'Óscar']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['Tobias', 'Óscar', 3]}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.ArrayConfig(title='Dog Names',
                                      description='Name your dogs',
                                      min_items=1,
                                      max_items=2)

        try:
            jsonschema.validate({'item': ['Tobias', 'Óscar']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['Tobias', 'Óscar', 'Pepe']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is too long', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': []}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is too short', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.ArrayConfig(title='Dog Names',
                                      description='Name your dogs',
                                      items=config.StringConfig(),
                                      uniqueItems=True)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['Tobias', 'Tobias']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('has non-unique elements', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.ArrayConfig(items=(config.StringConfig(),
                                             config.IntegerConfig()))
        try:
            jsonschema.validate({'item': ['Óscar', 4]}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['Tobias', 'Óscar']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.ArrayConfig(
                items=config.ArrayConfig(
                    items=(config.StringConfig(),
                           config.IntegerConfig())
                )
            )

        try:
            jsonschema.validate({'item': [['Tobias', 8], ['Óscar', 4]]}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': [['Tobias', 8], ['Óscar', '4']]}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(config.Configuration):
            item = config.ArrayConfig(items=config.StringConfig(enum=['Tobias', 'Óscar']))
        try:
            jsonschema.validate({'item': ['Óscar']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))
        try:
            jsonschema.validate({'item': ['Tobias']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['Pepe']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not one of', excinfo.exception.message)

    def test_oneof_config(self):
        item = config.OneOfConfig(
            items=(config.StringConfig(title='Yes', enum=['yes']),
                   config.StringConfig(title='No', enum=['no']))
        )
        self.assertEqual(
            item.serialize(), {
                'oneOf': [i.serialize() for i in item.items]
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_oneof_config_validation(self):
        class TestConf(config.Configuration):
            item = config.ArrayConfig(
                title='Hungry',
                description='Are you hungry?',
                items=config.OneOfConfig(
                    items=(config.StringConfig(title='Yes', enum=['yes']),
                           config.StringConfig(title='No', enum=['no']))
                )
            )

        try:
            jsonschema.validate({'item': ['no']}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['maybe']}, TestConf.serialize())
        self.assertIn('is not valid under any of the given schemas', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

    def test_anyof_config(self):
        item = config.AnyOfConfig(
            items=(config.StringConfig(title='Yes', enum=['yes']),
                   config.StringConfig(title='No', enum=['no']))
        )
        self.assertEqual(
            item.serialize(), {
                'anyOf': [i.serialize() for i in item.items]
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_anyof_config_validation(self):
        class TestConf(config.Configuration):
            item = config.ArrayConfig(
                title='Hungry',
                description='Are you hungry?',
                items=config.AnyOfConfig(
                    items=(config.StringConfig(title='Yes', enum=['yes']),
                           config.StringConfig(title='No', enum=['no']),
                           config.BooleanConfig())
                )
            )

        try:
            jsonschema.validate({'item': ['no']}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate({'item': ['yes']}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate({'item': [True]}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate({'item': [False]}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['maybe']}, TestConf.serialize())
        self.assertIn('is not valid under any of the given schemas', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

    def test_allof_config(self):
        item = config.AllOfConfig(
            items=(config.StringConfig(min_length=2),
                   config.StringConfig(max_length=3))
        )
        self.assertEqual(
            item.serialize(), {
                'allOf': [i.serialize() for i in item.items]
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_allof_config_validation(self):
        class TestConf(config.Configuration):
            item = config.ArrayConfig(
                title='Hungry',
                description='Are you hungry?',
                items=config.AllOfConfig(
                    items=(config.StringConfig(min_length=2),
                           config.StringConfig(max_length=3))
                )
            )

        try:
            jsonschema.validate({'item': ['no']}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate({'item': ['yes']}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['maybe']}, TestConf.serialize())
        self.assertIn('is too long', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['hmmmm']}, TestConf.serialize())
        self.assertIn('is too long', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

    def test_not_config(self):
        item = config.NotConfig(item=config.BooleanConfig())
        self.assertEqual(
            item.serialize(), {
                'not': item.item.serialize()
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_not_config_validation(self):
        class TestConf(config.Configuration):
            item = config.ArrayConfig(
                title='Hungry',
                description='Are you hungry?',
                items=config.NotConfig(item=config.BooleanConfig())
            )

        try:
            jsonschema.validate({'item': ['no']}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate({'item': ['yes']}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': [True]}, TestConf.serialize())
        self.assertIn('is not allowed for', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': [False]}, TestConf.serialize())
        self.assertIn('is not allowed for', excinfo.exception.message)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ConfigTestCase, needs_daemon=False)
