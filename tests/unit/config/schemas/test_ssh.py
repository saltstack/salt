# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`

    tests.unit.config.schemas.test_ssh
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''
# Import python libs
from __future__ import absolute_import, print_function

# Import Salt Testing Libs
from tests.support.unit import TestCase, skipIf

# Import Salt Libs
from salt.config.schemas import ssh as ssh_schemas
from salt.config.schemas.minion import MinionConfiguration
from salt.utils.versions import LooseVersion as _LooseVersion

# Import 3rd-party libs
import salt.ext.six as six
try:
    import jsonschema
    import jsonschema.exceptions
    HAS_JSONSCHEMA = True
    JSONSCHEMA_VERSION = _LooseVersion(jsonschema.__version__)
except ImportError:
    HAS_JSONSCHEMA = False
    JSONSCHEMA_VERSION = _LooseVersion('0')


@skipIf(six.PY3, 'Tests disabled under Python 3')
class RoosterEntryConfigTest(TestCase):
    def test_config(self):
        config = ssh_schemas.RosterEntryConfig()

        expected = {
            '$schema': 'http://json-schema.org/draft-04/schema#',
            'title': 'Roster Entry',
            'description': 'Salt SSH roster entry definition',
            'type': 'object',
            'properties': {
                'host': {
                    'title': 'Host',
                    'description': 'The IP address or DNS name of the remote host',
                    'type': 'string',
                    'pattern': r'^((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})|([A-Za-z0-9][A-Za-z0-9\.\-]{1,255}))$',
                    'minLength': 1
                },
                'port': {
                    'description': 'The target system\'s ssh port number',
                    'title': 'Port',
                    'default': 22,
                    'maximum': 65535,
                    'minimum': 0,
                    'type': 'integer'
                },
                'user': {
                    'default': 'root',
                    'type': 'string',
                    'description': 'The user to log in as. Defaults to root',
                    'title': 'User',
                    'minLength': 1
                },
                'passwd': {
                    'title': 'Password',
                    'type': 'string',
                    'description': 'The password to log in with',
                    'format': 'secret',
                    'minLength': 1
                },
                'priv': {
                    'type': 'string',
                    'description': 'File path to ssh private key, defaults to salt-ssh.rsa',
                    'title': 'Private Key',
                    'minLength': 1
                },
                'sudo': {
                    'default': False,
                    'type': 'boolean',
                    'description': 'run command via sudo. Defaults to False',
                    'title': 'Sudo'
                },
                'timeout': {
                    'type': 'integer',
                    'description': 'Number of seconds to wait for response when establishing an SSH connection',
                    'title': 'Timeout'
                },
                'thin_dir': {
                    'type': 'string',
                    'description': 'The target system\'s storage directory for Salt components. Defaults to /tmp/salt-<hash>.',
                    'title': 'Thin Directory'
                },
                # The actuall representation of the minion options would make this HUGE!
                'minion_opts': ssh_schemas.DictItem(title='Minion Options',
                                                    description='Dictionary of minion options',
                                                    properties=MinionConfiguration()).serialize(),
            },
            'anyOf': [
                {
                    'required': [
                        'passwd'
                    ]
                },
                {
                    'required': [
                        'priv'
                    ]
                }
            ],
            'required': [
                'host',
                'user',
            ],
            'x-ordering': [
                'host',
                'port',
                'user',
                'passwd',
                'priv',
                'sudo',
                'timeout',
                'thin_dir',
                'minion_opts'
            ],
            'additionalProperties': False
        }
        try:
            self.assertDictContainsSubset(expected['properties'], config.serialize()['properties'])
            self.assertDictContainsSubset(expected, config.serialize())
        except AssertionError:
            import json
            print(json.dumps(config.serialize(), indent=4))
            raise

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_config_validate(self):
        try:
            jsonschema.validate(
                {
                    'host': 'localhost',
                    'user': 'root',
                    'passwd': 'foo'
                },
                ssh_schemas.RosterEntryConfig.serialize(),
                format_checker=jsonschema.FormatChecker()
            )
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate(
                {
                    'host': '127.0.0.1',
                    'user': 'root',
                    'passwd': 'foo'
                },
                ssh_schemas.RosterEntryConfig.serialize(),
                format_checker=jsonschema.FormatChecker()
            )
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate(
                {
                    'host': '127.1.0.1',
                    'user': 'root',
                    'priv': 'foo',
                    'passwd': 'foo'
                },
                ssh_schemas.RosterEntryConfig.serialize(),
                format_checker=jsonschema.FormatChecker()
            )
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate(
                {
                    'host': '127.1.0.1',
                    'user': 'root',
                    'passwd': 'foo',
                    'sudo': False
                },
                ssh_schemas.RosterEntryConfig.serialize(),
                format_checker=jsonschema.FormatChecker()
            )
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate(
                {
                    'host': '127.1.0.1',
                    'user': 'root',
                    'priv': 'foo',
                    'passwd': 'foo',
                    'thin_dir': '/foo/bar'
                },
                ssh_schemas.RosterEntryConfig.serialize(),
                format_checker=jsonschema.FormatChecker()
            )
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        try:
            jsonschema.validate(
                {
                    'host': '127.1.0.1',
                    'user': 'root',
                    'passwd': 'foo',
                    'minion_opts': {
                        'interface': '0.0.0.0'
                    }
                },
                ssh_schemas.RosterEntryConfig.serialize(),
                format_checker=jsonschema.FormatChecker()
            )
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate(
                {
                    'host': '127.1.0.1',
                    'user': '',
                    'passwd': 'foo',
                },
                ssh_schemas.RosterEntryConfig.serialize(),
                format_checker=jsonschema.FormatChecker()
            )
        self.assertIn('is too short', excinfo.exception.message)

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate(
                {
                    'host': '127.1.0.1',
                    'user': 'root',
                    'passwd': 'foo',
                    'minion_opts': {
                        'interface': 0
                    }
                },
                ssh_schemas.RosterEntryConfig.serialize(),
                format_checker=jsonschema.FormatChecker()
            )
        self.assertIn('is not of type', excinfo.exception.message)


class RosterItemTest(TestCase):

    def test_roster_config(self):
        try:
            self.assertDictContainsSubset(
                {
                    "$schema": "http://json-schema.org/draft-04/schema#",
                    "title": "Roster Configuration",
                    "description": "Roster entries definition",
                    "type": "object",
                    "patternProperties": {
                        r"^([^:]+)$": ssh_schemas.RosterEntryConfig.serialize()
                    },
                    "additionalProperties": False
                },
                ssh_schemas.RosterItem.serialize()
            )
        except AssertionError:
            import json
            print(json.dumps(ssh_schemas.RosterItem.serialize(), indent=4))
            raise

    @skipIf(HAS_JSONSCHEMA is False, 'The \'jsonschema\' library is missing')
    def test_roster_config_validate(self):
        try:
            jsonschema.validate(
                {'target-1':
                    {
                        'host': 'localhost',
                        'user': 'root',
                        'passwd': 'foo'
                    }
                },
                ssh_schemas.RosterItem.serialize(),
                format_checker=jsonschema.FormatChecker()
            )
        except jsonschema.exceptions.ValidationError as exc:
            self.fail('ValidationError raised: {0}'.format(exc))

        with self.assertRaises(jsonschema.exceptions.ValidationError) as excinfo:
            jsonschema.validate(
                {'target-1:1':
                    {
                        'host': 'localhost',
                        'user': 'root',
                        'passwd': 'foo'
                    }
                },
                ssh_schemas.RosterItem.serialize(),
                format_checker=jsonschema.FormatChecker()
            )
        if JSONSCHEMA_VERSION < _LooseVersion('2.6.0'):
            self.assertIn(
                'Additional properties are not allowed (\'target-1:1\' was unexpected)',
                excinfo.exception.message
            )
        else:
            self.assertIn(
                '\'target-1:1\' does not match any of the regexes',
                excinfo.exception.message
            )
