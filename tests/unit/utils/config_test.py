# -*- coding: utf-8 -*-
# pylint: disable=function-redefined

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



if __name__ == '__main__':
    from integration import run_tests
    run_tests(ConfigTestCase, needs_daemon=False)
