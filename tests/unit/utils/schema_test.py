# -*- coding: utf-8 -*-
# pylint: disable=function-redefined,missing-docstring
# TODO: Remove the following PyLint disable as soon as we support YAML and RST rendering
# pylint: disable=abstract-method

# Import python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import TestCase, skipIf
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt Libs
from salt.utils import schema

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

    def test_configuration_subclass_inherits_items(self):
        class BaseConfig(schema.Schema):
            base = schema.BooleanItem(default=True, required=True)

        class SubClassedConfig(BaseConfig):
            hungry = schema.BooleanItem(title='Hungry', description='Are you hungry?', required=True)

        self.assertDictEqual(
            SubClassedConfig.serialize(),
            {
                '$schema': 'http://json-schema.org/draft-04/schema#',
                'type': 'object',
                'properties': {
                    'base': {
                      'default': True,
                      'type': 'boolean',
                      'title': 'base'
                    },
                    'hungry': {
                        'type': 'boolean',
                        'description': 'Are you hungry?',
                        'title': 'Hungry'
                    }
                },
                'required': ['base', 'hungry'],
                'x-ordering': ['base', 'hungry'],
                'additionalProperties': False,
            }
        )

        class MergedConfigClass(schema.Schema):
            thirsty = schema.BooleanItem(title='Thirsty', description='Are you thirsty?', required=True)
            merge_subclassed = SubClassedConfig(flatten=True)

        expected = {
            '$schema': 'http://json-schema.org/draft-04/schema#',
            'type': 'object',
            'properties': {
                'thirsty': {
                    'type': 'boolean',
                    'description': 'Are you thirsty?',
                    'title': 'Thirsty'
                },
                'base': {
                  'default': True,
                  'type': 'boolean',
                  'title': 'base'
                },
                'hungry': {
                    'type': 'boolean',
                    'description': 'Are you hungry?',
                    'title': 'Hungry'
                }
            },
            'required': ['thirsty', 'base', 'hungry'],
            'x-ordering': ['thirsty', 'base', 'hungry'],
            'additionalProperties': False,
        }
        self.assertDictContainsSubset(
            MergedConfigClass.serialize()['properties'],
            expected['properties']
        )
        self.assertDictContainsSubset(
            expected,
            MergedConfigClass.serialize()
        )

    def test_configuration_items_order(self):

        class One(schema.Schema):
            one = schema.BooleanItem()

        class Three(schema.Schema):
            three = schema.BooleanItem()

        class Final(One):
            two = schema.BooleanItem()
            three = Three(flatten=True)

        self.assertEqual(Final.serialize()['x-ordering'], ['one', 'two', 'three'])

    def test_optional_requirements_config(self):
        class BaseRequirements(schema.Schema):
            driver = schema.StringItem(default='digital_ocean', format='hidden')

        class SSHKeyFileSchema(schema.Schema):
            ssh_key_file = schema.StringItem(
                title='SSH Private Key',
                description='The path to an SSH private key which will be used '
                            'to authenticate on the deployed VMs',
                )

        class SSHKeyNamesSchema(schema.Schema):
            ssh_key_names = schema.StringItem(
                title='SSH Key Names',
                description='The names of an SSH key being managed on '
                            'Digital Ocean account which will be used to '
                            'authenticate on the deployed VMs',
                )

        class Requirements(BaseRequirements):
            title = 'Digital Ocean'
            description = 'Digital Ocean Cloud VM configuration requirements.'

            personal_access_token = schema.StringItem(
                title='Personal Access Token',
                description='This is the API access token which can be generated '
                            'under the API/Application on your account',
                required=True)

            requirements_definition = schema.AnyOfItem(
                items=(
                    SSHKeyFileSchema.as_requirements_item(),
                    SSHKeyNamesSchema.as_requirements_item()
                ),
            )(flatten=True)
            ssh_key_file = SSHKeyFileSchema(flatten=True)
            ssh_key_names = SSHKeyNamesSchema(flatten=True)

        expected = {
            '$schema': 'http://json-schema.org/draft-04/schema#',
            'title': 'Digital Ocean',
            'description': 'Digital Ocean Cloud VM configuration requirements.',
            'type': 'object',
            'properties': {
                'driver': {
                    'default': 'digital_ocean',
                    'format': 'hidden',
                    'type': 'string',
                    'title': 'driver'
                },
                'personal_access_token': {
                    'type': 'string',
                    'description': 'This is the API access token which can be '
                                   'generated under the API/Application on your account',
                    'title': 'Personal Access Token'
                },
                'ssh_key_file': {
                    'type': 'string',
                    'description': 'The path to an SSH private key which will '
                                   'be used to authenticate on the deployed VMs',
                    'title': 'SSH Private Key'
                },
                'ssh_key_names': {
                    'type': 'string',
                    'description': 'The names of an SSH key being managed on Digital '
                                   'Ocean account which will be used to authenticate '
                                   'on the deployed VMs',
                    'title': 'SSH Key Names'
                }
            },
            'anyOf': [
                {'required': ['ssh_key_file']},
                {'required': ['ssh_key_names']}
            ],
            'required': [
                'personal_access_token'
            ],
            'x-ordering': [
                'driver',
                'personal_access_token',
                'ssh_key_file',
                'ssh_key_names',
            ],
            'additionalProperties': False
        }
        self.assertDictEqual(expected, Requirements.serialize())

        class Requirements2(BaseRequirements):
            title = 'Digital Ocean'
            description = 'Digital Ocean Cloud VM configuration requirements.'

            personal_access_token = schema.StringItem(
                title='Personal Access Token',
                description='This is the API access token which can be generated '
                            'under the API/Application on your account',
                required=True)

            ssh_key_file = schema.StringItem(
                title='SSH Private Key',
                description='The path to an SSH private key which will be used '
                            'to authenticate on the deployed VMs')

            ssh_key_names = schema.StringItem(
                title='SSH Key Names',
                description='The names of an SSH key being managed on '
                            'Digital Ocean account which will be used to '
                            'authenticate on the deployed VMs')

            requirements_definition = schema.AnyOfItem(
                items=(
                    schema.RequirementsItem(requirements=['ssh_key_file']),
                    schema.RequirementsItem(requirements=['ssh_key_names'])
                ),
            )(flatten=True)

        expected = {
            '$schema': 'http://json-schema.org/draft-04/schema#',
            'title': 'Digital Ocean',
            'description': 'Digital Ocean Cloud VM configuration requirements.',
            'type': 'object',
            'properties': {
                'driver': {
                    'default': 'digital_ocean',
                    'format': 'hidden',
                    'type': 'string',
                    'title': 'driver'
                },
                'personal_access_token': {
                    'type': 'string',
                    'description': 'This is the API access token which can be '
                                   'generated under the API/Application on your account',
                    'title': 'Personal Access Token'
                },
                'ssh_key_file': {
                    'type': 'string',
                    'description': 'The path to an SSH private key which will '
                                   'be used to authenticate on the deployed VMs',
                    'title': 'SSH Private Key'
                },
                'ssh_key_names': {
                    'type': 'string',
                    'description': 'The names of an SSH key being managed on Digital '
                                   'Ocean account which will be used to authenticate '
                                   'on the deployed VMs',
                    'title': 'SSH Key Names'
                }
            },
            'anyOf': [
                {'required': ['ssh_key_file']},
                {'required': ['ssh_key_names']}
            ],
            'required': [
                'personal_access_token'
            ],
            'x-ordering': [
                'driver',
                'personal_access_token',
                'ssh_key_file',
                'ssh_key_names',
            ],
            'additionalProperties': False
        }
        self.assertDictContainsSubset(expected, Requirements2.serialize())

        class Requirements3(schema.Schema):
            title = 'Digital Ocean'
            description = 'Digital Ocean Cloud VM configuration requirements.'

            merge_reqs = Requirements(flatten=True)

        expected = {
            '$schema': 'http://json-schema.org/draft-04/schema#',
            'title': 'Digital Ocean',
            'description': 'Digital Ocean Cloud VM configuration requirements.',
            'type': 'object',
            'properties': {
                'driver': {
                    'default': 'digital_ocean',
                    'format': 'hidden',
                    'type': 'string',
                    'title': 'driver'
                },
                'personal_access_token': {
                    'type': 'string',
                    'description': 'This is the API access token which can be '
                                   'generated under the API/Application on your account',
                    'title': 'Personal Access Token'
                },
                'ssh_key_file': {
                    'type': 'string',
                    'description': 'The path to an SSH private key which will '
                                   'be used to authenticate on the deployed VMs',
                    'title': 'SSH Private Key'
                },
                'ssh_key_names': {
                    'type': 'string',
                    'description': 'The names of an SSH key being managed on Digital '
                                   'Ocean account which will be used to authenticate '
                                   'on the deployed VMs',
                    'title': 'SSH Key Names'
                }
            },
            'anyOf': [
                {'required': ['ssh_key_file']},
                {'required': ['ssh_key_names']}
            ],
            'required': [
                'personal_access_token'
            ],
            'x-ordering': [
                'driver',
                'personal_access_token',
                'ssh_key_file',
                'ssh_key_names',
            ],
            'additionalProperties': False
        }
        self.assertDictContainsSubset(expected, Requirements3.serialize())

        class Requirements4(schema.Schema):
            title = 'Digital Ocean'
            description = 'Digital Ocean Cloud VM configuration requirements.'

            merge_reqs = Requirements(flatten=True)

            ssh_key_file_2 = schema.StringItem(
                title='SSH Private Key',
                description='The path to an SSH private key which will be used '
                            'to authenticate on the deployed VMs')

            ssh_key_names_2 = schema.StringItem(
                title='SSH Key Names',
                description='The names of an SSH key being managed on '
                            'Digital Ocean account which will be used to '
                            'authenticate on the deployed VMs')

            requirements_definition_2 = schema.AnyOfItem(
                items=(
                    schema.RequirementsItem(requirements=['ssh_key_file_2']),
                    schema.RequirementsItem(requirements=['ssh_key_names_2'])
                ),
            )(flatten=True)

        expected = {
            '$schema': 'http://json-schema.org/draft-04/schema#',
            'title': 'Digital Ocean',
            'description': 'Digital Ocean Cloud VM configuration requirements.',
            'type': 'object',
            'properties': {
                'driver': {
                    'default': 'digital_ocean',
                    'format': 'hidden',
                    'type': 'string',
                    'title': 'driver'
                },
                'personal_access_token': {
                    'type': 'string',
                    'description': 'This is the API access token which can be '
                                   'generated under the API/Application on your account',
                    'title': 'Personal Access Token'
                },
                'ssh_key_file': {
                    'type': 'string',
                    'description': 'The path to an SSH private key which will '
                                   'be used to authenticate on the deployed VMs',
                    'title': 'SSH Private Key'
                },
                'ssh_key_names': {
                    'type': 'string',
                    'description': 'The names of an SSH key being managed on Digital '
                                   'Ocean account which will be used to authenticate '
                                   'on the deployed VMs',
                    'title': 'SSH Key Names'
                },
                'ssh_key_file_2': {
                    'type': 'string',
                    'description': 'The path to an SSH private key which will '
                                   'be used to authenticate on the deployed VMs',
                    'title': 'SSH Private Key'
                },
                'ssh_key_names_2': {
                    'type': 'string',
                    'description': 'The names of an SSH key being managed on Digital '
                                   'Ocean account which will be used to authenticate '
                                   'on the deployed VMs',
                    'title': 'SSH Key Names'
                }
            },
            'anyOf': [
                {'required': ['ssh_key_file']},
                {'required': ['ssh_key_names']},
                {'required': ['ssh_key_file_2']},
                {'required': ['ssh_key_names_2']}
            ],
            'required': [
                'personal_access_token'
            ],
            'x-ordering': [
                'driver',
                'personal_access_token',
                'ssh_key_file',
                'ssh_key_names',
                'ssh_key_file_2',
                'ssh_key_names_2',
            ],
            'additionalProperties': False
        }
        self.assertDictContainsSubset(expected, Requirements4.serialize())

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_optional_requirements_config_validation(self):
        class BaseRequirements(schema.Schema):
            driver = schema.StringItem(default='digital_ocean', format='hidden')

        class SSHKeyFileSchema(schema.Schema):
            ssh_key_file = schema.StringItem(
                title='SSH Private Key',
                description='The path to an SSH private key which will be used '
                            'to authenticate on the deployed VMs')

        class SSHKeyNamesSchema(schema.Schema):
            ssh_key_names = schema.StringItem(
                title='SSH Key Names',
                description='The names of an SSH key being managed on  '
                            'Digial Ocean account which will be used to '
                            'authenticate on the deployed VMs')

        class Requirements(BaseRequirements):
            title = 'Digital Ocean'
            description = 'Digital Ocean Cloud VM configuration requirements.'

            personal_access_token = schema.StringItem(
                title='Personal Access Token',
                description='This is the API access token which can be generated '
                            'under the API/Application on your account',
                required=True)

            requirements_definition = schema.AnyOfItem(
                items=(
                    SSHKeyFileSchema.as_requirements_item(),
                    SSHKeyNamesSchema.as_requirements_item()
                ),
            )(flatten=True)
            ssh_key_file = SSHKeyFileSchema(flatten=True)
            ssh_key_names = SSHKeyNamesSchema(flatten=True)

        try:
            jsonschema.validate(
                {'personal_access_token': 'foo', 'ssh_key_names': 'bar', 'ssh_key_file': 'test'},
                Requirements.serialize()
            )
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate(
                {'personal_access_token': 'foo', 'ssh_key_names': 'bar'},
                Requirements.serialize()
            )
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate(
                {'personal_access_token': 'foo', 'ssh_key_file': 'test'},
                Requirements.serialize()
            )
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate(
                {'personal_access_token': 'foo'},
                Requirements.serialize()
            )
        self.assertIn('is not valid under any of the given schemas', excinfo.exception.message)

    def test_boolean_config(self):
        item = schema.BooleanItem(title='Hungry', description='Are you hungry?')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'boolean',
                'title': item.title,
                'description': item.description
            }
        )

        item = schema.BooleanItem(title='Hungry',
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

        item = schema.BooleanItem(title='Hungry',
                                  description='Are you hungry?',
                                  default=schema.Null)
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
        class TestConf(schema.Schema):
            item = schema.BooleanItem(title='Hungry', description='Are you hungry?')

        try:
            jsonschema.validate({'item': False}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 1}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

    def test_string_config(self):
        item = schema.StringItem(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description
            }
        )

        item = schema.StringItem(title='Foo', description='Foo Item', min_length=1, max_length=3)
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'minLength': item.min_length,
                'maxLength': item.max_length
            }
        )

        item = schema.StringItem(title='Foo',
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

        item = schema.StringItem(title='Foo',
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

        item = schema.StringItem(title='Foo',
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

        item = schema.StringItem(title='Foo',
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
        class TestConf(schema.Schema):
            item = schema.StringItem(title='Foo', description='Foo Item')

        try:
            jsonschema.validate({'item': 'the item'}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        class TestConf(schema.Schema):
            item = schema.StringItem(title='Foo', description='Foo Item',
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

        class TestConf(schema.Schema):
            item = schema.StringItem(title='Foo', description='Foo Item',
                                     min_length=10, max_length=100)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 'the item'}, TestConf.serialize())
        self.assertIn('is too short', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.StringItem(title='Foo',
                                     description='Foo Item',
                                     enum=('foo', 'bar'))

        try:
            jsonschema.validate({'item': 'foo'}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        class TestConf(schema.Schema):
            item = schema.StringItem(title='Foo',
                                     description='Foo Item',
                                     enum=('foo', 'bar'))
        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 'bin'}, TestConf.serialize())
        self.assertIn('is not one of', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.StringItem(title='Foo', description='Foo Item',
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
        item = schema.EMailItem(title='Foo', description='Foo Item')
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
        class TestConf(schema.Schema):
            item = schema.EMailItem(title='Item', description='Item description')

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
        item = schema.IPv4Item(title='Foo', description='Foo Item')
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
        class TestConf(schema.Schema):
            item = schema.IPv4Item(title='Item', description='Item description')

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
        item = schema.IPv6Item(title='Foo', description='Foo Item')
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
        class TestConf(schema.Schema):
            item = schema.IPv6Item(title='Item', description='Item description')

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
        item = schema.HostnameItem(title='Foo', description='Foo Item')
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
        class TestConf(schema.Schema):
            item = schema.HostnameItem(title='Item', description='Item description')

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
        item = schema.DateTimeItem(title='Foo', description='Foo Item')
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
        class TestConf(schema.Schema):
            item = schema.DateTimeItem(title='Item', description='Item description')

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
        item = schema.SecretItem(title='Foo', description='Foo Item')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'string',
                'title': item.title,
                'description': item.description,
                'format': item.format
            }
        )

    def test_uri_config(self):
        item = schema.UriItem(title='Foo', description='Foo Item')
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
        class TestConf(schema.Schema):
            item = schema.UriItem(title='Item', description='Item description')

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
        item = schema.NumberItem(title='How many dogs', description='Question')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'number',
                'title': item.title,
                'description': item.description
            }
        )

        item = schema.NumberItem(title='How many dogs',
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

        item = schema.NumberItem(title='How many dogs',
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

        item = schema.NumberItem(title='How many dogs',
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

        item = schema.NumberItem(title='How many dogs',
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

        item = schema.NumberItem(title='How many dogs',
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
        class TestConf(schema.Schema):
            item = schema.NumberItem(title='How many dogs', description='Question')

        try:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': '3'}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.NumberItem(title='How many dogs',
                                     description='Question',
                                     multiple_of=2.2)

        try:
            jsonschema.validate({'item': 4.4}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 4}, TestConf.serialize())
        self.assertIn('is not a multiple of', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.NumberItem(title='Foo', description='Foo Item',
                                     minimum=1, maximum=10)

        try:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 11}, TestConf.serialize())
        self.assertIn('is greater than the maximum of', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.NumberItem(title='Foo', description='Foo Item',
                                     minimum=10, maximum=100)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is less than the minimum of', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.NumberItem(title='How many dogs',
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

        class TestConf(schema.Schema):
            item = schema.NumberItem(title='Foo',
                                     description='Foo Item',
                                     enum=(0, 2, 4, 6))

        try:
            jsonschema.validate({'item': 4}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        class TestConf(schema.Schema):
            item = schema.NumberItem(title='Foo',
                                     description='Foo Item',
                                     enum=(0, 2, 4, 6))
        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is not one of', excinfo.exception.message)

    def test_integer_config(self):
        item = schema.IntegerItem(title='How many dogs', description='Question')
        self.assertDictEqual(
            item.serialize(), {
                'type': 'integer',
                'title': item.title,
                'description': item.description
            }
        )

        item = schema.IntegerItem(title='How many dogs',
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

        item = schema.IntegerItem(title='How many dogs',
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

        item = schema.IntegerItem(title='How many dogs',
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

        item = schema.IntegerItem(title='How many dogs',
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

        item = schema.IntegerItem(title='How many dogs',
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
        class TestConf(schema.Schema):
            item = schema.IntegerItem(title='How many dogs', description='Question')

        try:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3.1}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.IntegerItem(title='How many dogs',
                                      description='Question',
                                      multiple_of=2)

        try:
            jsonschema.validate({'item': 4}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is not a multiple of', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.IntegerItem(title='Foo', description='Foo Item',
                                      minimum=1, maximum=10)

        try:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 11}, TestConf.serialize())
        self.assertIn('is greater than the maximum of', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.IntegerItem(title='Foo', description='Foo Item',
                                      minimum=10, maximum=100)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is less than the minimum of', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.IntegerItem(title='How many dogs',
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

        class TestConf(schema.Schema):
            item = schema.IntegerItem(title='Foo',
                                      description='Foo Item',
                                      enum=(0, 2, 4, 6))

        try:
            jsonschema.validate({'item': 4}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        class TestConf(schema.Schema):
            item = schema.IntegerItem(title='Foo',
                                      description='Foo Item',
                                      enum=(0, 2, 4, 6))
        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 3}, TestConf.serialize())
        self.assertIn('is not one of', excinfo.exception.message)

    def test_array_config(self):
        string_item = schema.StringItem(title='Dog Name',
                                        description='The dog name')
        item = schema.ArrayItem(title='Dog Names',
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

        integer_item = schema.IntegerItem(title='Dog Age',
                                          description='The dog age')
        item = schema.ArrayItem(title='Dog Names',
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

        item = schema.ArrayItem(title='Dog Names',
                                description='Name your dogs',
                                items=(schema.StringItem(),
                                       schema.IntegerItem()),
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

        class HowManyConfig(schema.Schema):
            item = schema.IntegerItem(title='How many dogs', description='Question')

        item = schema.ArrayItem(title='Dog Names',
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

        class AgesConfig(schema.Schema):
            item = schema.IntegerItem()

        item = schema.ArrayItem(title='Dog Names',
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
        class TestConf(schema.Schema):
            item = schema.ArrayItem(title='Dog Names',
                                    description='Name your dogs',
                                    items=schema.StringItem())

        try:
            jsonschema.validate({'item': ['Tobias', 'Óscar']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['Tobias', 'Óscar', 3]}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.ArrayItem(title='Dog Names',
                                    description='Name your dogs',
                                    items=schema.StringItem(),
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

        class TestConf(schema.Schema):
            item = schema.ArrayItem(title='Dog Names',
                                    description='Name your dogs',
                                    items=schema.StringItem(),
                                    uniqueItems=True)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['Tobias', 'Tobias']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('has non-unique elements', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.ArrayItem(items=(schema.StringItem(),
                                           schema.IntegerItem()))
        try:
            jsonschema.validate({'item': ['Óscar', 4]}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': ['Tobias', 'Óscar']}, TestConf.serialize(),
                                format_checker=jsonschema.FormatChecker())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.ArrayItem(
                items=schema.ArrayItem(
                    items=(schema.StringItem(),
                           schema.IntegerItem())
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

        class TestConf(schema.Schema):
            item = schema.ArrayItem(items=schema.StringItem(enum=['Tobias', 'Óscar']))
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

    def test_dict_config(self):
        item = schema.DictItem(
            title='Poligon',
            description='Describe the Poligon',
            properties={
                'sides': schema.IntegerItem()
            }
        )
        self.assertDictEqual(
            item.serialize(), {
                'type': 'object',
                'title': item.title,
                'description': item.description,
                'properties': {
                    'sides': {'type': 'integer'}
                }
            }
        )

        item = schema.DictItem(
            title='Poligon',
            description='Describe the Poligon',
            properties={
                'sides': schema.IntegerItem()
            },
            min_properties=1,
            max_properties=2
        )
        self.assertDictEqual(
            item.serialize(), {
                'type': 'object',
                'title': item.title,
                'description': item.description,
                'properties': {
                    'sides': {'type': 'integer'}
                },
                'minProperties': 1,
                'maxProperties': 2
            }
        )

        item = schema.DictItem(
            title='Poligon',
            description='Describe the Poligon',
            pattern_properties={
                's.*': schema.IntegerItem()
            },
            min_properties=1,
            max_properties=2
        )
        self.assertDictEqual(
            item.serialize(), {
                'type': 'object',
                'title': item.title,
                'description': item.description,
                'patternProperties': {
                    's.*': {'type': 'integer'}
                },
                'minProperties': 1,
                'maxProperties': 2
            }
        )

        item = schema.DictItem(
            title='Poligon',
            description='Describe the Poligon',
            properties={
                'color': schema.StringItem(enum=['red', 'green', 'blue'])
            },
            pattern_properties={
                's*': schema.IntegerItem()
            },
            min_properties=1,
            max_properties=2
        )
        self.assertDictEqual(
            item.serialize(), {
                'type': 'object',
                'title': item.title,
                'description': item.description,
                'properties': {
                    'color': {
                        'type': 'string',
                        'enum': ['red', 'green', 'blue']
                    }
                },
                'patternProperties': {
                    's*': {'type': 'integer'}
                },
                'minProperties': 1,
                'maxProperties': 2
            }
        )

        item = schema.DictItem(
            title='Poligon',
            description='Describe the Poligon',
            properties={
                'color': schema.StringItem(enum=['red', 'green', 'blue'])
            },
            pattern_properties={
                's*': schema.IntegerItem()
            },
            additional_properties=True,
            min_properties=1,
            max_properties=2
        )
        self.assertDictEqual(
            item.serialize(), {
                'type': 'object',
                'title': item.title,
                'description': item.description,
                'properties': {
                    'color': {
                        'type': 'string',
                        'enum': ['red', 'green', 'blue']
                    }
                },
                'patternProperties': {
                    's*': {'type': 'integer'}
                },
                'minProperties': 1,
                'maxProperties': 2,
                'additionalProperties': True
            }
        )
        item = schema.DictItem(
            title='Poligon',
            description='Describe the Poligon',
            properties={
                'sides': schema.IntegerItem()
            },
            additional_properties=schema.OneOfItem(items=[schema.BooleanItem(),
                                                          schema.StringItem()])
        )
        self.assertDictEqual(
            item.serialize(), {
                'type': 'object',
                'title': item.title,
                'description': item.description,
                'properties': {
                    'sides': {'type': 'integer'}
                },
                'additionalProperties': {
                    'oneOf': [
                        {'type': 'boolean'},
                        {'type': 'string'}
                    ]
                }
            }
        )

        class TestConf(schema.Schema):
            item = schema.DictItem(
                title='Poligon',
                description='Describe the Poligon',
                properties={
                    'sides': schema.IntegerItem(required=True)
                },
                additional_properties=schema.OneOfItem(items=[schema.BooleanItem(),
                                                              schema.StringItem()])
            )

        self.assertDictContainsSubset(
            TestConf.serialize(), {
                '$schema': 'http://json-schema.org/draft-04/schema#',
                'type': 'object',
                'properties': {
                    'item': {
                        'title': 'Poligon',
                        'description': 'Describe the Poligon',
                        'type': 'object',
                        'properties': {
                            'sides': {
                                'type': 'integer'
                            }
                        },
                        'additionalProperties': {
                            'oneOf': [
                                {
                                    'type': 'boolean'
                                },
                                {
                                    'type': 'string'
                                }
                            ]
                        },
                        'required': [
                            'sides'
                        ],
                    }
                },
                'x-ordering': [
                    'item'
                ],
                'additionalProperties': False
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_dict_config_validation(self):
        class TestConf(schema.Schema):
            item = schema.DictItem(
                title='Poligon',
                description='Describe the Poligon',
                properties={
                    'sides': schema.IntegerItem()
                }
            )
        try:
            jsonschema.validate({'item': {'sides': 1}}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': {'sides': '1'}}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.DictItem(
                title='Poligon',
                description='Describe the Poligon',
                properties={
                    'color': schema.StringItem(enum=['red', 'green', 'blue'])
                },
                pattern_properties={
                    'si.*': schema.IntegerItem()
                },
            )

        try:
            jsonschema.validate({'item': {'sides': 1, 'color': 'red'}}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': {'sides': '4', 'color': 'blue'}}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': 2}, TestConf.serialize())
        self.assertIn('is not of type', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.DictItem(
                title='Poligon',
                description='Describe the Poligon',
                properties={
                    'color': schema.StringItem(enum=['red', 'green', 'blue'])
                },
                pattern_properties={
                    'si.*': schema.IntegerItem()
                },
                additional_properties=False
            )

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': {'color': 'green', 'sides': 4, 'surfaces': 4}}, TestConf.serialize())
        self.assertIn('Additional properties are not allowed', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.DictItem(
                title='Poligon',
                description='Describe the Poligon',
                properties={
                    'color': schema.StringItem(enum=['red', 'green', 'blue'])
                },
                additional_properties=schema.OneOfItem(items=[
                    schema.BooleanItem(),
                    schema.IntegerItem()
                ])
            )

        try:
            jsonschema.validate({'item': {'sides': 1,
                                          'color': 'red',
                                          'rugged_surface': False}}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': {'sides': '4', 'color': 'blue'}}, TestConf.serialize())
        self.assertIn('is not valid under any of the given schemas', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.DictItem(
                title='Poligon',
                description='Describe the Poligon',
                properties={
                    'color': schema.StringItem(enum=['red', 'green', 'blue'])
                },
                additional_properties=schema.OneOfItem(items=[
                    schema.BooleanItem(),
                    schema.IntegerItem()
                ]),
                min_properties=2,
                max_properties=3
            )

        try:
            jsonschema.validate({'item': {'color': 'red', 'sides': 1}}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate({'item': {'sides': 1, 'color': 'red', 'rugged_surface': False}}, TestConf.serialize())
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': {'color': 'blue'}}, TestConf.serialize())
        self.assertIn('does not have enough properties', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': {'sides': 4,
                                          'color': 'blue',
                                          'rugged_surface': False,
                                          'opaque': True}}, TestConf.serialize())
        self.assertIn('has too many properties', excinfo.exception.message)

        class TestConf(schema.Schema):
            item = schema.DictItem(
                title='Poligon',
                description='Describe the Poligon',
                properties={
                    'sides': schema.IntegerItem(required=True)
                },
                additional_properties=schema.OneOfItem(items=[schema.BooleanItem(),
                                                              schema.StringItem()])
            )

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': {'color': 'blue',
                                          'rugged_surface': False,
                                          'opaque': True}}, TestConf.serialize())
        self.assertIn('\'sides\' is a required property', excinfo.exception.message)

        class Props(schema.Schema):
            sides = schema.IntegerItem(required=True)

        class TestConf(schema.Schema):
            item = schema.DictItem(
                title='Poligon',
                description='Describe the Poligon',
                properties=Props(),
                additional_properties=schema.OneOfItem(items=[schema.BooleanItem(),
                                                              schema.StringItem()])
            )

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate({'item': {'color': 'blue',
                                          'rugged_surface': False,
                                          'opaque': True}}, TestConf.serialize())
        self.assertIn('\'sides\' is a required property', excinfo.exception.message)

    def test_oneof_config(self):
        item = schema.OneOfItem(
            items=(schema.StringItem(title='Yes', enum=['yes']),
                   schema.StringItem(title='No', enum=['no']))
        )
        self.assertEqual(
            item.serialize(), {
                'oneOf': [i.serialize() for i in item.items]
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_oneof_config_validation(self):
        class TestConf(schema.Schema):
            item = schema.ArrayItem(
                title='Hungry',
                description='Are you hungry?',
                items=schema.OneOfItem(
                    items=(schema.StringItem(title='Yes', enum=['yes']),
                           schema.StringItem(title='No', enum=['no']))
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
        item = schema.AnyOfItem(
            items=(schema.StringItem(title='Yes', enum=['yes']),
                   schema.StringItem(title='No', enum=['no']))
        )
        self.assertEqual(
            item.serialize(), {
                'anyOf': [i.serialize() for i in item.items]  # pylint: disable=E1133
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_anyof_config_validation(self):
        class TestConf(schema.Schema):
            item = schema.ArrayItem(
                title='Hungry',
                description='Are you hungry?',
                items=schema.AnyOfItem(
                    items=(schema.StringItem(title='Yes', enum=['yes']),
                           schema.StringItem(title='No', enum=['no']),
                           schema.BooleanItem())
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
        item = schema.AllOfItem(
            items=(schema.StringItem(min_length=2),
                   schema.StringItem(max_length=3))
        )
        self.assertEqual(
            item.serialize(), {
                'allOf': [i.serialize() for i in item.items]  # pylint: disable=E1133
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_allof_config_validation(self):
        class TestConf(schema.Schema):
            item = schema.ArrayItem(
                title='Hungry',
                description='Are you hungry?',
                items=schema.AllOfItem(
                    items=(schema.StringItem(min_length=2),
                           schema.StringItem(max_length=3))
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
        item = schema.NotItem(item=schema.BooleanItem())
        self.assertEqual(
            item.serialize(), {
                'not': item.item.serialize()
            }
        )

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_not_config_validation(self):
        class TestConf(schema.Schema):
            item = schema.ArrayItem(
                title='Hungry',
                description='Are you hungry?',
                items=schema.NotItem(item=schema.BooleanItem())
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

    def test_item_name_override_class_attrname(self):
        class TestConf(schema.Schema):
            item = schema.BooleanItem(name='hungry', title='Hungry', description='Are you hungry?')

        expected = {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "type": "object",
            "properties": {
                "hungry": {
                    "type": "boolean",
                    "description": "Are you hungry?",
                    "title": "Hungry"
                }
            },
            "x-ordering": [
                "hungry"
            ],
            "additionalProperties": False
        }
        self.assertDictEqual(TestConf.serialize(), expected)

    def test_config_name_override_class_attrname(self):
        class TestConf(schema.Schema):
            item = schema.BooleanItem(title='Hungry', description='Are you hungry?')

        class TestConf2(schema.Schema):
            a_name = TestConf(name='another_name')

        expected = {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "type": "object",
            "properties": {
                "another_name": {
                    "id": "https://non-existing.saltstack.com/schemas/another_name.json#",
                    "type": "object",
                    "properties": {
                        "item": {
                            "type": "boolean",
                            "description": "Are you hungry?",
                            "title": "Hungry"
                        }
                    },
                    "x-ordering": [
                        "item"
                    ],
                    "additionalProperties": False
                }
            },
            "x-ordering": [
                "another_name"
            ],
            "additionalProperties": False
        }
        self.assertDictEqual(TestConf2.serialize(), expected)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(ConfigTestCase, needs_daemon=False)
