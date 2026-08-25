"""
tests.unit.utils.test_dockermod
===============================

Test the funcs in salt.utils.dockermod and salt.utils.dockermod.translate
"""

import copy
import functools
import logging
import os

import salt.config
import salt.loader
import salt.utils.dockermod.translate.container
import salt.utils.dockermod.translate.network
import salt.utils.platform
from salt.exceptions import CommandExecutionError
from salt.utils.dockermod.translate import helpers as translate_helpers
from tests.support.unit import TestCase

log = logging.getLogger(__name__)


class Assert:
    def __init__(self, translator):
        self.translator = translator

    def __call__(self, func):
        self.func = func
        return functools.wraps(func)(
            # pylint: disable=unnecessary-lambda
            lambda testcase, *args, **kwargs: self.wrap(testcase, *args, **kwargs)
            # pylint: enable=unnecessary-lambda
        )

    def wrap(self, *args, **kwargs):
        raise NotImplementedError

    def test_stringlist(self, testcase, name):
        alias = self.translator.ALIASES_REVMAP.get(name)
        # Using file paths here because "volumes" must be passed through this
        # set of assertions and it requires absolute paths.
        if salt.utils.platform.is_windows():
            data = [r"c:\foo", r"c:\bar", r"c:\baz"]
        else:
            data = ["/foo", "/bar", "/baz"]
        for item in (name, alias):
            if item is None:
                continue
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, **{item: ",".join(data)}
                ),
                testcase.apply_defaults({name: data}),
            )
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(self.translator, **{item: data}),
                testcase.apply_defaults({name: data}),
            )
            if name != "volumes":
                # Test coercing to string
                testcase.assertEqual(
                    salt.utils.dockermod.translate_input(
                        self.translator, **{item: ["one", 2]}
                    ),
                    testcase.apply_defaults({name: ["one", "2"]}),
                )
        if alias is not None:
            # Test collision
            # sorted() used here because we want to confirm that we discard the
            # alias' value and go with the unsorted version.
            test_kwargs = {name: data, alias: sorted(data)}
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=True, **test_kwargs
                ),
                testcase.apply_defaults({name: test_kwargs[name]}),
            )
            with testcase.assertRaisesRegex(
                CommandExecutionError, "is an alias for.+cannot both be used"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=False, **test_kwargs
                )

    def test_key_value(self, testcase, name, delimiter):
        """
        Common logic for key/value pair testing. IP address validation is
        turned off here, and must be done separately in the wrapped function.
        """
        alias = self.translator.ALIASES_REVMAP.get(name)
        expected = {"foo": "bar", "baz": "qux"}
        vals = "foo{0}bar,baz{0}qux".format(delimiter)
        for item in (name, alias):
            if item is None:
                continue
            for val in (vals, vals.split(",")):
                testcase.assertEqual(
                    salt.utils.dockermod.translate_input(
                        self.translator, validate_ip_addrs=False, **{item: val}
                    ),
                    testcase.apply_defaults({name: expected}),
                )
            # Dictionary input
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, validate_ip_addrs=False, **{item: expected}
                ),
                testcase.apply_defaults({name: expected}),
            )
            # "Dictlist" input from states
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator,
                    validate_ip_addrs=False,
                    **{item: [{"foo": "bar"}, {"baz": "qux"}]},
                ),
                testcase.apply_defaults({name: expected}),
            )
        if alias is not None:
            # Test collision
            test_kwargs = {name: vals, alias: f"hello{delimiter}world"}
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator,
                    validate_ip_addrs=False,
                    ignore_collisions=True,
                    **test_kwargs,
                ),
                testcase.apply_defaults({name: expected}),
            )
            with testcase.assertRaisesRegex(
                CommandExecutionError, "is an alias for.+cannot both be used"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator,
                    validate_ip_addrs=False,
                    ignore_collisions=False,
                    **test_kwargs,
                )


class assert_bool(Assert):
    """
    Test a boolean value
    """

    def wrap(self, testcase, *args, **kwargs):  # pylint: disable=arguments-differ
        # Strip off the "test_" from the function name
        name = self.func.__name__[5:]
        alias = self.translator.ALIASES_REVMAP.get(name)
        for item in (name, alias):
            if item is None:
                continue
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(self.translator, **{item: True}),
                testcase.apply_defaults({name: True}),
            )
            # These two are contrived examples, but they will test bool-ifying
            # a non-bool value to ensure proper input format.
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(self.translator, **{item: "foo"}),
                testcase.apply_defaults({name: True}),
            )
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(self.translator, **{item: 0}),
                testcase.apply_defaults({name: False}),
            )
        if alias is not None:
            # Test collision
            test_kwargs = {name: True, alias: False}
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=True, **test_kwargs
                ),
                testcase.apply_defaults({name: test_kwargs[name]}),
            )
            with testcase.assertRaisesRegex(
                CommandExecutionError, "is an alias for.+cannot both be used"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=False, **test_kwargs
                )
        return self.func(testcase, *args, **kwargs)


class assert_int(Assert):
    """
    Test an integer value
    """

    def wrap(self, testcase, *args, **kwargs):  # pylint: disable=arguments-differ
        # Strip off the "test_" from the function name
        name = self.func.__name__[5:]
        alias = self.translator.ALIASES_REVMAP.get(name)
        for item in (name, alias):
            if item is None:
                continue
            for val in (100, "100"):
                testcase.assertEqual(
                    salt.utils.dockermod.translate_input(
                        self.translator, **{item: val}
                    ),
                    testcase.apply_defaults({name: 100}),
                )
            # Error case: non-numeric value passed
            with testcase.assertRaisesRegex(
                CommandExecutionError, "'foo' is not an integer"
            ):
                salt.utils.dockermod.translate_input(self.translator, **{item: "foo"})
        if alias is not None:
            # Test collision
            test_kwargs = {name: 100, alias: 200}
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=True, **test_kwargs
                ),
                testcase.apply_defaults({name: test_kwargs[name]}),
            )
            with testcase.assertRaisesRegex(
                CommandExecutionError, "is an alias for.+cannot both be used"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=False, **test_kwargs
                )
        return self.func(testcase, *args, **kwargs)


class assert_string(Assert):
    """
    Test that item is a string or is converted to one
    """

    def wrap(self, testcase, *args, **kwargs):  # pylint: disable=arguments-differ
        # Strip off the "test_" from the function name
        name = self.func.__name__[5:]
        alias = self.translator.ALIASES_REVMAP.get(name)
        # Using file paths here because "working_dir" must be passed through
        # this set of assertions and it requires absolute paths.
        if salt.utils.platform.is_windows():
            data = r"c:\foo"
        else:
            data = "/foo"
        for item in (name, alias):
            if item is None:
                continue
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(self.translator, **{item: data}),
                testcase.apply_defaults({name: data}),
            )
            if name != "working_dir":
                # Test coercing to string
                testcase.assertEqual(
                    salt.utils.dockermod.translate_input(
                        self.translator, **{item: 123}
                    ),
                    testcase.apply_defaults({name: "123"}),
                )
        if alias is not None:
            # Test collision
            test_kwargs = {name: data, alias: data}
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=True, **test_kwargs
                ),
                testcase.apply_defaults({name: test_kwargs[name]}),
            )
            with testcase.assertRaisesRegex(
                CommandExecutionError, "is an alias for.+cannot both be used"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=False, **test_kwargs
                )
        return self.func(testcase, *args, **kwargs)


class assert_int_or_string(Assert):
    """
    Test an integer or string value
    """

    def wrap(self, testcase, *args, **kwargs):  # pylint: disable=arguments-differ
        # Strip off the "test_" from the function name
        name = self.func.__name__[5:]
        alias = self.translator.ALIASES_REVMAP.get(name)
        for item in (name, alias):
            if item is None:
                continue
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(self.translator, **{item: 100}),
                testcase.apply_defaults({name: 100}),
            )
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(self.translator, **{item: "100M"}),
                testcase.apply_defaults({name: "100M"}),
            )
        if alias is not None:
            # Test collision
            test_kwargs = {name: 100, alias: "100M"}
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=True, **test_kwargs
                ),
                testcase.apply_defaults({name: test_kwargs[name]}),
            )
            with testcase.assertRaisesRegex(
                CommandExecutionError, "is an alias for.+cannot both be used"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=False, **test_kwargs
                )
        return self.func(testcase, *args, **kwargs)


class assert_stringlist(Assert):
    """
    Test a comma-separated or Python list of strings
    """

    def wrap(self, testcase, *args, **kwargs):  # pylint: disable=arguments-differ
        # Strip off the "test_" from the function name
        name = self.func.__name__[5:]
        self.test_stringlist(testcase, name)
        return self.func(testcase, *args, **kwargs)


class assert_dict(Assert):
    """
    Dictionaries should be untouched, dictlists should be repacked and end up
    as a single dictionary.
    """

    def wrap(self, testcase, *args, **kwargs):  # pylint: disable=arguments-differ
        # Strip off the "test_" from the function name
        name = self.func.__name__[5:]
        alias = self.translator.ALIASES_REVMAP.get(name)
        expected = {"foo": "bar", "baz": "qux"}
        for item in (name, alias):
            if item is None:
                continue
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, **{item: expected}
                ),
                testcase.apply_defaults({name: expected}),
            )
            # "Dictlist" input from states
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, **{item: [{x: y} for x, y in expected.items()]}
                ),
                testcase.apply_defaults({name: expected}),
            )
            # Error case: non-dictionary input
            with testcase.assertRaisesRegex(
                CommandExecutionError, "'foo' is not a dictionary"
            ):
                salt.utils.dockermod.translate_input(self.translator, **{item: "foo"})
        if alias is not None:
            # Test collision
            test_kwargs = {name: "foo", alias: "bar"}
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=True, **test_kwargs
                ),
                testcase.apply_defaults({name: test_kwargs[name]}),
            )
            with testcase.assertRaisesRegex(
                CommandExecutionError, "is an alias for.+cannot both be used"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=False, **test_kwargs
                )
        return self.func(testcase, *args, **kwargs)


class assert_cmd(Assert):
    """
    Test for a string, or a comma-separated or Python list of strings. This is
    different from a stringlist in that we do not do any splitting. This
    decorator is used both by the "command" and "entrypoint" arguments.
    """

    def wrap(self, testcase, *args, **kwargs):  # pylint: disable=arguments-differ
        # Strip off the "test_" from the function name
        name = self.func.__name__[5:]
        alias = self.translator.ALIASES_REVMAP.get(name)
        for item in (name, alias):
            if item is None:
                continue
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, **{item: "foo bar"}
                ),
                testcase.apply_defaults({name: "foo bar"}),
            )
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, **{item: ["foo", "bar"]}
                ),
                testcase.apply_defaults({name: ["foo", "bar"]}),
            )
            # Test coercing to string
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(self.translator, **{item: 123}),
                testcase.apply_defaults({name: "123"}),
            )
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, **{item: ["one", 2]}
                ),
                testcase.apply_defaults({name: ["one", "2"]}),
            )
        if alias is not None:
            # Test collision
            test_kwargs = {name: "foo", alias: "bar"}
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=True, **test_kwargs
                ),
                testcase.apply_defaults({name: test_kwargs[name]}),
            )
            with testcase.assertRaisesRegex(
                CommandExecutionError, "is an alias for.+cannot both be used"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=False, **test_kwargs
                )
        return self.func(testcase, *args, **kwargs)


class assert_key_colon_value(Assert):
    """
    Test a key/value pair with parameters passed as key:value pairs
    """

    def wrap(self, testcase, *args, **kwargs):  # pylint: disable=arguments-differ
        # Strip off the "test_" from the function name
        name = self.func.__name__[5:]
        self.test_key_value(testcase, name, ":")
        return self.func(testcase, *args, **kwargs)


class assert_key_equals_value(Assert):
    """
    Test a key/value pair with parameters passed as key=value pairs
    """

    def wrap(self, testcase, *args, **kwargs):  # pylint: disable=arguments-differ
        # Strip off the "test_" from the function name
        name = self.func.__name__[5:]
        self.test_key_value(testcase, name, "=")
        if name == "labels":
            self.test_stringlist(testcase, name)
        return self.func(testcase, *args, **kwargs)


class assert_labels(Assert):
    def wrap(self, testcase, *args, **kwargs):  # pylint: disable=arguments-differ
        # Strip off the "test_" from the function name
        name = self.func.__name__[5:]
        alias = self.translator.ALIASES_REVMAP.get(name)
        labels = ["foo", "bar=baz", {"hello": "world"}]
        expected = {"foo": "", "bar": "baz", "hello": "world"}
        for item in (name, alias):
            if item is None:
                continue

            testcase.assertEqual(
                salt.utils.dockermod.translate_input(self.translator, **{item: labels}),
                testcase.apply_defaults({name: expected}),
            )
            # Error case: Passed a mutli-element dict in dictlist
            bad_labels = copy.deepcopy(labels)
            bad_labels[-1]["bad"] = "input"
            with testcase.assertRaisesRegex(
                CommandExecutionError, r"Invalid label\(s\)"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator, **{item: bad_labels}
                )
        return self.func(testcase, *args, **kwargs)


class assert_device_rates(Assert):
    """
    Tests for device_{read,write}_{bps,iops}. The bps values have a "Rate"
    value expressed in bytes/kb/mb/gb, while the iops values have a "Rate"
    expressed as a simple integer.
    """

    def wrap(self, testcase, *args, **kwargs):  # pylint: disable=arguments-differ
        # Strip off the "test_" from the function name
        name = self.func.__name__[5:]
        alias = self.translator.ALIASES_REVMAP.get(name)
        for item in (name, alias):
            if item is None:
                continue

            # Error case: Not an absolute path
            path = os.path.join("foo", "bar", "baz")
            with testcase.assertRaisesRegex(
                CommandExecutionError,
                "Path '{}' is not absolute".format(path.replace("\\", "\\\\")),
            ):
                salt.utils.dockermod.translate_input(
                    self.translator, **{item: f"{path}:1048576"}
                )

            if name.endswith("_bps"):
                # Both integer bytes and a string providing a shorthand for kb,
                # mb, or gb can be used, so we need to test for both.
                expected = ({}, [])
                vals = "/dev/sda:1048576,/dev/sdb:1048576"
                for val in (vals, vals.split(",")):
                    testcase.assertEqual(
                        salt.utils.dockermod.translate_input(
                            self.translator, **{item: val}
                        ),
                        testcase.apply_defaults(
                            {
                                name: [
                                    {"Path": "/dev/sda", "Rate": 1048576},
                                    {"Path": "/dev/sdb", "Rate": 1048576},
                                ]
                            }
                        ),
                    )

                vals = "/dev/sda:1mb,/dev/sdb:5mb"
                for val in (vals, vals.split(",")):
                    testcase.assertEqual(
                        salt.utils.dockermod.translate_input(
                            self.translator, **{item: val}
                        ),
                        testcase.apply_defaults(
                            {
                                name: [
                                    {"Path": "/dev/sda", "Rate": "1mb"},
                                    {"Path": "/dev/sdb", "Rate": "5mb"},
                                ]
                            }
                        ),
                    )

                if alias is not None:
                    # Test collision
                    test_kwargs = {
                        name: "/dev/sda:1048576,/dev/sdb:1048576",
                        alias: "/dev/sda:1mb,/dev/sdb:5mb",
                    }
                    testcase.assertEqual(
                        salt.utils.dockermod.translate_input(
                            self.translator, ignore_collisions=True, **test_kwargs
                        ),
                        testcase.apply_defaults(
                            {
                                name: [
                                    {"Path": "/dev/sda", "Rate": 1048576},
                                    {"Path": "/dev/sdb", "Rate": 1048576},
                                ]
                            }
                        ),
                    )
                    with testcase.assertRaisesRegex(
                        CommandExecutionError, "is an alias for.+cannot both be used"
                    ):
                        salt.utils.dockermod.translate_input(
                            self.translator, ignore_collisions=False, **test_kwargs
                        )
            else:
                # The "Rate" value must be an integer
                vals = "/dev/sda:1000,/dev/sdb:500"
                for val in (vals, vals.split(",")):
                    testcase.assertEqual(
                        salt.utils.dockermod.translate_input(
                            self.translator, **{item: val}
                        ),
                        testcase.apply_defaults(
                            {
                                name: [
                                    {"Path": "/dev/sda", "Rate": 1000},
                                    {"Path": "/dev/sdb", "Rate": 500},
                                ]
                            }
                        ),
                    )
                # Test non-integer input
                expected = (
                    {},
                    {item: "Rate '5mb' for path '/dev/sdb' is non-numeric"},
                    [],
                )
                vals = "/dev/sda:1000,/dev/sdb:5mb"
                for val in (vals, vals.split(",")):
                    with testcase.assertRaisesRegex(
                        CommandExecutionError,
                        "Rate '5mb' for path '/dev/sdb' is non-numeric",
                    ):
                        salt.utils.dockermod.translate_input(
                            self.translator, **{item: val}
                        )

                if alias is not None:
                    # Test collision
                    test_kwargs = {
                        name: "/dev/sda:1000,/dev/sdb:500",
                        alias: "/dev/sda:888,/dev/sdb:999",
                    }
                    testcase.assertEqual(
                        salt.utils.dockermod.translate_input(
                            self.translator, ignore_collisions=True, **test_kwargs
                        ),
                        testcase.apply_defaults(
                            {
                                name: [
                                    {"Path": "/dev/sda", "Rate": 1000},
                                    {"Path": "/dev/sdb", "Rate": 500},
                                ]
                            }
                        ),
                    )
                    with testcase.assertRaisesRegex(
                        CommandExecutionError, "is an alias for.+cannot both be used"
                    ):
                        salt.utils.dockermod.translate_input(
                            self.translator, ignore_collisions=False, **test_kwargs
                        )
        return self.func(testcase, *args, **kwargs)


class assert_subnet(Assert):
    """
    Test an IPv4 or IPv6 subnet
    """

    def wrap(self, testcase, *args, **kwargs):  # pylint: disable=arguments-differ
        # Strip off the "test_" from the function name
        name = self.func.__name__[5:]
        alias = self.translator.ALIASES_REVMAP.get(name)
        for item in (name, alias):
            if item is None:
                continue
            for val in ("127.0.0.1/32", "::1/128"):
                log.debug("Verifying '%s' is a valid subnet", val)
                testcase.assertEqual(
                    salt.utils.dockermod.translate_input(
                        self.translator, validate_ip_addrs=True, **{item: val}
                    ),
                    testcase.apply_defaults({name: val}),
                )
            # Error case: invalid subnet caught by validation
            for val in (
                "127.0.0.1",
                "999.999.999.999/24",
                "10.0.0.0/33",
                "::1",
                "feaz::1/128",
                "::1/129",
            ):
                log.debug("Verifying '%s' is not a valid subnet", val)
                with testcase.assertRaisesRegex(
                    CommandExecutionError, f"'{val}' is not a valid subnet"
                ):
                    salt.utils.dockermod.translate_input(
                        self.translator, validate_ip_addrs=True, **{item: val}
                    )

            # This is not valid input but it will test whether or not subnet
            # validation happened
            val = "foo"
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, validate_ip_addrs=False, **{item: val}
                ),
                testcase.apply_defaults({name: val}),
            )

        if alias is not None:
            # Test collision
            test_kwargs = {name: "10.0.0.0/24", alias: "192.168.50.128/25"}
            testcase.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=True, **test_kwargs
                ),
                testcase.apply_defaults({name: test_kwargs[name]}),
            )
            with testcase.assertRaisesRegex(
                CommandExecutionError, "is an alias for.+cannot both be used"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator, ignore_collisions=False, **test_kwargs
                )
        return self.func(testcase, *args, **kwargs)


class TranslateBase(TestCase):
    maxDiff = None
    translator = None  # Must be overridden in the subclass

    def apply_defaults(self, ret, skip_translate=None):
        if skip_translate is not True:
            defaults = getattr(self.translator, "DEFAULTS", {})
            for key, val in defaults.items():
                if key not in ret:
                    ret[key] = val
        return ret

    @staticmethod
    def normalize_ports(ret):
        """
        When we translate exposed ports, we can end up with a mixture of ints
        (representing TCP ports) and tuples (representing UDP ports). Python 2
        will sort an iterable containing these mixed types, but Python 3 will
        not. This helper is used to munge the ports in the return data so that
        the resulting list is sorted in a way that can reliably be compared to
        the expected results in the test.

        This helper should only be needed for port_bindings and ports.
        """
        if "ports" in ret[0]:
            tcp_ports = []
            udp_ports = []
            for item in ret[0]["ports"]:
                if isinstance(item, int):
                    tcp_ports.append(item)
                else:
                    udp_ports.append(item)
            ret[0]["ports"] = sorted(tcp_ports) + sorted(udp_ports)
        return ret

    def tearDown(self):
        """
        Test skip_translate kwarg
        """
        name = self.id().split(".")[-1][5:]
        # The below is not valid input for the Docker API, but these
        # assertions confirm that we successfully skipped translation.
        for val in (True, name, [name]):
            self.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, skip_translate=val, **{name: "foo"}
                ),
                self.apply_defaults({name: "foo"}, skip_translate=val),
            )


class TranslateContainerInputTestCase(TranslateBase):
    """
    Tests for salt.utils.dockermod.translate_input(), invoked using
    salt.utils.dockermod.translate.container as the translator module.
    """

    translator = salt.utils.dockermod.translate.container

    @staticmethod
    def normalize_ports(ret):
        """
        When we translate exposed ports, we can end up with a mixture of ints
        (representing TCP ports) and tuples (representing UDP ports). Python 2
        will sort an iterable containing these mixed types, but Python 3 will
        not. This helper is used to munge the ports in the return data so that
        the resulting list is sorted in a way that can reliably be compared to
        the expected results in the test.

        This helper should only be needed for port_bindings and ports.
        """
        if "ports" in ret:
            tcp_ports = []
            udp_ports = []
            for item in ret["ports"]:
                if isinstance(item, int):
                    tcp_ports.append(item)
                else:
                    udp_ports.append(item)
            ret["ports"] = sorted(tcp_ports) + sorted(udp_ports)
        return ret

    @assert_bool(salt.utils.dockermod.translate.container)
    def test_auto_remove(self):
        """
        Should be a bool or converted to one
        """

    def test_binds(self):
        """
        Test the "binds" kwarg. Any volumes not defined in the "volumes" kwarg
        should be added to the results.
        """
        self.assertEqual(
            salt.utils.dockermod.translate_input(
                self.translator, binds="/srv/www:/var/www:ro", volumes="/testing"
            ),
            {"binds": ["/srv/www:/var/www:ro"], "volumes": ["/testing", "/var/www"]},
        )
        self.assertEqual(
            salt.utils.dockermod.translate_input(
                self.translator, binds=["/srv/www:/var/www:ro"], volumes="/testing"
            ),
            {"binds": ["/srv/www:/var/www:ro"], "volumes": ["/testing", "/var/www"]},
        )
        self.assertEqual(
            salt.utils.dockermod.translate_input(
                self.translator,
                binds={"/srv/www": {"bind": "/var/www", "mode": "ro"}},
                volumes="/testing",
            ),
            {
                "binds": {"/srv/www": {"bind": "/var/www", "mode": "ro"}},
                "volumes": ["/testing", "/var/www"],
            },
        )

    @assert_int(salt.utils.dockermod.translate.container)
    def test_blkio_weight(self):
        """
        Should be an int or converted to one
        """

    def test_blkio_weight_device(self):
        """
        Should translate a list of PATH:WEIGHT pairs to a list of dictionaries
        with the following format: {'Path': PATH, 'Weight': WEIGHT}
        """
        for val in ("/dev/sda:100,/dev/sdb:200", ["/dev/sda:100", "/dev/sdb:200"]):
            self.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, blkio_weight_device="/dev/sda:100,/dev/sdb:200"
                ),
                {
                    "blkio_weight_device": [
                        {"Path": "/dev/sda", "Weight": 100},
                        {"Path": "/dev/sdb", "Weight": 200},
                    ]
                },
            )

        # Error cases
        with self.assertRaisesRegex(
            CommandExecutionError, r"'foo' contains 1 value\(s\) \(expected 2\)"
        ):
            salt.utils.dockermod.translate_input(
                self.translator, blkio_weight_device="foo"
            )
        with self.assertRaisesRegex(
            CommandExecutionError, r"'foo:bar:baz' contains 3 value\(s\) \(expected 2\)"
        ):
            salt.utils.dockermod.translate_input(
                self.translator, blkio_weight_device="foo:bar:baz"
            )
        with self.assertRaisesRegex(
            CommandExecutionError, r"Weight 'foo' for path '/dev/sdb' is not an integer"
        ):
            salt.utils.dockermod.translate_input(
                self.translator, blkio_weight_device=["/dev/sda:100", "/dev/sdb:foo"]
            )

    @assert_stringlist(salt.utils.dockermod.translate.container)
    def test_cap_add(self):
        """
        Should be a list of strings or converted to one
        """

    @assert_stringlist(salt.utils.dockermod.translate.container)
    def test_cap_drop(self):
        """
        Should be a list of strings or converted to one
        """

    @assert_cmd(salt.utils.dockermod.translate.container)
    def test_command(self):
        """
        Can either be a string or a comma-separated or Python list of strings.
        """

    @assert_string(salt.utils.dockermod.translate.container)
    def test_cpuset_cpus(self):
        """
        Should be a string or converted to one
        """

    @assert_string(salt.utils.dockermod.translate.container)
    def test_cpuset_mems(self):
        """
        Should be a string or converted to one
        """

    @assert_int(salt.utils.dockermod.translate.container)
    def test_cpu_group(self):
        """
        Should be an int or converted to one
        """

    @assert_int(salt.utils.dockermod.translate.container)
    def test_cpu_period(self):
        """
        Should be an int or converted to one
        """

    @assert_int(salt.utils.dockermod.translate.container)
    def test_cpu_shares(self):
        """
        Should be an int or converted to one
        """

    @assert_bool(salt.utils.dockermod.translate.container)
    def test_detach(self):
        """
        Should be a bool or converted to one
        """

    @assert_device_rates(salt.utils.dockermod.translate.container)
    def test_device_read_bps(self):
        """
        CLI input is a list of PATH:RATE pairs, but the API expects a list of
        dictionaries in the format [{'Path': path, 'Rate': rate}]
        """

    @assert_device_rates(salt.utils.dockermod.translate.container)
    def test_device_read_iops(self):
        """
        CLI input is a list of PATH:RATE pairs, but the API expects a list of
        dictionaries in the format [{'Path': path, 'Rate': rate}]
        """

    @assert_device_rates(salt.utils.dockermod.translate.container)
    def test_device_write_bps(self):
        """
        CLI input is a list of PATH:RATE pairs, but the API expects a list of
        dictionaries in the format [{'Path': path, 'Rate': rate}]
        """

    @assert_device_rates(salt.utils.dockermod.translate.container)
    def test_device_write_iops(self):
        """
        CLI input is a list of PATH:RATE pairs, but the API expects a list of
        dictionaries in the format [{'Path': path, 'Rate': rate}]
        """

    @assert_stringlist(salt.utils.dockermod.translate.container)
    def test_devices(self):
        """
        Should be a list of strings or converted to one
        """

    @assert_stringlist(salt.utils.dockermod.translate.container)
    def test_dns_opt(self):
        """
        Should be a list of strings or converted to one
        """

    @assert_stringlist(salt.utils.dockermod.translate.container)
    def test_dns_search(self):
        """
        Should be a list of strings or converted to one
        """

    def test_dns(self):
        """
        While this is a stringlist, it also supports IP address validation, so
        it can't use the test_stringlist decorator because we need to test both
        with and without validation, and it isn't necessary to make all other
        stringlist tests also do that same kind of testing.
        """
        for val in ("8.8.8.8,8.8.4.4", ["8.8.8.8", "8.8.4.4"]):
            self.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator,
                    dns=val,
                    validate_ip_addrs=True,
                ),
                {"dns": ["8.8.8.8", "8.8.4.4"]},
            )

        # Error case: invalid IP address caught by validation
        for val in ("8.8.8.888,8.8.4.4", ["8.8.8.888", "8.8.4.4"]):
            with self.assertRaisesRegex(
                CommandExecutionError, r"'8.8.8.888' is not a valid IP address"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator,
                    dns=val,
                    validate_ip_addrs=True,
                )

        # This is not valid input but it will test whether or not IP address
        # validation happened.
        for val in ("foo,bar", ["foo", "bar"]):
            self.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator,
                    dns=val,
                    validate_ip_addrs=False,
                ),
                {"dns": ["foo", "bar"]},
            )

    @assert_string(salt.utils.dockermod.translate.container)
    def test_domainname(self):
        """
        Should be a list of strings or converted to one
        """

    @assert_cmd(salt.utils.dockermod.translate.container)
    def test_entrypoint(self):
        """
        Can either be a string or a comma-separated or Python list of strings.
        """

    @assert_key_equals_value(salt.utils.dockermod.translate.container)
    def test_environment(self):
        """
        Can be passed in several formats but must end up as a dictionary
        mapping keys to values
        """

    def test_extra_hosts(self):
        """
        Can be passed as a list of key:value pairs but can't be simply tested
        using @assert_key_colon_value since we need to test both with and without
        IP address validation.
        """
        for val in ("web1:10.9.8.7,web2:10.9.8.8", ["web1:10.9.8.7", "web2:10.9.8.8"]):
            self.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator,
                    extra_hosts=val,
                    validate_ip_addrs=True,
                ),
                {"extra_hosts": {"web1": "10.9.8.7", "web2": "10.9.8.8"}},
            )

        # Error case: invalid IP address caught by validation
        for val in (
            "web1:10.9.8.299,web2:10.9.8.8",
            ["web1:10.9.8.299", "web2:10.9.8.8"],
        ):
            with self.assertRaisesRegex(
                CommandExecutionError, r"'10.9.8.299' is not a valid IP address"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator,
                    extra_hosts=val,
                    validate_ip_addrs=True,
                )

        # This is not valid input but it will test whether or not IP address
        # validation happened.
        for val in ("foo:bar,baz:qux", ["foo:bar", "baz:qux"]):
            self.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator,
                    extra_hosts=val,
                    validate_ip_addrs=False,
                ),
                {"extra_hosts": {"foo": "bar", "baz": "qux"}},
            )

    @assert_stringlist(salt.utils.dockermod.translate.container)
    def test_group_add(self):
        """
        Should be a list of strings or converted to one
        """

    @assert_string(salt.utils.dockermod.translate.container)
    def test_hostname(self):
        """
        Should be a string or converted to one
        """

    @assert_string(salt.utils.dockermod.translate.container)
    def test_ipc_mode(self):
        """
        Should be a string or converted to one
        """

    @assert_string(salt.utils.dockermod.translate.container)
    def test_isolation(self):
        """
        Should be a string or converted to one
        """

    @assert_labels(salt.utils.dockermod.translate.container)
    def test_labels(self):
        """
        Can be passed as a list of key=value pairs or a dictionary, and must
        ultimately end up as a dictionary.
        """

    @assert_key_colon_value(salt.utils.dockermod.translate.container)
    def test_links(self):
        """
        Can be passed as a list of key:value pairs or a dictionary, and must
        ultimately end up as a dictionary.
        """

    def test_log_config(self):
        """
        This is a mixture of log_driver and log_opt, which get combined into a
        dictionary.

        log_driver is a simple string, but log_opt can be passed in several
        ways, so we need to test them all.
        """
        expected = (
            {"log_config": {"Type": "foo", "Config": {"foo": "bar", "baz": "qux"}}},
            {},
            [],
        )
        for val in (
            "foo=bar,baz=qux",
            ["foo=bar", "baz=qux"],
            [{"foo": "bar"}, {"baz": "qux"}],
            {"foo": "bar", "baz": "qux"},
        ):
            self.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, log_driver="foo", log_opt="foo=bar,baz=qux"
                ),
                {"log_config": {"Type": "foo", "Config": {"foo": "bar", "baz": "qux"}}},
            )

        # Ensure passing either `log_driver` or `log_opt` alone works
        self.assertEqual(
            salt.utils.dockermod.translate_input(self.translator, log_driver="foo"),
            {"log_config": {"Type": "foo", "Config": {}}},
        )
        self.assertEqual(
            salt.utils.dockermod.translate_input(
                self.translator, log_opt={"foo": "bar", "baz": "qux"}
            ),
            {"log_config": {"Type": "none", "Config": {"foo": "bar", "baz": "qux"}}},
        )

    @assert_key_equals_value(salt.utils.dockermod.translate.container)
    def test_lxc_conf(self):
        """
        Can be passed as a list of key=value pairs or a dictionary, and must
        ultimately end up as a dictionary.
        """

    @assert_string(salt.utils.dockermod.translate.container)
    def test_mac_address(self):
        """
        Should be a string or converted to one
        """

    @assert_int_or_string(salt.utils.dockermod.translate.container)
    def test_mem_limit(self):
        """
        Should be a string or converted to one
        """

    @assert_int(salt.utils.dockermod.translate.container)
    def test_mem_swappiness(self):
        """
        Should be an int or converted to one
        """

    @assert_int_or_string(salt.utils.dockermod.translate.container)
    def test_memswap_limit(self):
        """
        Should be a string or converted to one
        """

    @assert_string(salt.utils.dockermod.translate.container)
    def test_name(self):
        """
        Should be a string or converted to one
        """

    @assert_bool(salt.utils.dockermod.translate.container)
    def test_network_disabled(self):
        """
        Should be a bool or converted to one
        """

    @assert_string(salt.utils.dockermod.translate.container)
    def test_network_mode(self):
        """
        Should be a string or converted to one
        """

    @assert_bool(salt.utils.dockermod.translate.container)
    def test_oom_kill_disable(self):
        """
        Should be a bool or converted to one
        """

    @assert_int(salt.utils.dockermod.translate.container)
    def test_oom_score_adj(self):
        """
        Should be an int or converted to one
        """

    @assert_string(salt.utils.dockermod.translate.container)
    def test_pid_mode(self):
        """
        Should be a string or converted to one
        """

    @assert_int(salt.utils.dockermod.translate.container)
    def test_pids_limit(self):
        """
        Should be an int or converted to one
        """

    def test_port_bindings(self):
        """
        This has several potential formats and can include port ranges. It
        needs its own test.
        """
        # ip:hostPort:containerPort - Bind a specific IP and port on the host
        # to a specific port within the container.
        bindings = (
            "10.1.2.3:8080:80,10.1.2.3:8888:80,10.4.5.6:3333:3333,"
            "10.7.8.9:14505-14506:4505-4506,10.1.2.3:8080:81/udp,"
            "10.1.2.3:8888:81/udp,10.4.5.6:3334:3334/udp,"
            "10.7.8.9:15505-15506:5505-5506/udp"
        )
        for val in (bindings, bindings.split(",")):
            self.assertEqual(
                self.normalize_ports(
                    salt.utils.dockermod.translate_input(
                        self.translator,
                        port_bindings=val,
                    )
                ),
                {
                    "port_bindings": {
                        80: [("10.1.2.3", 8080), ("10.1.2.3", 8888)],
                        3333: ("10.4.5.6", 3333),
                        4505: ("10.7.8.9", 14505),
                        4506: ("10.7.8.9", 14506),
                        "81/udp": [("10.1.2.3", 8080), ("10.1.2.3", 8888)],
                        "3334/udp": ("10.4.5.6", 3334),
                        "5505/udp": ("10.7.8.9", 15505),
                        "5506/udp": ("10.7.8.9", 15506),
                    },
                    "ports": [
                        80,
                        3333,
                        4505,
                        4506,
                        (81, "udp"),
                        (3334, "udp"),
                        (5505, "udp"),
                        (5506, "udp"),
                    ],
                },
            )

        # ip::containerPort - Bind a specific IP and an ephemeral port to a
        # specific port within the container.
        bindings = (
            "10.1.2.3::80,10.1.2.3::80,10.4.5.6::3333,10.7.8.9::4505-4506,"
            "10.1.2.3::81/udp,10.1.2.3::81/udp,10.4.5.6::3334/udp,"
            "10.7.8.9::5505-5506/udp"
        )
        for val in (bindings, bindings.split(",")):
            self.assertEqual(
                self.normalize_ports(
                    salt.utils.dockermod.translate_input(
                        self.translator,
                        port_bindings=val,
                    )
                ),
                {
                    "port_bindings": {
                        80: [("10.1.2.3",), ("10.1.2.3",)],
                        3333: ("10.4.5.6",),
                        4505: ("10.7.8.9",),
                        4506: ("10.7.8.9",),
                        "81/udp": [("10.1.2.3",), ("10.1.2.3",)],
                        "3334/udp": ("10.4.5.6",),
                        "5505/udp": ("10.7.8.9",),
                        "5506/udp": ("10.7.8.9",),
                    },
                    "ports": [
                        80,
                        3333,
                        4505,
                        4506,
                        (81, "udp"),
                        (3334, "udp"),
                        (5505, "udp"),
                        (5506, "udp"),
                    ],
                },
            )

        # hostPort:containerPort - Bind a specific port on all of the host's
        # interfaces to a specific port within the container.
        bindings = (
            "8080:80,8888:80,3333:3333,14505-14506:4505-4506,8080:81/udp,"
            "8888:81/udp,3334:3334/udp,15505-15506:5505-5506/udp"
        )
        for val in (bindings, bindings.split(",")):
            self.assertEqual(
                self.normalize_ports(
                    salt.utils.dockermod.translate_input(
                        self.translator,
                        port_bindings=val,
                    )
                ),
                {
                    "port_bindings": {
                        80: [8080, 8888],
                        3333: 3333,
                        4505: 14505,
                        4506: 14506,
                        "81/udp": [8080, 8888],
                        "3334/udp": 3334,
                        "5505/udp": 15505,
                        "5506/udp": 15506,
                    },
                    "ports": [
                        80,
                        3333,
                        4505,
                        4506,
                        (81, "udp"),
                        (3334, "udp"),
                        (5505, "udp"),
                        (5506, "udp"),
                    ],
                },
            )

        # containerPort - Bind an ephemeral port on all of the host's
        # interfaces to a specific port within the container.
        bindings = "80,3333,4505-4506,81/udp,3334/udp,5505-5506/udp"
        for val in (bindings, bindings.split(",")):
            self.assertEqual(
                self.normalize_ports(
                    salt.utils.dockermod.translate_input(
                        self.translator,
                        port_bindings=val,
                    )
                ),
                {
                    "port_bindings": {
                        80: None,
                        3333: None,
                        4505: None,
                        4506: None,
                        "81/udp": None,
                        "3334/udp": None,
                        "5505/udp": None,
                        "5506/udp": None,
                    },
                    "ports": [
                        80,
                        3333,
                        4505,
                        4506,
                        (81, "udp"),
                        (3334, "udp"),
                        (5505, "udp"),
                        (5506, "udp"),
                    ],
                },
            )

        # Test a mixture of different types of input
        bindings = (
            "10.1.2.3:8080:80,10.4.5.6::3333,14505-14506:4505-4506,"
            "9999-10001,10.1.2.3:8080:81/udp,10.4.5.6::3334/udp,"
            "15505-15506:5505-5506/udp,19999-20001/udp"
        )
        for val in (bindings, bindings.split(",")):
            self.assertEqual(
                self.normalize_ports(
                    salt.utils.dockermod.translate_input(
                        self.translator,
                        port_bindings=val,
                    )
                ),
                {
                    "port_bindings": {
                        80: ("10.1.2.3", 8080),
                        3333: ("10.4.5.6",),
                        4505: 14505,
                        4506: 14506,
                        9999: None,
                        10000: None,
                        10001: None,
                        "81/udp": ("10.1.2.3", 8080),
                        "3334/udp": ("10.4.5.6",),
                        "5505/udp": 15505,
                        "5506/udp": 15506,
                        "19999/udp": None,
                        "20000/udp": None,
                        "20001/udp": None,
                    },
                    "ports": [
                        80,
                        3333,
                        4505,
                        4506,
                        9999,
                        10000,
                        10001,
                        (81, "udp"),
                        (3334, "udp"),
                        (5505, "udp"),
                        (5506, "udp"),
                        (19999, "udp"),
                        (20000, "udp"),
                        (20001, "udp"),
                    ],
                },
            )

        # Error case: too many items (max 3)
        with self.assertRaisesRegex(
            CommandExecutionError,
            r"'10.1.2.3:8080:80:123' is an invalid port binding "
            r"definition \(at most 3 components are allowed, found 4\)",
        ):
            salt.utils.dockermod.translate_input(
                self.translator, port_bindings="10.1.2.3:8080:80:123"
            )

        # Error case: port range start is greater than end
        for val in (
            "10.1.2.3:5555-5554:1111-1112",
            "10.1.2.3:1111-1112:5555-5554",
            "10.1.2.3::5555-5554",
            "5555-5554:1111-1112",
            "1111-1112:5555-5554",
            "5555-5554",
        ):
            with self.assertRaisesRegex(
                CommandExecutionError,
                r"Start of port range \(5555\) cannot be greater than end "
                r"of port range \(5554\)",
            ):
                salt.utils.dockermod.translate_input(
                    self.translator,
                    port_bindings=val,
                )

        # Error case: non-numeric port range
        for val in (
            "10.1.2.3:foo:1111-1112",
            "10.1.2.3:1111-1112:foo",
            "10.1.2.3::foo",
            "foo:1111-1112",
            "1111-1112:foo",
            "foo",
        ):
            with self.assertRaisesRegex(
                CommandExecutionError, "'foo' is non-numeric or an invalid port range"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator,
                    port_bindings=val,
                )

        # Error case: misatched port range
        for val in ("10.1.2.3:1111-1113:1111-1112", "1111-1113:1111-1112"):
            with self.assertRaisesRegex(
                CommandExecutionError,
                r"Host port range \(1111-1113\) does not have the same "
                r"number of ports as the container port range \(1111-1112\)",
            ):
                salt.utils.dockermod.translate_input(self.translator, port_bindings=val)

        for val in ("10.1.2.3:1111-1112:1111-1113", "1111-1112:1111-1113"):
            with self.assertRaisesRegex(
                CommandExecutionError,
                r"Host port range \(1111-1112\) does not have the same "
                r"number of ports as the container port range \(1111-1113\)",
            ):
                salt.utils.dockermod.translate_input(
                    self.translator,
                    port_bindings=val,
                )

        # Error case: empty host port or container port
        with self.assertRaisesRegex(
            CommandExecutionError, "Empty host port in port binding definition ':1111'"
        ):
            salt.utils.dockermod.translate_input(self.translator, port_bindings=":1111")
        with self.assertRaisesRegex(
            CommandExecutionError,
            "Empty container port in port binding definition '1111:'",
        ):
            salt.utils.dockermod.translate_input(self.translator, port_bindings="1111:")
        with self.assertRaisesRegex(
            CommandExecutionError, "Empty port binding definition found"
        ):
            salt.utils.dockermod.translate_input(self.translator, port_bindings="")

    def test_ports(self):
        """
        Ports can be passed as a comma-separated or Python list of port
        numbers, with '/tcp' being optional for TCP ports. They must ultimately
        be a list of port definitions, in which an integer denotes a TCP port,
        and a tuple in the format (port_num, 'udp') denotes a UDP port. Also,
        the port numbers must end up as integers. None of the decorators will
        suffice so this one must be tested specially.
        """
        for val in (
            "1111,2222/tcp,3333/udp,4505-4506",
            [1111, "2222/tcp", "3333/udp", "4505-4506"],
            ["1111", "2222/tcp", "3333/udp", "4505-4506"],
        ):
            self.assertEqual(
                self.normalize_ports(
                    salt.utils.dockermod.translate_input(
                        self.translator,
                        ports=val,
                    )
                ),
                {"ports": [1111, 2222, 4505, 4506, (3333, "udp")]},
            )

        # Error case: non-integer and non/string value
        for val in (1.0, [1.0]):
            with self.assertRaisesRegex(
                CommandExecutionError, "'1.0' is not a valid port definition"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator,
                    ports=val,
                )

        # Error case: port range start is greater than end
        with self.assertRaisesRegex(
            CommandExecutionError,
            r"Start of port range \(5555\) cannot be greater than end of "
            r"port range \(5554\)",
        ):
            salt.utils.dockermod.translate_input(
                self.translator,
                ports="5555-5554",
            )

    @assert_bool(salt.utils.dockermod.translate.container)
    def test_privileged(self):
        """
        Should be a bool or converted to one
        """

    @assert_bool(salt.utils.dockermod.translate.container)
    def test_publish_all_ports(self):
        """
        Should be a bool or converted to one
        """

    @assert_bool(salt.utils.dockermod.translate.container)
    def test_read_only(self):
        """
        Should be a bool or converted to one
        """

    def test_restart_policy(self):
        """
        Input is in the format "name[:retry_count]", but the API wants it
        in the format {'Name': name, 'MaximumRetryCount': retry_count}
        """
        name = "restart_policy"
        alias = "restart"
        for item in (name, alias):
            # Test with retry count
            self.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, **{item: "on-failure:5"}
                ),
                {name: {"Name": "on-failure", "MaximumRetryCount": 5}},
            )
            # Test without retry count
            self.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator, **{item: "on-failure"}
                ),
                {name: {"Name": "on-failure", "MaximumRetryCount": 0}},
            )
            # Error case: more than one policy passed
            with self.assertRaisesRegex(
                CommandExecutionError, "Only one policy is permitted"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator, **{item: "on-failure,always"}
                )

        # Test collision
        test_kwargs = {name: "on-failure:5", alias: "always"}
        self.assertEqual(
            salt.utils.dockermod.translate_input(
                self.translator, ignore_collisions=True, **test_kwargs
            ),
            {name: {"Name": "on-failure", "MaximumRetryCount": 5}},
        )
        with self.assertRaisesRegex(
            CommandExecutionError, "'restart' is an alias for 'restart_policy'"
        ):
            salt.utils.dockermod.translate_input(
                self.translator, ignore_collisions=False, **test_kwargs
            )

    @assert_stringlist(salt.utils.dockermod.translate.container)
    def test_security_opt(self):
        """
        Should be a list of strings or converted to one
        """

    @assert_int_or_string(salt.utils.dockermod.translate.container)
    def test_shm_size(self):
        """
        Should be a string or converted to one
        """

    @assert_bool(salt.utils.dockermod.translate.container)
    def test_stdin_open(self):
        """
        Should be a bool or converted to one
        """

    @assert_string(salt.utils.dockermod.translate.container)
    def test_stop_signal(self):
        """
        Should be a string or converted to one
        """

    @assert_int(salt.utils.dockermod.translate.container)
    def test_stop_timeout(self):
        """
        Should be an int or converted to one
        """

    @assert_key_equals_value(salt.utils.dockermod.translate.container)
    def test_storage_opt(self):
        """
        Can be passed in several formats but must end up as a dictionary
        mapping keys to values
        """

    @assert_key_equals_value(salt.utils.dockermod.translate.container)
    def test_sysctls(self):
        """
        Can be passed in several formats but must end up as a dictionary
        mapping keys to values
        """

    @assert_dict(salt.utils.dockermod.translate.container)
    def test_tmpfs(self):
        """
        Can be passed in several formats but must end up as a dictionary
        mapping keys to values
        """

    @assert_bool(salt.utils.dockermod.translate.container)
    def test_tty(self):
        """
        Should be a bool or converted to one
        """

    def test_ulimits(self):
        """
        Input is in the format "name=soft_limit[:hard_limit]", but the API
        wants it in the format
        {'Name': name, 'Soft': soft_limit, 'Hard': hard_limit}
        """
        # Test with and without hard limit
        ulimits = "nofile=1024:2048,nproc=50"
        for val in (ulimits, ulimits.split(",")):
            self.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator,
                    ulimits=val,
                ),
                {
                    "ulimits": [
                        {"Name": "nofile", "Soft": 1024, "Hard": 2048},
                        {"Name": "nproc", "Soft": 50, "Hard": 50},
                    ]
                },
            )

        # Error case: Invalid format
        with self.assertRaisesRegex(
            CommandExecutionError,
            r"Ulimit definition 'nofile:1024:2048' is not in the format "
            r"type=soft_limit\[:hard_limit\]",
        ):
            salt.utils.dockermod.translate_input(
                self.translator, ulimits="nofile:1024:2048"
            )

        # Error case: Invalid format
        with self.assertRaisesRegex(
            CommandExecutionError,
            r"Limit 'nofile=foo:2048' contains non-numeric value\(s\)",
        ):
            salt.utils.dockermod.translate_input(
                self.translator, ulimits="nofile=foo:2048"
            )

    def test_user(self):
        """
        Must be either username (string) or uid (int). An int passed as a
        string (e.g. '0') should be converted to an int.
        """
        # Username passed as string
        self.assertEqual(
            salt.utils.dockermod.translate_input(self.translator, user="foo"),
            {"user": "foo"},
        )
        for val in (0, "0"):
            self.assertEqual(
                salt.utils.dockermod.translate_input(self.translator, user=val),
                {"user": 0},
            )

        # Error case: non string/int passed
        with self.assertRaisesRegex(
            CommandExecutionError, "Value must be a username or uid"
        ):
            salt.utils.dockermod.translate_input(self.translator, user=["foo"])

        # Error case: negative int passed
        with self.assertRaisesRegex(CommandExecutionError, "'-1' is an invalid uid"):
            salt.utils.dockermod.translate_input(self.translator, user=-1)

    @assert_string(salt.utils.dockermod.translate.container)
    def test_userns_mode(self):
        """
        Should be a bool or converted to one
        """

    @assert_string(salt.utils.dockermod.translate.container)
    def test_volume_driver(self):
        """
        Should be a bool or converted to one
        """

    @assert_stringlist(salt.utils.dockermod.translate.container)
    def test_volumes(self):
        """
        Should be a list of absolute paths
        """
        # Error case: Not an absolute path
        path = os.path.join("foo", "bar", "baz")
        with self.assertRaisesRegex(
            CommandExecutionError,
            "'{}' is not an absolute path".format(path.replace("\\", "\\\\")),
        ):
            salt.utils.dockermod.translate_input(self.translator, volumes=path)

    @assert_stringlist(salt.utils.dockermod.translate.container)
    def test_volumes_from(self):
        """
        Should be a list of strings or converted to one
        """

    @assert_string(salt.utils.dockermod.translate.container)
    def test_working_dir(self):
        """
        Should be a single absolute path
        """
        # Error case: Not an absolute path
        path = os.path.join("foo", "bar", "baz")
        with self.assertRaisesRegex(
            CommandExecutionError,
            "'{}' is not an absolute path".format(path.replace("\\", "\\\\")),
        ):
            salt.utils.dockermod.translate_input(self.translator, working_dir=path)


class TranslateNetworkInputTestCase(TranslateBase):
    """
    Tests for salt.utils.dockermod.translate_input(), invoked using
    salt.utils.dockermod.translate.network as the translator module.
    """

    translator = salt.utils.dockermod.translate.network

    ip_addrs = {
        True: ("10.1.2.3", "::1"),
        False: ("FOO", "0.9.800.1000", "feaz::1", "aj01::feac"),
    }

    @assert_string(salt.utils.dockermod.translate.network)
    def test_driver(self):
        """
        Should be a string or converted to one
        """

    @assert_key_equals_value(salt.utils.dockermod.translate.network)
    def test_options(self):
        """
        Can be passed in several formats but must end up as a dictionary
        mapping keys to values
        """

    @assert_dict(salt.utils.dockermod.translate.network)
    def test_ipam(self):
        """
        Must be a dict
        """

    @assert_bool(salt.utils.dockermod.translate.network)
    def test_check_duplicate(self):
        """
        Should be a bool or converted to one
        """

    @assert_bool(salt.utils.dockermod.translate.network)
    def test_internal(self):
        """
        Should be a bool or converted to one
        """

    @assert_labels(salt.utils.dockermod.translate.network)
    def test_labels(self):
        """
        Can be passed as a list of key=value pairs or a dictionary, and must
        ultimately end up as a dictionary.
        """

    @assert_bool(salt.utils.dockermod.translate.network)
    def test_enable_ipv6(self):
        """
        Should be a bool or converted to one
        """

    @assert_bool(salt.utils.dockermod.translate.network)
    def test_attachable(self):
        """
        Should be a bool or converted to one
        """

    @assert_bool(salt.utils.dockermod.translate.network)
    def test_ingress(self):
        """
        Should be a bool or converted to one
        """

    @assert_string(salt.utils.dockermod.translate.network)
    def test_ipam_driver(self):
        """
        Should be a bool or converted to one
        """

    @assert_key_equals_value(salt.utils.dockermod.translate.network)
    def test_ipam_opts(self):
        """
        Can be passed in several formats but must end up as a dictionary
        mapping keys to values
        """

    def ipam_pools(self):
        """
        Must be a list of dictionaries (not a dictlist)
        """
        good_pool = {
            "subnet": "10.0.0.0/24",
            "iprange": "10.0.0.128/25",
            "gateway": "10.0.0.254",
            "aux_addresses": {
                "foo.bar.tld": "10.0.0.20",
                "hello.world.tld": "10.0.0.21",
            },
        }
        bad_pools = [
            {
                "subnet": "10.0.0.0/33",
                "iprange": "10.0.0.128/25",
                "gateway": "10.0.0.254",
                "aux_addresses": {
                    "foo.bar.tld": "10.0.0.20",
                    "hello.world.tld": "10.0.0.21",
                },
            },
            {
                "subnet": "10.0.0.0/24",
                "iprange": "foo/25",
                "gateway": "10.0.0.254",
                "aux_addresses": {
                    "foo.bar.tld": "10.0.0.20",
                    "hello.world.tld": "10.0.0.21",
                },
            },
            {
                "subnet": "10.0.0.0/24",
                "iprange": "10.0.0.128/25",
                "gateway": "10.0.0.256",
                "aux_addresses": {
                    "foo.bar.tld": "10.0.0.20",
                    "hello.world.tld": "10.0.0.21",
                },
            },
            {
                "subnet": "10.0.0.0/24",
                "iprange": "10.0.0.128/25",
                "gateway": "10.0.0.254",
                "aux_addresses": {
                    "foo.bar.tld": "10.0.0.20",
                    "hello.world.tld": "999.0.0.21",
                },
            },
        ]
        self.assertEqual(
            salt.utils.dockermod.translate_input(
                self.translator,
                ipam_pools=[good_pool],
            ),
            {"ipam_pools": [good_pool]},
        )
        for bad_pool in bad_pools:
            with self.assertRaisesRegex(CommandExecutionError, "not a valid"):
                salt.utils.dockermod.translate_input(
                    self.translator, ipam_pools=[good_pool, bad_pool]
                )

    @assert_subnet(salt.utils.dockermod.translate.network)
    def test_subnet(self):
        """
        Must be an IPv4 or IPv6 subnet
        """

    @assert_subnet(salt.utils.dockermod.translate.network)
    def test_iprange(self):
        """
        Must be an IPv4 or IPv6 subnet
        """

    def test_gateway(self):
        """
        Must be an IPv4 or IPv6 address
        """
        for val in self.ip_addrs[True]:
            self.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator,
                    validate_ip_addrs=True,
                    gateway=val,
                ),
                self.apply_defaults({"gateway": val}),
            )

        for val in self.ip_addrs[False]:
            with self.assertRaisesRegex(
                CommandExecutionError, f"'{val}' is not a valid IP address"
            ):
                salt.utils.dockermod.translate_input(
                    self.translator,
                    validate_ip_addrs=True,
                    gateway=val,
                )
            self.assertEqual(
                salt.utils.dockermod.translate_input(
                    self.translator,
                    validate_ip_addrs=False,
                    gateway=val,
                ),
                self.apply_defaults(
                    {"gateway": val if isinstance(val, str) else str(val)}
                ),
            )

    @assert_key_equals_value(salt.utils.dockermod.translate.network)
    def test_aux_addresses(self):
        """
        Must be a mapping of hostnames to IP addresses
        """
        name = "aux_addresses"
        alias = "aux_address"
        for item in (name, alias):
            for val in self.ip_addrs[True]:
                addresses = {"foo.bar.tld": val}
                self.assertEqual(
                    salt.utils.dockermod.translate_input(
                        self.translator, validate_ip_addrs=True, **{item: addresses}
                    ),
                    self.apply_defaults({name: addresses}),
                )

            for val in self.ip_addrs[False]:
                addresses = {"foo.bar.tld": val}
                with self.assertRaisesRegex(
                    CommandExecutionError, f"'{val}' is not a valid IP address"
                ):
                    salt.utils.dockermod.translate_input(
                        self.translator, validate_ip_addrs=True, **{item: addresses}
                    )
                self.assertEqual(
                    salt.utils.dockermod.translate_input(
                        self.translator,
                        validate_ip_addrs=False,
                        aux_addresses=addresses,
                    ),
                    self.apply_defaults({name: addresses}),
                )


class DockerTranslateHelperTestCase(TestCase):
    """
    Tests for a couple helper functions in salt.utils.dockermod.translate
    """

    def test_get_port_def(self):
        """
        Test translation of port definition (1234, '1234/tcp', '1234/udp',
        etc.) into the format which docker-py uses (integer for TCP ports,
        'port_num/udp' for UDP ports).
        """
        # Test TCP port (passed as int, no protocol passed)
        self.assertEqual(translate_helpers.get_port_def(2222), 2222)
        # Test TCP port (passed as str, no protocol passed)
        self.assertEqual(translate_helpers.get_port_def("2222"), 2222)
        # Test TCP port (passed as str, with protocol passed)
        self.assertEqual(translate_helpers.get_port_def("2222", "tcp"), 2222)
        # Test TCP port (proto passed in port_num, with passed proto ignored).
        # This is a contrived example as we would never invoke the function in
        # this way, but it tests that we are taking the port number from the
        # port_num argument and ignoring the passed protocol.
        self.assertEqual(translate_helpers.get_port_def("2222/tcp", "udp"), 2222)

        # Test UDP port (passed as int)
        self.assertEqual(translate_helpers.get_port_def(2222, "udp"), (2222, "udp"))
        # Test UDP port (passed as string)
        self.assertEqual(translate_helpers.get_port_def("2222", "udp"), (2222, "udp"))
        # Test UDP port (proto passed in port_num
        self.assertEqual(translate_helpers.get_port_def("2222/udp"), (2222, "udp"))

    def test_get_port_range(self):
        """
        Test extracting the start and end of a port range from a port range
        expression (e.g. 4505-4506)
        """
        # Passing a single int should return the start and end as the same value
        self.assertEqual(translate_helpers.get_port_range(2222), (2222, 2222))
        # Same as above but with port number passed as a string
        self.assertEqual(translate_helpers.get_port_range("2222"), (2222, 2222))
        # Passing a port range
        self.assertEqual(translate_helpers.get_port_range("2222-2223"), (2222, 2223))
        # Error case: port range start is greater than end
        with self.assertRaisesRegex(
            ValueError,
            r"Start of port range \(2222\) cannot be greater than end of "
            r"port range \(2221\)",
        ):
            translate_helpers.get_port_range("2222-2221")
        # Error case: non-numeric input
        with self.assertRaisesRegex(
            ValueError, "'2222-bar' is non-numeric or an invalid port range"
        ):
            translate_helpers.get_port_range("2222-bar")
