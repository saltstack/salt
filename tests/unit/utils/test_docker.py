# -*- coding: utf-8 -*-
'''
tests.unit.utils.test_docker
============================

Test the funcs in salt.utils.docker and salt.utils.docker.translate
'''
# Import Python Libs
from __future__ import absolute_import
import functools
import logging

log = logging.getLogger(__name__)

# Import Salt Testing Libs
from tests.support.unit import TestCase

# Import salt libs
import salt.config
import salt.loader
import salt.utils.docker as docker_utils
import salt.utils.docker.translate as translate_funcs

# Import 3rd-party libs
from salt.ext import six


def test_skip_translate(testcase, name):
    '''
    Ensure that skip_translate is checked. This function is called from the
    tearDown for the TranslateInputTestCase.

    Note that the example arguments used are in many cases not valid input for
    the Docker API, but these assertions confirm that we successfully skipped
    translation (which is what we are actually testing).
    '''
    testcase.assertEqual(
        docker_utils.translate_input(
            **{name: 'foo', 'skip_translate': True}
        ),
        ({name: 'foo'}, {}, [])
    )
    testcase.assertEqual(
        docker_utils.translate_input(
            **{name: 'foo', 'skip_translate': [name]}
        ),
        ({name: 'foo'}, {}, [])
    )


def __test_stringlist(testcase, name):
    alias = salt.utils.docker.ALIASES_REVMAP.get(name)
    # Using file paths here because "volumes" must be passed through this
    # set of assertions and it requires absolute paths.
    if salt.utils.is_windows():
        data = [r'c:\foo', r'c:\bar', r'c:\baz']
    else:
        data = ['/foo', '/bar', '/baz']
    for item in (name, alias):
        if item is None:
            continue
        testcase.assertEqual(
            docker_utils.translate_input(**{item: ','.join(data)}),
            ({name: data}, {}, [])
        )
        testcase.assertEqual(
            docker_utils.translate_input(**{item: data}),
            ({name: data}, {}, [])
        )
        if name != 'volumes':
            # Test coercing to string
            testcase.assertEqual(
                docker_utils.translate_input(**{item: ['one', 2]}),
                ({name: ['one', '2']}, {}, [])
            )
    if alias is not None:
        # Test collision
        testcase.assertEqual(
            docker_utils.translate_input(**{name: data, alias: sorted(data)}),
            ({name: data}, {}, [name])
        )


def __test_key_value(testcase, name, delimiter):
    '''
    Common logic for key/value pair testing
    '''
    alias = salt.utils.docker.ALIASES_REVMAP.get(name)
    expected = {'foo': 'bar', 'baz': 'qux'}
    for item in (name, alias):
        if item is None:
            continue
        testcase.assertEqual(
            docker_utils.translate_input(
                **{item: 'foo{0}bar,baz{0}qux'.format(delimiter)}),
            ({name: expected}, {}, [])
        )
        # This two are contrived examples, but they will test bool-ifying a
        # non-bool value to ensure proper input format.
        testcase.assertEqual(
            docker_utils.translate_input(
                **{item: ['foo{0}bar'.format(delimiter),
                          'baz{0}qux'.format(delimiter)]}
            ),
            ({name: expected}, {}, [])
        )
        testcase.assertEqual(
            docker_utils.translate_input(**{item: expected}),
            ({name: expected}, {}, [])
        )
        # "Dictlist" input from states
        testcase.assertEqual(
            docker_utils.translate_input(
                **{item: [{'foo': 'bar'}, {'baz': 'qux'}]}
            ),
            ({name: expected}, {}, [])
        )
        # Passing a non-string should be converted to a string
        testcase.assertEqual(
            docker_utils.translate_input(labels=1.0),
            ({'labels': ['1.0']}, {}, [])
        )
    if alias is not None:
        # Test collision
        testcase.assertEqual(
            docker_utils.translate_input(
                **{name: 'foo{0}bar,baz{0}qux'.format(delimiter),
                   alias: 'hello{0}world'.format(delimiter)}),
            ({name: expected}, {}, [name])
        )


def test_bool(func):
    '''
    Test a boolean value
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]
        alias = salt.utils.docker.ALIASES_REVMAP.get(name)
        for item in (name, alias):
            if item is None:
                continue
            self.assertEqual(
                docker_utils.translate_input(**{item: True}),
                ({name: True}, {}, [])
            )
            # This two are contrived examples, but they will test bool-ifying a
            # non-bool value to ensure proper input format.
            self.assertEqual(
                docker_utils.translate_input(**{item: 'foo'}),
                ({name: True}, {}, [])
            )
            self.assertEqual(
                docker_utils.translate_input(**{item: 0}),
                ({name: False}, {}, [])
            )
        if alias is not None:
            # Test collision
            self.assertEqual(
                docker_utils.translate_input(**{name: True, alias: False}),
                ({name: True}, {}, [name])
            )
        return func(self, *args, **kwargs)
    return wrapper


def test_int(func):
    '''
    Test an integer value
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]
        alias = salt.utils.docker.ALIASES_REVMAP.get(name)
        for item in (name, alias):
            if item is None:
                continue
            self.assertEqual(
                docker_utils.translate_input(**{item: 100}),
                ({name: 100}, {}, [])
            )
            self.assertEqual(
                docker_utils.translate_input(**{item: '200'}),
                ({name: 200}, {}, [])
            )
            # Error case: non-numeric value passed
            self.assertEqual(
                docker_utils.translate_input(**{item: 'foo'}),
                ({}, {item: '\'foo\' is not an integer'}, [])
            )
        if alias is not None:
            # Test collision
            self.assertEqual(
                docker_utils.translate_input(**{name: 100, alias: 200}),
                ({name: 100}, {}, [name])
            )
        return func(self, *args, **kwargs)
    return wrapper


def test_string(func):
    '''
    Test that item is a string or is converted to one
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]
        alias = salt.utils.docker.ALIASES_REVMAP.get(name)
        # Using file paths here because "working_dir" must be passed through
        # this set of assertions and it requires absolute paths.
        if salt.utils.is_windows():
            data = r'c:\foo'
        else:
            data = '/foo'
        for item in (name, alias):
            if item is None:
                continue
            self.assertEqual(
                docker_utils.translate_input(**{item: data}),
                ({name: data}, {}, [])
            )
            if name != 'working_dir':
                # Test coercing to string
                self.assertEqual(
                    docker_utils.translate_input(**{item: 123}),
                    ({name: '123'}, {}, [])
                )
        if alias is not None:
            # Test collision
            self.assertEqual(
                docker_utils.translate_input(**{name: data, alias: data}),
                ({name: data}, {}, [name])
            )
        return func(self, *args, **kwargs)
    return wrapper


def test_int_or_string(func):
    '''
    Test an integer or string value
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]
        alias = salt.utils.docker.ALIASES_REVMAP.get(name)
        for item in (name, alias):
            if item is None:
                continue
            self.assertEqual(
                docker_utils.translate_input(**{item: 100}),
                ({name: 100}, {}, [])
            )
            self.assertEqual(
                docker_utils.translate_input(**{item: '100M'}),
                ({name: '100M'}, {}, [])
            )
        if alias is not None:
            # Test collision
            self.assertEqual(
                docker_utils.translate_input(**{name: 100, alias: '100M'}),
                ({name: 100}, {}, [name])
            )
        return func(self, *args, **kwargs)
    return wrapper


def test_stringlist(func):
    '''
    Test a comma-separated or Python list of strings
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]
        __test_stringlist(self, name)
        return func(self, *args, **kwargs)
    return wrapper


def test_dict(func):
    '''
    Dictionaries should be untouched, dictlists should be repacked and end up
    as a single dictionary.
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]
        alias = salt.utils.docker.ALIASES_REVMAP.get(name)
        expected = {'foo': 'bar', 'baz': 'qux'}
        for item in (name, alias):
            if item is None:
                continue
            self.assertEqual(
                docker_utils.translate_input(**{item: expected}),
                ({name: expected}, {}, [])
            )
            # "Dictlist" input from states
            self.assertEqual(
                docker_utils.translate_input(
                    **{item: [{x: y} for x, y in six.iteritems(expected)]}
                ),
                ({name: expected}, {}, [])
            )
            # Error case: non-dictionary input
            self.assertEqual(
                docker_utils.translate_input(**{item: 'foo'}),
                ({}, {item: '\'foo\' is not a dictionary'}, [])
            )
        if alias is not None:
            # Test collision
            self.assertEqual(
                docker_utils.translate_input(**{name: 'foo', alias: 'bar'}),
                ({name: 'foo'}, {}, [name])
            )
        return func(self, *args, **kwargs)
    return wrapper


def test_cmd(func):
    '''
    Test for a string, or a comma-separated or Python list of strings. This is
    different from a stringlist in that we do not do any splitting. This
    decorator is used both by the "command" and "entrypoint" arguments.
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]
        alias = salt.utils.docker.ALIASES_REVMAP.get(name)
        for item in (name, alias):
            if item is None:
                continue
            self.assertEqual(
                docker_utils.translate_input(**{item: 'foo bar'}),
                ({name: 'foo bar'}, {}, [])
            )
            self.assertEqual(
                docker_utils.translate_input(**{item: ['foo', 'bar']}),
                ({name: ['foo', 'bar']}, {}, [])
            )
            # Test coercing to string
            self.assertEqual(
                docker_utils.translate_input(**{item: 123}),
                ({name: '123'}, {}, [])
            )
            self.assertEqual(
                docker_utils.translate_input(**{item: ['one', 2]}),
                ({name: ['one', '2']}, {}, [])
            )
        if alias is not None:
            # Test collision
            self.assertEqual(
                docker_utils.translate_input(**{name: 'foo', alias: 'bar'}),
                ({name: 'foo'}, {}, [name])
            )
        return func(self, *args, **kwargs)
    return wrapper


def test_key_colon_value(func):
    '''
    Test a key/value pair with parameters passed as key:value pairs
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]
        __test_key_value(self, name, ':')
        return func(self, *args, **kwargs)
    return wrapper


def test_key_equals_value(func):
    '''
    Test a key/value pair with parameters passed as key=value pairs
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]
        __test_key_value(self, name, '=')
        if name == 'labels':
            __test_stringlist(self, name)
        return func(self, *args, **kwargs)
    return wrapper


def test_device_rates(func):
    '''
    Tests for device_{read,write}_{bps,iops}. The bps values have a "Rate"
    value expressed in bytes/kb/mb/gb, while the iops values have a "Rate"
    expressed as a simple integer.
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # Strip off the "test_" from the function name
        name = func.__name__[5:]
        alias = salt.utils.docker.ALIASES_REVMAP.get(name)
        for item in (name, alias):
            if item is None:
                continue

            # Error case: Not an absolute path
            if salt.utils.is_windows():
                path = r'foo\bar\baz'
            else:
                path = 'foo/bar/baz'

            self.assertEqual(
                docker_utils.translate_input(
                    **{item: '{0}:1048576'.format(path)}
                ),
                (
                    {},
                    {item: 'Path \'{0}\' is not absolute'.format(path)},
                    []
                )
            )

            if name.endswith('_bps'):
                # Both integer bytes and a string providing a shorthand for kb,
                # mb, or gb can be used, so we need to test for both.
                expected = (
                    {name: [{'Path': '/dev/sda', 'Rate': 1048576},
                            {'Path': '/dev/sdb', 'Rate': 1048576}]},
                    {}, []
                )
                self.assertEqual(
                    docker_utils.translate_input(
                        **{item: '/dev/sda:1048576,/dev/sdb:1048576'}
                    ),
                    expected
                )
                self.assertEqual(
                    docker_utils.translate_input(
                        **{item: ['/dev/sda:1048576', '/dev/sdb:1048576']}
                    ),
                    expected
                )
                expected = (
                    {name: [{'Path': '/dev/sda', 'Rate': '1mb'},
                            {'Path': '/dev/sdb', 'Rate': '5mb'}]},
                    {}, []
                )
                self.assertEqual(
                    docker_utils.translate_input(
                        **{item: '/dev/sda:1mb,/dev/sdb:5mb'}
                    ),
                    expected
                )
                self.assertEqual(
                    docker_utils.translate_input(
                        **{item: ['/dev/sda:1mb', '/dev/sdb:5mb']}
                    ),
                    expected
                )

                if alias is not None:
                    # Test collision
                    self.assertEqual(
                        docker_utils.translate_input(
                            **{name: '/dev/sda:1048576,/dev/sdb:1048576',
                               alias: '/dev/sda:1mb,/dev/sdb:5mb'}
                        ),
                        (
                            {name: [{'Path': '/dev/sda', 'Rate': 1048576},
                                    {'Path': '/dev/sdb', 'Rate': 1048576}]},
                            {}, [name]
                        )
                    )
            else:
                # The "Rate" value must be an integer
                expected = (
                    {name: [{'Path': '/dev/sda', 'Rate': 1000},
                            {'Path': '/dev/sdb', 'Rate': 500}]},
                    {}, []
                )
                self.assertEqual(
                    docker_utils.translate_input(
                        **{item: '/dev/sda:1000,/dev/sdb:500'}
                    ),
                    expected
                )
                self.assertEqual(
                    docker_utils.translate_input(
                        **{item: ['/dev/sda:1000', '/dev/sdb:500']}
                    ),
                    expected
                )
                # Test non-integer input
                expected = (
                    {},
                    {item: 'Rate \'5mb\' for path \'/dev/sdb\' is non-numeric'},
                    []
                )
                self.assertEqual(
                    docker_utils.translate_input(
                        **{item: '/dev/sda:1000,/dev/sdb:5mb'}
                    ),
                    expected
                )
                self.assertEqual(
                    docker_utils.translate_input(
                        **{item: ['/dev/sda:1000', '/dev/sdb:5mb']}
                    ),
                    expected
                )

                if alias is not None:
                    # Test collision
                    self.assertEqual(
                        docker_utils.translate_input(
                            **{name: '/dev/sda:1000,/dev/sdb:500',
                               alias: '/dev/sda:888,/dev/sdb:999'}
                        ),
                        (
                            {name: [{'Path': '/dev/sda', 'Rate': 1000},
                                    {'Path': '/dev/sdb', 'Rate': 500}]},
                            {}, [name]
                        )
                    )

        return func(self, *args, **kwargs)
    return wrapper


class TranslateInputTestCase(TestCase):
    '''
    Tests for salt.utils.docker.translate_input(). This function returns a
    3-tuple consisting of:

    1) A translated copy of the kwargs
    2) A dictionary mapping any invalid arguments to error messages describing
       why they are invalid
    3) A list of "collisions" (API arguments for which their alias was also
       provided)
    '''
    maxDiff = None

    def tearDown(self):
        '''
        Test skip_translate kwarg
        '''
        name = self.id().split('.')[-1][5:]
        # The below is not valid input for the Docker API, but these
        # assertions confirm that we successfully skipped translation.
        expected = ({name: 'foo'}, {}, [])
        self.assertEqual(
            docker_utils.translate_input(
                **{name: 'foo', 'skip_translate': True}
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                **{name: 'foo', 'skip_translate': [name]}
            ),
            expected
        )

    @test_bool
    def test_auto_remove(self):
        '''
        Should be a bool or converted to one
        '''
        pass

    def test_binds(self):
        '''
        Test the "binds" kwarg. Any volumes not defined in the "volumes" kwarg
        should be added to the results.
        '''
        self.assertEqual(
            docker_utils.translate_input(
                binds='/srv/www:/var/www:ro',
                volumes='/testing'),
            (
                {'binds': ['/srv/www:/var/www:ro'],
                 'volumes': ['/testing', '/var/www']},
                {},
                []
            )
        )
        self.assertEqual(
            docker_utils.translate_input(
                binds=['/srv/www:/var/www:ro'],
                volumes='/testing'),
            (
                {'binds': ['/srv/www:/var/www:ro'],
                 'volumes': ['/testing', '/var/www']},
                {},
                []
            )
        )
        self.assertEqual(
            docker_utils.translate_input(
                binds={'/srv/www': {'bind': '/var/www', 'mode': 'ro'}},
                volumes='/testing'),
            (
                {'binds': {'/srv/www': {'bind': '/var/www', 'mode': 'ro'}},
                 'volumes': ['/testing', '/var/www']},
                {},
                []
            )
        )

    @test_int
    def test_blkio_weight(self):
        '''
        Should be an int or converted to one
        '''
        pass

    def test_blkio_weight_device(self):
        '''
        Should translate a list of PATH:WEIGHT pairs to a list of dictionaries
        with the following format: {'Path': PATH, 'Weight': WEIGHT}
        '''
        expected = (
            {'blkio_weight_device': [{'Path': '/dev/sda', 'Weight': 100},
                                     {'Path': '/dev/sdb', 'Weight': 200}]},
            {}, []
        )
        self.assertEqual(
            docker_utils.translate_input(
                blkio_weight_device='/dev/sda:100,/dev/sdb:200'
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                blkio_weight_device=['/dev/sda:100', '/dev/sdb:200']
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(blkio_weight_device='foo'),
            (
                {},
                {'blkio_weight_device': '\'foo\' contains 1 value(s) '
                                        '(expected 2)'},
                []
            )
        )
        self.assertEqual(
            docker_utils.translate_input(blkio_weight_device='foo:bar:baz'),
            (
                {},
                {'blkio_weight_device': '\'foo:bar:baz\' contains 3 value(s) '
                                        '(expected 2)'},
                []
            )
        )
        self.assertEqual(
            docker_utils.translate_input(
                blkio_weight_device=['/dev/sda:100', '/dev/sdb:foo']
            ),
            (
                {},
                {'blkio_weight_device': 'Weight \'foo\' for path \'/dev/sdb\' '
                                        'is not an integer'},
                []
            )
        )

    @test_stringlist
    def test_cap_add(self):
        '''
        Should be a list of strings or converted to one
        '''
        pass

    @test_stringlist
    def test_cap_drop(self):
        '''
        Should be a list of strings or converted to one
        '''
        pass

    @test_cmd
    def test_command(self):
        '''
        Can either be a string or a comma-separated or Python list of strings.
        '''
        pass

    @test_string
    def test_cpuset_cpus(self):
        '''
        Should be a string or converted to one
        '''
        pass

    @test_string
    def test_cpuset_mems(self):
        '''
        Should be a string or converted to one
        '''
        pass

    @test_int
    def test_cpu_group(self):
        '''
        Should be an int or converted to one
        '''
        pass

    @test_int
    def test_cpu_period(self):
        '''
        Should be an int or converted to one
        '''
        pass

    @test_int
    def test_cpu_shares(self):
        '''
        Should be an int or converted to one
        '''
        pass

    @test_bool
    def test_detach(self):
        '''
        Should be a bool or converted to one
        '''
        pass

    @test_device_rates
    def test_device_read_bps(self):
        '''
        CLI input is a list of PATH:RATE pairs, but the API expects a list of
        dictionaries in the format [{'Path': path, 'Rate': rate}]
        '''
        pass

    @test_device_rates
    def test_device_read_iops(self):
        '''
        CLI input is a list of PATH:RATE pairs, but the API expects a list of
        dictionaries in the format [{'Path': path, 'Rate': rate}]
        '''
        pass

    @test_device_rates
    def test_device_write_bps(self):
        '''
        CLI input is a list of PATH:RATE pairs, but the API expects a list of
        dictionaries in the format [{'Path': path, 'Rate': rate}]
        '''
        pass

    @test_device_rates
    def test_device_write_iops(self):
        '''
        CLI input is a list of PATH:RATE pairs, but the API expects a list of
        dictionaries in the format [{'Path': path, 'Rate': rate}]
        '''
        pass

    @test_stringlist
    def test_devices(self):
        '''
        Should be a list of strings or converted to one
        '''
        pass

    @test_stringlist
    def test_dns_opt(self):
        '''
        Should be a list of strings or converted to one
        '''
        pass

    @test_stringlist
    def test_dns_search(self):
        '''
        Should be a list of strings or converted to one
        '''
        pass

    def test_dns(self):
        '''
        While this is a stringlist, it also supports IP address validation, so
        it can't use the test_stringlist decorator because we need to test both
        with and without validation, and it isn't necessary to make all other
        stringlist tests also do that same kind of testing.
        '''
        expected = ({'dns': ['8.8.8.8', '8.8.4.4']}, {}, [])
        self.assertEqual(
            docker_utils.translate_input(
                dns='8.8.8.8,8.8.4.4',
                validate_ip_addrs=True,
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                dns=['8.8.8.8', '8.8.4.4'],
                validate_ip_addrs=True,
            ),
            expected
        )

        # Error case: invalid IP address caught by validaton
        expected = ({}, {'dns': '\'8.8.8.888\' is not a valid IP address'}, [])
        self.assertEqual(
            docker_utils.translate_input(
                dns='8.8.8.888,8.8.4.4',
                validate_ip_addrs=True,
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                dns=['8.8.8.888', '8.8.4.4'],
                validate_ip_addrs=True,
            ),
            expected
        )

        # This is not valid input but it will test whether or not IP address
        # validation happened.
        expected = ({'dns': ['foo', 'bar']}, {}, [])
        self.assertEqual(
            docker_utils.translate_input(
                dns='foo,bar',
                validate_ip_addrs=False,
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                dns=['foo', 'bar'],
                validate_ip_addrs=False,
            ),
            expected
        )

    @test_stringlist
    def test_domainname(self):
        '''
        Should be a list of strings or converted to one
        '''
        pass

    @test_cmd
    def test_entrypoint(self):
        '''
        Can either be a string or a comma-separated or Python list of strings.
        '''
        pass

    @test_key_equals_value
    def test_environment(self):
        '''
        Can be passed in several formats but must end up as a dictionary
        mapping keys to values
        '''
        pass

    def test_extra_hosts(self):
        '''
        Can be passed as a list of key:value pairs but can't be simply tested
        using @test_key_colon_value since we need to test both with and without
        IP address validation.
        '''
        expected = (
            {'extra_hosts': {'web1': '10.9.8.7', 'web2': '10.9.8.8'}},
            {}, []
        )
        self.assertEqual(
            docker_utils.translate_input(
                extra_hosts='web1:10.9.8.7,web2:10.9.8.8',
                validate_ip_addrs=True,
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                extra_hosts=['web1:10.9.8.7', 'web2:10.9.8.8'],
                validate_ip_addrs=True,
            ),
            expected
        )

        expected = (
            {},
            {'extra_hosts': '\'10.9.8.299\' is not a valid IP address'},
            []
        )
        self.assertEqual(
            docker_utils.translate_input(
                extra_hosts='web1:10.9.8.299,web2:10.9.8.8',
                validate_ip_addrs=True,
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                extra_hosts=['web1:10.9.8.299', 'web2:10.9.8.8'],
                validate_ip_addrs=True,
            ),
            expected
        )

        # This is not valid input but it will test whether or not IP address
        # validation happened.
        expected = ({'extra_hosts': {'foo': 'bar', 'baz': 'qux'}}, {}, [])
        self.assertEqual(
            docker_utils.translate_input(
                extra_hosts='foo:bar,baz:qux',
                validate_ip_addrs=False,
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                extra_hosts=['foo:bar', 'baz:qux'],
                validate_ip_addrs=False,
            ),
            expected
        )

    @test_stringlist
    def test_group_add(self):
        '''
        Should be a list of strings or converted to one
        '''
        pass

    @test_string
    def test_hostname(self):
        '''
        Should be a string or converted to one
        '''
        pass

    @test_string
    def test_ipc_mode(self):
        '''
        Should be a string or converted to one
        '''
        pass

    @test_string
    def test_isolation(self):
        '''
        Should be a string or converted to one
        '''
        pass

    @test_key_equals_value
    def test_labels(self):
        '''
        Can be passed as a list of key=value pairs or a dictionary, and must
        ultimately end up as a dictionary.
        '''
        pass

    @test_key_colon_value
    def test_links(self):
        '''
        Can be passed as a list of key:value pairs or a dictionary, and must
        ultimately end up as a dictionary.
        '''
        pass

    def test_log_config(self):
        '''
        This is a mixture of log_driver and log_opt, which get combined into a
        dictionary.

        log_driver is a simple string, but log_opt can be passed in several
        ways, so we need to test them all.
        '''
        expected = (
            {'log_config': {'Type': 'foo',
                            'Config': {'foo': 'bar', 'baz': 'qux'}}},
            {}, []
        )
        self.assertEqual(
            docker_utils.translate_input(
                log_driver='foo',
                log_opt='foo=bar,baz=qux'
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                log_driver='foo',
                log_opt=['foo=bar', 'baz=qux']
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                log_driver='foo',
                log_opt={'foo': 'bar', 'baz': 'qux'}
            ),
            expected
        )

    @test_key_equals_value
    def test_lxc_conf(self):
        '''
        Can be passed as a list of key=value pairs or a dictionary, and must
        ultimately end up as a dictionary.
        '''
        pass

    @test_string
    def test_mac_address(self):
        '''
        Should be a string or converted to one
        '''
        pass

    @test_int_or_string
    def test_mem_limit(self):
        '''
        Should be a string or converted to one
        '''
        pass

    @test_int
    def test_mem_swappiness(self):
        '''
        Should be an int or converted to one
        '''
        pass

    @test_int_or_string
    def test_memswap_limit(self):
        '''
        Should be a string or converted to one
        '''
        pass

    @test_string
    def test_name(self):
        '''
        Should be a string or converted to one
        '''
        pass

    @test_bool
    def test_network_disabled(self):
        '''
        Should be a bool or converted to one
        '''
        pass

    @test_string
    def test_network_mode(self):
        '''
        Should be a string or converted to one
        '''
        pass

    @test_bool
    def test_oom_kill_disable(self):
        '''
        Should be a bool or converted to one
        '''
        pass

    @test_int
    def test_oom_score_adj(self):
        '''
        Should be an int or converted to one
        '''
        pass

    @test_string
    def test_pid_mode(self):
        '''
        Should be a string or converted to one
        '''
        pass

    @test_int
    def test_pids_limit(self):
        '''
        Should be an int or converted to one
        '''
        pass

    def test_port_bindings(self):
        '''
        This has several potential formats and can include port ranges. It
        needs its own test.
        '''
        # ip:hostPort:containerPort - Bind a specific IP and port on the host
        # to a specific port within the container.
        expected = (
            {'port_bindings': {
                80: [('10.1.2.3', 8080), ('10.1.2.3', 8888)],
                3333: ('10.4.5.6', 3333),
                4505: ('10.7.8.9', 14505),
                4506: ('10.7.8.9', 14506),
                '81/udp': [('10.1.2.3', 8080), ('10.1.2.3', 8888)],
                '3334/udp': ('10.4.5.6', 3334),
                '5505/udp': ('10.7.8.9', 15505),
                '5506/udp': ('10.7.8.9', 15506)},
             'ports': [80, 3333, 4505, 4506,
                       '3334/udp', '5505/udp', '5506/udp', '81/udp'],
            },
            {}, []
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings='10.1.2.3:8080:80,10.1.2.3:8888:80,10.4.5.6:3333:3333,10.7.8.9:14505-14506:4505-4506,10.1.2.3:8080:81/udp,10.1.2.3:8888:81/udp,10.4.5.6:3334:3334/udp,10.7.8.9:15505-15506:5505-5506/udp',
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings=[
                    '10.1.2.3:8080:80',
                    '10.1.2.3:8888:80',
                    '10.4.5.6:3333:3333',
                    '10.7.8.9:14505-14506:4505-4506',
                    '10.1.2.3:8080:81/udp',
                    '10.1.2.3:8888:81/udp',
                    '10.4.5.6:3334:3334/udp',
                    '10.7.8.9:15505-15506:5505-5506/udp']
            ),
            expected
        )

        # ip::containerPort - Bind a specific IP and an ephemeral port to a
        # specific port within the container.
        expected = (
            {'port_bindings': {
                80: [('10.1.2.3',), ('10.1.2.3',)],
                3333: ('10.4.5.6',),
                4505: ('10.7.8.9',),
                4506: ('10.7.8.9',),
                '81/udp': [('10.1.2.3',), ('10.1.2.3',)],
                '3334/udp': ('10.4.5.6',),
                '5505/udp': ('10.7.8.9',),
                '5506/udp': ('10.7.8.9',)},
             'ports': [80, 3333, 4505, 4506,
                       '3334/udp', '5505/udp', '5506/udp', '81/udp'],
            },
            {}, []
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings='10.1.2.3::80,10.1.2.3::80,10.4.5.6::3333,10.7.8.9::4505-4506,10.1.2.3::81/udp,10.1.2.3::81/udp,10.4.5.6::3334/udp,10.7.8.9::5505-5506/udp',
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings=[
                    '10.1.2.3::80',
                    '10.1.2.3::80',
                    '10.4.5.6::3333',
                    '10.7.8.9::4505-4506',
                    '10.1.2.3::81/udp',
                    '10.1.2.3::81/udp',
                    '10.4.5.6::3334/udp',
                    '10.7.8.9::5505-5506/udp']
            ),
            expected
        )

        # hostPort:containerPort - Bind a specific port on all of the host's
        # interfaces to a specific port within the container.
        expected = (
            {'port_bindings': {80: [8080, 8888],
                               3333: 3333,
                               4505: 14505,
                               4506: 14506,
                               '81/udp': [8080, 8888],
                               '3334/udp': 3334,
                               '5505/udp': 15505,
                               '5506/udp': 15506},
             'ports': [80, 3333, 4505, 4506,
                       '3334/udp', '5505/udp', '5506/udp', '81/udp'],
            },
            {}, []
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings='8080:80,8888:80,3333:3333,14505-14506:4505-4506,8080:81/udp,8888:81/udp,3334:3334/udp,15505-15506:5505-5506/udp',
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings=['8080:80',
                               '8888:80',
                               '3333:3333',
                               '14505-14506:4505-4506',
                               '8080:81/udp',
                               '8888:81/udp',
                               '3334:3334/udp',
                               '15505-15506:5505-5506/udp']
            ),
            expected
        )

        # containerPort - Bind an ephemeral port on all of the host's
        # interfaces to a specific port within the container.
        expected = (
            {'port_bindings': {80: None,
                               3333: None,
                               4505: None,
                               4506: None,
                               '81/udp': None,
                               '3334/udp': None,
                               '5505/udp': None,
                               '5506/udp': None},
             'ports': [80, 3333, 4505, 4506,
                       '3334/udp', '5505/udp', '5506/udp', '81/udp'],
            },
            {}, []
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings='80,3333,4505-4506,81/udp,3334/udp,5505-5506/udp',
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings=['80', '3333', '4505-4506',
                               '81/udp', '3334/udp', '5505-5506/udp']
            ),
            expected
        )

        # Test a mixture of different types of input
        expected = (
            {'port_bindings': {80: ('10.1.2.3', 8080),
                               3333: ('10.4.5.6',),
                               4505: 14505,
                               4506: 14506,
                               9999: None,
                               10000: None,
                               10001: None,
                               '81/udp': ('10.1.2.3', 8080),
                               '3334/udp': ('10.4.5.6',),
                               '5505/udp': 15505,
                               '5506/udp': 15506,
                               '19999/udp': None,
                               '20000/udp': None,
                               '20001/udp': None},
             'ports': [80, 3333, 4505, 4506, 9999, 10000, 10001,
                       '19999/udp', '20000/udp', '20001/udp',
                       '3334/udp', '5505/udp', '5506/udp', '81/udp']
            },
            {}, []
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings='10.1.2.3:8080:80,10.4.5.6::3333,14505-14506:4505-4506,9999-10001,10.1.2.3:8080:81/udp,10.4.5.6::3334/udp,15505-15506:5505-5506/udp,19999-20001/udp',
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings=[
                    '10.1.2.3:8080:80',
                    '10.4.5.6::3333',
                    '14505-14506:4505-4506',
                    '9999-10001',
                    '10.1.2.3:8080:81/udp',
                    '10.4.5.6::3334/udp',
                    '15505-15506:5505-5506/udp',
                    '19999-20001/udp']
            ),
            expected
        )

        # Error case: too many items (max 3)
        self.assertEqual(
            docker_utils.translate_input(port_bindings='10.1.2.3:8080:80:123'),
            (
                {},
                {'port_bindings': '\'10.1.2.3:8080:80:123\' is an invalid '
                                  'port binding definition (at most 3 '
                                  'components are allowed, found 4)'},
                []
            )
        )

        # Error case: port range start is greater than end
        expected = (
            {},
            {'port_bindings': 'Start of port range (5555) cannot be greater '
                              'than end of port range (5554)'},
            []
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings='10.1.2.3:5555-5554:1111-1112'
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings='10.1.2.3:1111-1112:5555-5554'
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(port_bindings='10.1.2.3::5555-5554'),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(port_bindings='5555-5554:1111-1112'),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(port_bindings='1111-1112:5555-5554'),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(port_bindings='5555-5554'),
            expected
        )

        # Error case: non-numeric port range
        expected = (
            {},
            {'port_bindings': '\'foo\' is non-numeric or an invalid port range'},
            []
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings='10.1.2.3:foo:1111-1112'
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings='10.1.2.3:1111-1112:foo'
            ),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(port_bindings='10.1.2.3::foo'),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(port_bindings='foo:1111-1112'),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(port_bindings='1111-1112:foo'),
            expected
        )
        self.assertEqual(
            docker_utils.translate_input(port_bindings='foo'),
            expected
        )

        # Error case: misatched port range
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings='10.1.2.3:1111-1113:1111-1112'
            ),
            (
                {},
                {'port_bindings': 'Host port range (1111-1113) does not have '
                                  'the same number of ports as the container '
                                  'port range (1111-1112)'},
                []
            )
        )
        self.assertEqual(
            docker_utils.translate_input(
                port_bindings='10.1.2.3:1111-1112:1111-1113'
            ),
            (
                {},
                {'port_bindings': 'Host port range (1111-1112) does not have '
                                  'the same number of ports as the container '
                                  'port range (1111-1113)'},
                []
            )
        )
        self.assertEqual(
            docker_utils.translate_input(port_bindings='1111-1113:1111-1112'),
            (
                {},
                {'port_bindings': 'Host port range (1111-1113) does not have '
                                  'the same number of ports as the container '
                                  'port range (1111-1112)'},
                []
            )
        )
        self.assertEqual(
            docker_utils.translate_input(port_bindings='1111-1112:1111-1113'),
            (
                {},
                {'port_bindings': 'Host port range (1111-1112) does not have '
                                  'the same number of ports as the container '
                                  'port range (1111-1113)'},
                []
            )
        )

        # Error case: empty host port or container port
        self.assertEqual(
            docker_utils.translate_input(port_bindings=':1111'),
            (
                {},
                {'port_bindings': 'Empty host port in port binding definition '
                                  '\':1111\''},
                []
            )
        )
        self.assertEqual(
            docker_utils.translate_input(port_bindings='1111:'),
            (
                {},
                {'port_bindings': 'Empty container port in port binding '
                                  'definition \'1111:\''},
                []
            )
        )
        self.assertEqual(
            docker_utils.translate_input(port_bindings=''),
            ({}, {'port_bindings': 'Empty port binding definition found'}, [])
        )

    def test_ports(self):
        '''
        Ports can be passed as a comma-separated or Python list of port
        numbers, with '/tcp' being optional for TCP ports. They must ultimately
        be a list of port definitions, in which an integer denotes a TCP port,
        and a tuple in the format (port_num, 'udp') denotes a UDP port. Also,
        the port numbers must end up as integers. None of the decorators will
        suffice so this one must be tested specially.
        '''
        expected = ({'ports': [1111, 2222, 4505, 4506, (3333, 'udp')]}, {}, [])
        # Comma-separated list
        self.assertEqual(
            docker_utils.translate_input(ports='1111,2222/tcp,3333/udp,4505-4506'),
            expected
        )
        # Python list
        self.assertEqual(
            docker_utils.translate_input(
                ports=[1111, '2222/tcp', '3333/udp', '4505-4506']
            ),
            expected
        )
        # Same as above but with the first port as a string (it should be
        # converted to an integer).
        self.assertEqual(
            docker_utils.translate_input(
                ports=['1111', '2222/tcp', '3333/udp', '4505-4506']
            ),
            expected
        )
        # Error case: argument passed as a list, but with a non-integer and
        # non/string value
        self.assertEqual(
            docker_utils.translate_input(ports=1.0),
            ({}, {'ports': '\'1.0\' is not a valid port definition'}, [])
        )
        self.assertEqual(
            docker_utils.translate_input(ports=[1.0]),
            ({}, {'ports': '\'1.0\' is not a valid port definition'}, [])
        )
        # Error case: port range start is greater than end
        self.assertEqual(
            docker_utils.translate_input(ports='5555-5554'),
            (
                {},
                {'ports': 'Start of port range (5555) cannot be greater than '
                          'end of port range (5554)'},
                []
            )
        )

    @test_bool
    def test_privileged(self):
        '''
        Should be a bool or converted to one
        '''
        pass

    @test_bool
    def test_publish_all_ports(self):
        '''
        Should be a bool or converted to one
        '''
        pass

    @test_bool
    def test_read_only(self):
        '''
        Should be a bool or converted to one
        '''
        pass

    def test_restart_policy(self):
        '''
        Input is in the format "name[:retry_count]", but the API wants it
        in the format {'Name': name, 'MaximumRetryCount': retry_count}
        '''
        for item in ('restart_policy', 'restart'):
            # Test with retry count
            self.assertEqual(
                docker_utils.translate_input(**{item: 'on-failure:5'}),
                (
                    {'restart_policy': {'Name': 'on-failure',
                                                'MaximumRetryCount': 5}},
                    {}, []
                )
            )
            # Test without retry count
            self.assertEqual(
                docker_utils.translate_input(**{item: 'on-failure'}),
                (
                    {'restart_policy': {'Name': 'on-failure',
                                                'MaximumRetryCount': 0}},
                    {}, []
                )
            )
            # Test collision
            self.assertEqual(
                docker_utils.translate_input(
                    restart_policy='on-failure:5',
                    restart='always'
                ),
                (
                    {'restart_policy': {'Name': 'on-failure',
                                        'MaximumRetryCount': 5}},
                    {},
                    ['restart_policy']
                )
            )
            # Error case: more than one policy passed
            self.assertEqual(
                docker_utils.translate_input(**{item: 'on-failure,always'}),
                ({}, {item: 'Only one policy is permitted'}, [])
            )

    @test_stringlist
    def test_security_opt(self):
        '''
        Should be a list of strings or converted to one
        '''
        pass

    @test_int_or_string
    def test_shm_size(self):
        '''
        Should be a string or converted to one
        '''
        pass

    @test_bool
    def test_stdin_open(self):
        '''
        Should be a bool or converted to one
        '''
        pass

    @test_string
    def test_stop_signal(self):
        '''
        Should be a string or converted to one
        '''
        pass

    @test_int
    def test_stop_timeout(self):
        '''
        Should be an int or converted to one
        '''
        pass

    @test_key_equals_value
    def test_storage_opt(self):
        '''
        Can be passed in several formats but must end up as a dictionary
        mapping keys to values
        '''
        pass

    @test_key_equals_value
    def test_sysctls(self):
        '''
        Can be passed in several formats but must end up as a dictionary
        mapping keys to values
        '''
        pass

    @test_dict
    def test_tmpfs(self):
        '''
        Can be passed in several formats but must end up as a dictionary
        mapping keys to values
        '''
        pass

    @test_bool
    def test_tty(self):
        '''
        Should be a bool or converted to one
        '''
        pass

    def test_ulimits(self):
        '''
        Input is in the format "name=soft_limit[:hard_limit]", but the API wants it
        in the format {'Name': name, 'Soft': soft_limit, 'Hard': hard_limit}
        '''
        # Test with and without hard limit
        self.assertEqual(
            docker_utils.translate_input(ulimits='nofile=1024:2048,nproc=50'),
            (
                {'ulimits': [{'Name': 'nofile', 'Soft': 1024, 'Hard': 2048},
                             {'Name': 'nproc', 'Soft': 50, 'Hard': 50}]},
                {}, []
            )
        )
        self.assertEqual(
            docker_utils.translate_input(
                ulimits=['nofile=1024:2048', 'nproc=50:50']
            ),
            (
                {'ulimits': [{'Name': 'nofile', 'Soft': 1024, 'Hard': 2048},
                             {'Name': 'nproc', 'Soft': 50, 'Hard': 50}]},
                {}, []
            )
        )

        # Error case: Invalid format
        self.assertEqual(
            docker_utils.translate_input(ulimits='nofile:1024:2048'),
            (
                {},
                {'ulimits': 'Ulimit definition \'nofile:1024:2048\' is not '
                            'in the format type=soft_limit[:hard_limit]'},
                []
            )
        )

        # Error case: Invalid format
        self.assertEqual(
            docker_utils.translate_input(ulimits='nofile=foo:2048'),
            (
                {},
                {'ulimits': 'Limit \'nofile=foo:2048\' contains non-numeric '
                            'value(s)'},
                []
            )
        )

    def test_user(self):
        '''
        Must be either username (string) or uid (int). An int passed as a
        string (e.g. '0') should be converted to an int.
        '''
        # Username passed as string
        self.assertEqual(
            docker_utils.translate_input(user='foo'),
            ({'user': 'foo'}, {}, [])
        )
        # Username passed as int
        self.assertEqual(
            docker_utils.translate_input(user=0),
            ({'user': 0}, {}, [])
        )
        # Username passed as stringified int
        self.assertEqual(
            docker_utils.translate_input(user='0'),
            ({'user': 0}, {}, [])
        )
        # Error case: non string/int passed
        self.assertEqual(
            docker_utils.translate_input(user=['foo']),
            ({}, {'user': 'Value must be a username or uid'}, [])
        )
        # Error case: negative int passed
        self.assertEqual(
            docker_utils.translate_input(user=-1),
            ({}, {'user': '\'-1\' is an invalid uid'}, [])
        )

    @test_string
    def test_userns_mode(self):
        '''
        Should be a bool or converted to one
        '''
        pass

    @test_string
    def test_volume_driver(self):
        '''
        Should be a bool or converted to one
        '''
        pass

    @test_stringlist
    def test_volumes(self):
        '''
        Should be a list of absolute paths
        '''
        # Error case: Not an absolute path
        if salt.utils.is_windows():
            path = r'foo\bar\baz'
        else:
            path = 'foo/bar/baz'
        self.assertEqual(
            docker_utils.translate_input(volumes=path),
            (
                {},
                {'volumes': '\'{0}\' is not an absolute path'.format(path)},
                []
            )
        )

    @test_stringlist
    def test_volumes_from(self):
        '''
        Should be a list of strings or converted to one
        '''
        pass

    @test_string
    def test_working_dir(self):
        '''
        Should be a single absolute path
        '''
        # Error case: Not an absolute path
        if salt.utils.is_windows():
            path = r'foo\bar\baz'
        else:
            path = 'foo/bar/baz'
        self.assertEqual(
            docker_utils.translate_input(volumes=path),
            (
                {},
                {'volumes': '\'{0}\' is not an absolute path'.format(path)},
                []
            )
        )


class DockerUtilsTestCase(TestCase):
    '''
    Tests for functions other than translate_input() in salt.utils.docker
    '''
    def test_get_repo_tag(self):
        # Pass image name without tag (take the default_tag value from 2nd arg)
        self.assertEqual(
            docker_utils.get_repo_tag('foo', 'bar'),
            ('foo', 'bar')
        )
        # Pass image name with tag (ignore the default_tag value from 2nd arg)
        self.assertEqual(
            docker_utils.get_repo_tag('foo:1.0', 'bar'),
            ('foo', '1.0')
        )
        # Pass numeric image (should be converted to string and assume the
        # default_tag value)
        self.assertEqual(
            docker_utils.get_repo_tag(123, 'bar'),
            ('123', 'bar')
        )
        # Edge case where someone passes an image name ending with a colon but
        # with no tag (should assume the default_tag value)
        self.assertEqual(
            docker_utils.get_repo_tag('foo:', 'bar'),
            ('foo', 'bar')
        )


class DockerTranslateHelperTestCase(TestCase):
    '''
    Tests for a couple helper functions in salt.utils.docker.translate
    '''
    def test_get_port_def(self):
        '''
        Test translation of port definition (1234, '1234/tcp', '1234/udp',
        etc.) into the format which docker-py uses (integer for TCP ports,
        'port_num/udp' for UDP ports).
        '''
        # Test TCP port (passed as int, no protocol passed)
        self.assertEqual(translate_funcs._get_port_def(2222), 2222)
        # Test TCP port (passed as str, no protocol passed)
        self.assertEqual(translate_funcs._get_port_def('2222'), 2222)
        # Test TCP port (passed as str, with protocol passed)
        self.assertEqual(translate_funcs._get_port_def('2222', 'tcp'), 2222)
        # Test TCP port (proto passed in port_num, with passed proto ignored).
        # This is a contrived example as we would never invoke the function in
        # this way, but it tests that we are taking the port number from the
        # port_num argument and ignoring the passed protocol.
        self.assertEqual(translate_funcs._get_port_def('2222/tcp', 'udp'), 2222)

        # Test UDP port (passed as int)
        self.assertEqual(translate_funcs._get_port_def(2222, 'udp'), (2222, 'udp'))
        # Test UDP port (passed as string)
        self.assertEqual(translate_funcs._get_port_def('2222', 'udp'), (2222, 'udp'))
        # Test UDP port (proto passed in port_num
        self.assertEqual(translate_funcs._get_port_def('2222/udp'), (2222, 'udp'))

    def test_get_port_range(self):
        '''
        Test extracting the start and end of a port range from a port range
        expression (e.g. 4505-4506)
        '''
        # Passing a single int should return the start and end as the same value
        self.assertEqual(translate_funcs._get_port_range(2222), (2222, 2222))
        # Same as above but with port number passed as a string
        self.assertEqual(translate_funcs._get_port_range('2222'), (2222, 2222))
        # Passing a port range
        self.assertEqual(translate_funcs._get_port_range('2222-2223'), (2222, 2223))
        # Error case: port range start is greater than end
        with self.assertRaisesRegexp(
                ValueError,
                r'Start of port range \(2222\) cannot be greater than end of '
                r'port range \(2221\)'):
            translate_funcs._get_port_range('2222-2221')
        # Error case: non-numeric input
        with self.assertRaisesRegexp(
                ValueError,
                '\'2222-bar\' is non-numeric or an invalid port range'):
            translate_funcs._get_port_range('2222-bar')
