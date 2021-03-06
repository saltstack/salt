"""
    :copyright: Copyright 2013-2017 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    tests.support.helpers
    ~~~~~~~~~~~~~~~~~~~~~

    Test support helpers
"""
import base64
import builtins
import errno
import fnmatch
import functools
import inspect
import json
import logging
import os
import pathlib
import random
import shutil
import socket
import string
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import types
from contextlib import contextmanager

import attr
import pytest
import salt.ext.tornado.ioloop
import salt.ext.tornado.web
import salt.utils.files
import salt.utils.platform
import salt.utils.pycrypto
import salt.utils.stringutils
import salt.utils.versions
from saltfactories.exceptions import FactoryFailure as ProcessFailed
from saltfactories.utils.ports import get_unused_localhost_port
from saltfactories.utils.processes import ProcessResult
from tests.support.mock import patch
from tests.support.runtests import RUNTIME_VARS
from tests.support.sminion import create_sminion
from tests.support.unit import SkipTest, _id, skip

log = logging.getLogger(__name__)

HAS_SYMLINKS = None


PRE_PYTEST_SKIP_OR_NOT = "PRE_PYTEST_DONT_SKIP" not in os.environ
PRE_PYTEST_SKIP_REASON = (
    "PRE PYTEST - This test was skipped before running under pytest"
)
PRE_PYTEST_SKIP = pytest.mark.skipif(
    PRE_PYTEST_SKIP_OR_NOT, reason=PRE_PYTEST_SKIP_REASON
)
ON_PY35 = sys.version_info < (3, 6)


def no_symlinks():
    """
    Check if git is installed and has symlinks enabled in the configuration.
    """
    global HAS_SYMLINKS
    if HAS_SYMLINKS is not None:
        return not HAS_SYMLINKS
    output = ""
    try:
        output = subprocess.Popen(
            ["git", "config", "--get", "core.symlinks"],
            cwd=RUNTIME_VARS.TMP,
            stdout=subprocess.PIPE,
        ).communicate()[0]
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            raise
    except subprocess.CalledProcessError:
        # git returned non-zero status
        pass
    HAS_SYMLINKS = False
    if output.strip() == "true":
        HAS_SYMLINKS = True
    return not HAS_SYMLINKS


def destructiveTest(caller):
    """
    Mark a test case as a destructive test for example adding or removing users
    from your system.

    .. code-block:: python

        class MyTestCase(TestCase):

            @destructiveTest
            def test_create_user(self):
                pass
    """
    salt.utils.versions.warn_until_date(
        "20220101",
        "Please stop using `@destructiveTest`, it will be removed in {date}, and instead use "
        "`@pytest.mark.destructive_test`.",
        stacklevel=3,
    )
    setattr(caller, "__destructive_test__", True)

    if os.environ.get("DESTRUCTIVE_TESTS", "False").lower() == "false":
        reason = "Destructive tests are disabled"

        if not isinstance(caller, type):

            @functools.wraps(caller)
            def skip_wrapper(*args, **kwargs):
                raise SkipTest(reason)

            caller = skip_wrapper

        caller.__unittest_skip__ = True
        caller.__unittest_skip_why__ = reason

    return caller


def expensiveTest(caller):
    """
    Mark a test case as an expensive test, for example, a test which can cost
    money(Salt's cloud provider tests).

    .. code-block:: python

        class MyTestCase(TestCase):

            @expensiveTest
            def test_create_user(self):
                pass
    """
    salt.utils.versions.warn_until_date(
        "20220101",
        "Please stop using `@expensiveTest`, it will be removed in {date}, and instead use "
        "`@pytest.mark.expensive_test`.",
        stacklevel=3,
    )
    setattr(caller, "__expensive_test__", True)

    if os.environ.get("EXPENSIVE_TESTS", "False").lower() == "false":
        reason = "Expensive tests are disabled"

        if not isinstance(caller, type):

            @functools.wraps(caller)
            def skip_wrapper(*args, **kwargs):
                raise SkipTest(reason)

            caller = skip_wrapper

        caller.__unittest_skip__ = True
        caller.__unittest_skip_why__ = reason

    return caller


def slowTest(caller):
    """
    Mark a test case as a slow test.
    .. code-block:: python
        class MyTestCase(TestCase):
            @slowTest
            def test_that_takes_much_time(self):
                pass
    """
    salt.utils.versions.warn_until_date(
        "20220101",
        "Please stop using `@slowTest`, it will be removed in {date}, and instead use "
        "`@pytest.mark.slow_test`.",
        stacklevel=3,
    )
    setattr(caller, "__slow_test__", True)
    return caller


def flaky(caller=None, condition=True, attempts=4):
    """
    Mark a test as flaky. The test will attempt to run five times,
    looking for a successful run. After an immediate second try,
    it will use an exponential backoff starting with one second.

    .. code-block:: python

        class MyTestCase(TestCase):

        @flaky
        def test_sometimes_works(self):
            pass
    """
    salt.utils.versions.warn_until_date(
        "20220101",
        "Please stop using `@flaky`, it will be removed in {date}, and instead use "
        "`@pytest.mark.flaky`. See https://pypi.org/project/flaky for information on "
        "how to use it.",
        stacklevel=3,
    )
    if caller is None:
        return functools.partial(flaky, condition=condition, attempts=attempts)

    if isinstance(condition, bool) and condition is False:
        # Don't even decorate
        return caller
    elif callable(condition):
        if condition() is False:
            # Don't even decorate
            return caller

    if inspect.isclass(caller):
        attrs = [n for n in dir(caller) if n.startswith("test_")]
        for attrname in attrs:
            try:
                function = getattr(caller, attrname)
                if not inspect.isfunction(function) and not inspect.ismethod(function):
                    continue
                setattr(
                    caller,
                    attrname,
                    flaky(caller=function, condition=condition, attempts=attempts),
                )
            except Exception as exc:  # pylint: disable=broad-except
                log.exception(exc)
                continue
        return caller

    @functools.wraps(caller)
    def wrap(cls):
        for attempt in range(0, attempts):
            try:
                if attempt > 0:
                    # Run through setUp again
                    # We only run it after the first iteration(>0) because the regular
                    # test runner will have already ran setUp the first time
                    setup = getattr(cls, "setUp", None)
                    if callable(setup):
                        setup()
                return caller(cls)
            except SkipTest as exc:
                cls.skipTest(exc.args[0])
            except Exception as exc:  # pylint: disable=broad-except
                exc_info = sys.exc_info()
                if isinstance(exc, SkipTest):
                    raise exc_info[0].with_traceback(exc_info[1], exc_info[2])
                if not isinstance(exc, AssertionError) and log.isEnabledFor(
                    logging.DEBUG
                ):
                    log.exception(exc, exc_info=exc_info)
                if attempt >= attempts - 1:
                    # We won't try to run tearDown once the attempts are exhausted
                    # because the regular test runner will do that for us
                    raise exc_info[0].with_traceback(exc_info[1], exc_info[2])
                # Run through tearDown again
                teardown = getattr(cls, "tearDown", None)
                if callable(teardown):
                    teardown()
                backoff_time = attempt ** 2
                log.info("Found Exception. Waiting %s seconds to retry.", backoff_time)
                time.sleep(backoff_time)
        return cls

    return wrap


def requires_sshd_server(caller):
    """
    Mark a test as requiring the tests SSH daemon running.

    .. code-block:: python

        class MyTestCase(TestCase):

            @requiresSshdServer
            def test_create_user(self):
                pass
    """
    raise RuntimeError(
        "Please replace @requires_sshd_server with @pytest.mark.requires_sshd_server"
    )


class RedirectStdStreams:
    """
    Temporarily redirect system output to file like objects.
    Default is to redirect to `os.devnull`, which just mutes output, `stdout`
    and `stderr`.
    """

    def __init__(self, stdout=None, stderr=None):
        if stdout is None:
            # pylint: disable=resource-leakage
            stdout = salt.utils.files.fopen(os.devnull, "w")
            # pylint: enable=resource-leakage
        if stderr is None:
            # pylint: disable=resource-leakage
            stderr = salt.utils.files.fopen(os.devnull, "w")
            # pylint: enable=resource-leakage

        self.__stdout = stdout
        self.__stderr = stderr
        self.__redirected = False
        self.patcher = patch.multiple(sys, stderr=self.__stderr, stdout=self.__stdout)

    def __enter__(self):
        self.redirect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.unredirect()

    def redirect(self):
        self.old_stdout = sys.stdout
        self.old_stdout.flush()
        self.old_stderr = sys.stderr
        self.old_stderr.flush()
        self.patcher.start()
        self.__redirected = True

    def unredirect(self):
        if not self.__redirected:
            return
        try:
            self.__stdout.flush()
            self.__stdout.close()
        except ValueError:
            # already closed?
            pass
        try:
            self.__stderr.flush()
            self.__stderr.close()
        except ValueError:
            # already closed?
            pass
        self.patcher.stop()

    def flush(self):
        if self.__redirected:
            try:
                self.__stdout.flush()
            except Exception:  # pylint: disable=broad-except
                pass
            try:
                self.__stderr.flush()
            except Exception:  # pylint: disable=broad-except
                pass


class TstSuiteLoggingHandler:
    """
    Simple logging handler which can be used to test if certain logging
    messages get emitted or not:

    .. code-block:: python

        with TstSuiteLoggingHandler() as handler:
            # (...)               Do what ever you wish here
            handler.messages    # here are the emitted log messages

    """

    def __init__(self, level=0, format="%(levelname)s:%(message)s"):
        self.level = level
        self.format = format
        self.activated = False
        self.prev_logging_level = None

    def activate(self):
        class Handler(logging.Handler):
            def __init__(self, level):
                logging.Handler.__init__(self, level)
                self.messages = []

            def emit(self, record):
                self.messages.append(self.format(record))

        self.handler = Handler(self.level)
        formatter = logging.Formatter(self.format)
        self.handler.setFormatter(formatter)
        logging.root.addHandler(self.handler)
        self.activated = True
        # Make sure we're running with the lowest logging level with our
        # tests logging handler
        current_logging_level = logging.root.getEffectiveLevel()
        if current_logging_level > logging.DEBUG:
            self.prev_logging_level = current_logging_level
            logging.root.setLevel(0)

    def deactivate(self):
        if not self.activated:
            return
        logging.root.removeHandler(self.handler)
        # Restore previous logging level if changed
        if self.prev_logging_level is not None:
            logging.root.setLevel(self.prev_logging_level)

    @property
    def messages(self):
        if not self.activated:
            return []
        return self.handler.messages

    def clear(self):
        self.handler.messages = []

    def __enter__(self):
        self.activate()
        return self

    def __exit__(self, type, value, traceback):
        self.deactivate()
        self.activated = False

    # Mimic some handler attributes and methods
    @property
    def lock(self):
        if self.activated:
            return self.handler.lock

    def createLock(self):
        if self.activated:
            return self.handler.createLock()

    def acquire(self):
        if self.activated:
            return self.handler.acquire()

    def release(self):
        if self.activated:
            return self.handler.release()


class ForceImportErrorOn:
    """
    This class is meant to be used in mock'ed test cases which require an
    ``ImportError`` to be raised.

    >>> import os.path
    >>> with ForceImportErrorOn('os.path'):
    ...     import os.path
    ...
    Traceback (most recent call last):
      File "<stdin>", line 2, in <module>
      File "salttesting/helpers.py", line 263, in __import__
        'Forced ImportError raised for {0!r}'.format(name)
    ImportError: Forced ImportError raised for 'os.path'
    >>>


    >>> with ForceImportErrorOn(('os', 'path')):
    ...     import os.path
    ...     sys.modules.pop('os', None)
    ...     from os import path
    ...
    <module 'os' from '/usr/lib/python2.7/os.pyc'>
    Traceback (most recent call last):
      File "<stdin>", line 4, in <module>
      File "salttesting/helpers.py", line 288, in __fake_import__
        name, ', '.join(fromlist)
    ImportError: Forced ImportError raised for 'from os import path'
    >>>


    >>> with ForceImportErrorOn(('os', 'path'), 'os.path'):
    ...     import os.path
    ...     sys.modules.pop('os', None)
    ...     from os import path
    ...
    Traceback (most recent call last):
      File "<stdin>", line 2, in <module>
      File "salttesting/helpers.py", line 281, in __fake_import__
        'Forced ImportError raised for {0!r}'.format(name)
    ImportError: Forced ImportError raised for 'os.path'
    >>>
    """

    def __init__(self, *module_names):
        self.__module_names = {}
        for entry in module_names:
            if isinstance(entry, (list, tuple)):
                modname = entry[0]
                self.__module_names[modname] = set(entry[1:])
            else:
                self.__module_names[entry] = None
        self.__original_import = builtins.__import__
        self.patcher = patch.object(builtins, "__import__", self.__fake_import__)

    def patch_import_function(self):
        self.patcher.start()

    def restore_import_funtion(self):
        self.patcher.stop()

    def __fake_import__(
        self, name, globals_=None, locals_=None, fromlist=None, level=None
    ):
        if level is None:
            level = 0
        if fromlist is None:
            fromlist = []

        if name in self.__module_names:
            importerror_fromlist = self.__module_names.get(name)
            if importerror_fromlist is None:
                raise ImportError("Forced ImportError raised for {!r}".format(name))

            if importerror_fromlist.intersection(set(fromlist)):
                raise ImportError(
                    "Forced ImportError raised for {!r}".format(
                        "from {} import {}".format(name, ", ".join(fromlist))
                    )
                )
        return self.__original_import(name, globals_, locals_, fromlist, level)

    def __enter__(self):
        self.patch_import_function()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.restore_import_funtion()


class MockWraps:
    """
    Helper class to be used with the mock library.
    To be used in the ``wraps`` keyword of ``Mock`` or ``MagicMock`` where you
    want to trigger a side effect for X times, and afterwards, call the
    original and un-mocked method.

    As an example:

    >>> def original():
    ...     print 'original'
    ...
    >>> def side_effect():
    ...     print 'side effect'
    ...
    >>> mw = MockWraps(original, 2, side_effect)
    >>> mw()
    side effect
    >>> mw()
    side effect
    >>> mw()
    original
    >>>

    """

    def __init__(self, original, expected_failures, side_effect):
        self.__original = original
        self.__expected_failures = expected_failures
        self.__side_effect = side_effect
        self.__call_counter = 0

    def __call__(self, *args, **kwargs):
        try:
            if self.__call_counter < self.__expected_failures:
                if isinstance(self.__side_effect, types.FunctionType):
                    return self.__side_effect()
                raise self.__side_effect
            return self.__original(*args, **kwargs)
        finally:
            self.__call_counter += 1


def requires_network(only_local_network=False):
    """
    Simple decorator which is supposed to skip a test case in case there's no
    network connection to the internet.
    """
    salt.utils.versions.warn_until_date(
        "20220101",
        "Please stop using `@requires_network`, it will be removed in {date}, and instead use "
        "`@pytest.mark.requires_network`.",
        stacklevel=3,
    )

    def decorator(func):
        @functools.wraps(func)
        def wrapper(cls, *args, **kwargs):
            has_local_network = False
            # First lets try if we have a local network. Inspired in
            # verify_socket
            try:
                pubsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                retsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                pubsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                pubsock.bind(("", 18000))
                pubsock.close()
                retsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                retsock.bind(("", 18001))
                retsock.close()
                has_local_network = True
            except OSError:
                # I wonder if we just have IPV6 support?
                try:
                    pubsock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                    retsock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                    pubsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    pubsock.bind(("", 18000))
                    pubsock.close()
                    retsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    retsock.bind(("", 18001))
                    retsock.close()
                    has_local_network = True
                except OSError:
                    # Let's continue
                    pass

            if only_local_network is True:
                if has_local_network is False:
                    # Since we're only supposed to check local network, and no
                    # local network was detected, skip the test
                    cls.skipTest("No local network was detected")
                return func(cls)

            if os.environ.get("NO_INTERNET"):
                cls.skipTest("Environment variable NO_INTERNET is set.")

            # We are using the google.com DNS records as numerical IPs to avoid
            # DNS lookups which could greatly slow down this check
            for addr in (
                "173.194.41.198",
                "173.194.41.199",
                "173.194.41.200",
                "173.194.41.201",
                "173.194.41.206",
                "173.194.41.192",
                "173.194.41.193",
                "173.194.41.194",
                "173.194.41.195",
                "173.194.41.196",
                "173.194.41.197",
            ):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    sock.settimeout(0.25)
                    sock.connect((addr, 80))
                    # We connected? Stop the loop
                    break
                except OSError:
                    # Let's check the next IP
                    continue
                else:
                    cls.skipTest("No internet network connection was detected")
                finally:
                    sock.close()
            return func(cls, *args, **kwargs)

        return wrapper

    return decorator


def with_system_user(
    username, on_existing="delete", delete=True, password=None, groups=None
):
    """
    Create and optionally destroy a system user to be used within a test
    case. The system user is created using the ``user`` salt module.

    The decorated testcase function must accept 'username' as an argument.

    :param username: The desired username for the system user.
    :param on_existing: What to do when the desired username is taken. The
      available options are:

      * nothing: Do nothing, act as if the user was created.
      * delete: delete and re-create the existing user
      * skip: skip the test case
    """
    if on_existing not in ("nothing", "delete", "skip"):
        raise RuntimeError(
            "The value of 'on_existing' can only be one of, "
            "'nothing', 'delete' and 'skip'"
        )

    if not isinstance(delete, bool):
        raise RuntimeError("The value of 'delete' can only be 'True' or 'False'")

    def decorator(func):
        @functools.wraps(func)
        def wrap(cls):

            # Let's add the user to the system.
            log.debug("Creating system user {!r}".format(username))
            kwargs = {"timeout": 60, "groups": groups}
            if salt.utils.platform.is_windows():
                kwargs.update({"password": password})
            create_user = cls.run_function("user.add", [username], **kwargs)
            if not create_user:
                log.debug("Failed to create system user")
                # The user was not created
                if on_existing == "skip":
                    cls.skipTest("Failed to create system user {!r}".format(username))

                if on_existing == "delete":
                    log.debug("Deleting the system user {!r}".format(username))
                    delete_user = cls.run_function(
                        "user.delete", [username, True, True]
                    )
                    if not delete_user:
                        cls.skipTest(
                            "A user named {!r} already existed on the "
                            "system and re-creating it was not possible".format(
                                username
                            )
                        )
                    log.debug("Second time creating system user {!r}".format(username))
                    create_user = cls.run_function("user.add", [username], **kwargs)
                    if not create_user:
                        cls.skipTest(
                            "A user named {!r} already existed, was deleted "
                            "as requested, but re-creating it was not possible".format(
                                username
                            )
                        )
            if not salt.utils.platform.is_windows() and password is not None:
                if salt.utils.platform.is_darwin():
                    hashed_password = password
                else:
                    hashed_password = salt.utils.pycrypto.gen_hash(password=password)
                hashed_password = "'{}'".format(hashed_password)
                add_pwd = cls.run_function(
                    "shadow.set_password", [username, hashed_password]
                )

            failure = None
            try:
                try:
                    return func(cls, username)
                except Exception as exc:  # pylint: disable=W0703
                    log.error(
                        "Running {!r} raised an exception: {}".format(func, exc),
                        exc_info=True,
                    )
                    # Store the original exception details which will be raised
                    # a little further down the code
                    failure = sys.exc_info()
            finally:
                if delete:
                    delete_user = cls.run_function(
                        "user.delete", [username, True, True], timeout=60
                    )
                    if not delete_user:
                        if failure is None:
                            log.warning(
                                "Although the actual test-case did not fail, "
                                "deleting the created system user {!r} "
                                "afterwards did.".format(username)
                            )
                        else:
                            log.warning(
                                "The test-case failed and also did the removal"
                                " of the system user {!r}".format(username)
                            )
                if failure is not None:
                    # If an exception was thrown, raise it
                    raise failure[1].with_traceback(failure[2])

        return wrap

    return decorator


def with_system_group(group, on_existing="delete", delete=True):
    """
    Create and optionally destroy a system group to be used within a test
    case. The system user is crated using the ``group`` salt module.

    The decorated testcase function must accept 'group' as an argument.

    :param group: The desired group name for the system user.
    :param on_existing: What to do when the desired username is taken. The
      available options are:

      * nothing: Do nothing, act as if the group was created
      * delete: delete and re-create the existing user
      * skip: skip the test case
    """
    if on_existing not in ("nothing", "delete", "skip"):
        raise RuntimeError(
            "The value of 'on_existing' can only be one of, "
            "'nothing', 'delete' and 'skip'"
        )

    if not isinstance(delete, bool):
        raise RuntimeError("The value of 'delete' can only be 'True' or 'False'")

    def decorator(func):
        @functools.wraps(func)
        def wrap(cls):

            # Let's add the user to the system.
            log.debug("Creating system group {!r}".format(group))
            create_group = cls.run_function("group.add", [group])
            if not create_group:
                log.debug("Failed to create system group")
                # The group was not created
                if on_existing == "skip":
                    cls.skipTest("Failed to create system group {!r}".format(group))

                if on_existing == "delete":
                    log.debug("Deleting the system group {!r}".format(group))
                    delete_group = cls.run_function("group.delete", [group])
                    if not delete_group:
                        cls.skipTest(
                            "A group named {!r} already existed on the "
                            "system and re-creating it was not possible".format(group)
                        )
                    log.debug("Second time creating system group {!r}".format(group))
                    create_group = cls.run_function("group.add", [group])
                    if not create_group:
                        cls.skipTest(
                            "A group named {!r} already existed, was deleted "
                            "as requested, but re-creating it was not possible".format(
                                group
                            )
                        )

            failure = None
            try:
                try:
                    return func(cls, group)
                except Exception as exc:  # pylint: disable=W0703
                    log.error(
                        "Running {!r} raised an exception: {}".format(func, exc),
                        exc_info=True,
                    )
                    # Store the original exception details which will be raised
                    # a little further down the code
                    failure = sys.exc_info()
            finally:
                if delete:
                    delete_group = cls.run_function("group.delete", [group])
                    if not delete_group:
                        if failure is None:
                            log.warning(
                                "Although the actual test-case did not fail, "
                                "deleting the created system group {!r} "
                                "afterwards did.".format(group)
                            )
                        else:
                            log.warning(
                                "The test-case failed and also did the removal"
                                " of the system group {!r}".format(group)
                            )
                if failure is not None:
                    # If an exception was thrown, raise it
                    raise failure[1].with_traceback(failure[2])

        return wrap

    return decorator


def with_system_user_and_group(username, group, on_existing="delete", delete=True):
    """
    Create and optionally destroy a system user and group to be used within a
    test case. The system user is crated using the ``user`` salt module, and
    the system group is created with the ``group`` salt module.

    The decorated testcase function must accept both the 'username' and 'group'
    arguments.

    :param username: The desired username for the system user.
    :param group: The desired name for the system group.
    :param on_existing: What to do when the desired username is taken. The
      available options are:

      * nothing: Do nothing, act as if the user was created.
      * delete: delete and re-create the existing user
      * skip: skip the test case
    """
    if on_existing not in ("nothing", "delete", "skip"):
        raise RuntimeError(
            "The value of 'on_existing' can only be one of, "
            "'nothing', 'delete' and 'skip'"
        )

    if not isinstance(delete, bool):
        raise RuntimeError("The value of 'delete' can only be 'True' or 'False'")

    def decorator(func):
        @functools.wraps(func)
        def wrap(cls):

            # Let's add the user to the system.
            log.debug("Creating system user {!r}".format(username))
            create_user = cls.run_function("user.add", [username])
            log.debug("Creating system group {!r}".format(group))
            create_group = cls.run_function("group.add", [group])
            if not create_user:
                log.debug("Failed to create system user")
                # The user was not created
                if on_existing == "skip":
                    cls.skipTest("Failed to create system user {!r}".format(username))

                if on_existing == "delete":
                    log.debug("Deleting the system user {!r}".format(username))
                    delete_user = cls.run_function(
                        "user.delete", [username, True, True]
                    )
                    if not delete_user:
                        cls.skipTest(
                            "A user named {!r} already existed on the "
                            "system and re-creating it was not possible".format(
                                username
                            )
                        )
                    log.debug("Second time creating system user {!r}".format(username))
                    create_user = cls.run_function("user.add", [username])
                    if not create_user:
                        cls.skipTest(
                            "A user named {!r} already existed, was deleted "
                            "as requested, but re-creating it was not possible".format(
                                username
                            )
                        )
            if not create_group:
                log.debug("Failed to create system group")
                # The group was not created
                if on_existing == "skip":
                    cls.skipTest("Failed to create system group {!r}".format(group))

                if on_existing == "delete":
                    log.debug("Deleting the system group {!r}".format(group))
                    delete_group = cls.run_function("group.delete", [group])
                    if not delete_group:
                        cls.skipTest(
                            "A group named {!r} already existed on the "
                            "system and re-creating it was not possible".format(group)
                        )
                    log.debug("Second time creating system group {!r}".format(group))
                    create_group = cls.run_function("group.add", [group])
                    if not create_group:
                        cls.skipTest(
                            "A group named {!r} already existed, was deleted "
                            "as requested, but re-creating it was not possible".format(
                                group
                            )
                        )

            failure = None
            try:
                try:
                    return func(cls, username, group)
                except Exception as exc:  # pylint: disable=W0703
                    log.error(
                        "Running {!r} raised an exception: {}".format(func, exc),
                        exc_info=True,
                    )
                    # Store the original exception details which will be raised
                    # a little further down the code
                    failure = sys.exc_info()
            finally:
                if delete:
                    delete_user = cls.run_function(
                        "user.delete", [username, True, True]
                    )
                    delete_group = cls.run_function("group.delete", [group])
                    if not delete_user:
                        if failure is None:
                            log.warning(
                                "Although the actual test-case did not fail, "
                                "deleting the created system user {!r} "
                                "afterwards did.".format(username)
                            )
                        else:
                            log.warning(
                                "The test-case failed and also did the removal"
                                " of the system user {!r}".format(username)
                            )
                    if not delete_group:
                        if failure is None:
                            log.warning(
                                "Although the actual test-case did not fail, "
                                "deleting the created system group {!r} "
                                "afterwards did.".format(group)
                            )
                        else:
                            log.warning(
                                "The test-case failed and also did the removal"
                                " of the system group {!r}".format(group)
                            )
                if failure is not None:
                    # If an exception was thrown, raise it
                    raise failure[1].with_traceback(failure[2])

        return wrap

    return decorator


class WithTempfile:
    def __init__(self, **kwargs):
        self.create = kwargs.pop("create", True)
        if "dir" not in kwargs:
            kwargs["dir"] = RUNTIME_VARS.TMP
        if "prefix" not in kwargs:
            kwargs["prefix"] = "__salt.test."
        self.kwargs = kwargs

    def __call__(self, func):
        self.func = func
        return functools.wraps(func)(
            # pylint: disable=unnecessary-lambda
            lambda testcase, *args, **kwargs: self.wrap(testcase, *args, **kwargs)
            # pylint: enable=unnecessary-lambda
        )

    def wrap(self, testcase, *args, **kwargs):
        name = salt.utils.files.mkstemp(**self.kwargs)
        if not self.create:
            os.remove(name)
        try:
            return self.func(testcase, name, *args, **kwargs)
        finally:
            try:
                os.remove(name)
            except OSError:
                pass


with_tempfile = WithTempfile


class WithTempdir:
    def __init__(self, **kwargs):
        self.create = kwargs.pop("create", True)
        if "dir" not in kwargs:
            kwargs["dir"] = RUNTIME_VARS.TMP
        self.kwargs = kwargs

    def __call__(self, func):
        self.func = func
        return functools.wraps(func)(
            # pylint: disable=unnecessary-lambda
            lambda testcase, *args, **kwargs: self.wrap(testcase, *args, **kwargs)
            # pylint: enable=unnecessary-lambda
        )

    def wrap(self, testcase, *args, **kwargs):
        tempdir = tempfile.mkdtemp(**self.kwargs)
        if not self.create:
            os.rmdir(tempdir)
        try:
            return self.func(testcase, tempdir, *args, **kwargs)
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)


with_tempdir = WithTempdir


def requires_system_grains(func):
    """
    Function decorator which loads and passes the system's grains to the test
    case.
    """

    @functools.wraps(func)
    def decorator(*args, **kwargs):
        if not hasattr(requires_system_grains, "__grains__"):
            # Late import
            from tests.support.sminion import build_minion_opts

            opts = build_minion_opts(minion_id="runtests-internal-sminion")
            requires_system_grains.__grains__ = salt.loader.grains(opts)
        kwargs["grains"] = requires_system_grains.__grains__
        return func(*args, **kwargs)

    return decorator


@requires_system_grains
def runs_on(grains=None, **kwargs):
    """
    Skip the test if grains don't match the values passed into **kwargs
    if a kwarg value is a list then skip if the grains don't match any item in the list
    """
    reason = kwargs.pop("reason", None)
    for kw, value in kwargs.items():
        if isinstance(value, list):
            if not any(str(grains.get(kw)).lower() != str(v).lower() for v in value):
                if reason is None:
                    reason = "This test does not run on {}={}".format(
                        kw, grains.get(kw)
                    )
                return skip(reason)
        else:
            if str(grains.get(kw)).lower() != str(value).lower():
                if reason is None:
                    reason = "This test runs on {}={}, not {}".format(
                        kw, value, grains.get(kw)
                    )
                return skip(reason)
    return _id


@requires_system_grains
def not_runs_on(grains=None, **kwargs):
    """
    Reverse of `runs_on`.
    Skip the test if any grains match the values passed into **kwargs
    if a kwarg value is a list then skip if the grains match any item in the list
    """
    reason = kwargs.pop("reason", None)
    for kw, value in kwargs.items():
        if isinstance(value, list):
            if any(str(grains.get(kw)).lower() == str(v).lower() for v in value):
                if reason is None:
                    reason = "This test does not run on {}={}".format(
                        kw, grains.get(kw)
                    )
                return skip(reason)
        else:
            if str(grains.get(kw)).lower() == str(value).lower():
                if reason is None:
                    reason = "This test does not run on {}={}, got {}".format(
                        kw, value, grains.get(kw)
                    )
                return skip(reason)
    return _id


def _check_required_sminion_attributes(sminion_attr, *required_items):
    """
    :param sminion_attr: The name of the sminion attribute to check, such as 'functions' or 'states'
    :param required_items: The items that must be part of the designated sminion attribute for the decorated test
    :return The packages that are not available
    """
    # Late import
    from tests.support.sminion import create_sminion

    required_salt_items = set(required_items)
    sminion = create_sminion(minion_id="runtests-internal-sminion")
    available_items = list(getattr(sminion, sminion_attr))
    not_available_items = set()

    name = "__not_available_{items}s__".format(items=sminion_attr)
    if not hasattr(sminion, name):
        setattr(sminion, name, set())

    cached_not_available_items = getattr(sminion, name)

    for not_available_item in cached_not_available_items:
        if not_available_item in required_salt_items:
            not_available_items.add(not_available_item)
            required_salt_items.remove(not_available_item)

    for required_item_name in required_salt_items:
        search_name = required_item_name
        if "." not in search_name:
            search_name += ".*"
        if not fnmatch.filter(available_items, search_name):
            not_available_items.add(required_item_name)
            cached_not_available_items.add(required_item_name)

    return not_available_items


def requires_salt_states(*names):
    """
    Makes sure the passed salt state is available. Skips the test if not

    .. versionadded:: 3000
    """
    salt.utils.versions.warn_until_date(
        "20220101",
        "Please stop using `@requires_salt_states`, it will be removed in {date}, and instead use "
        "`@pytest.mark.requires_salt_states`.",
        stacklevel=3,
    )
    not_available = _check_required_sminion_attributes("states", *names)
    if not_available:
        return skip("Unavailable salt states: {}".format(*not_available))
    return _id


def requires_salt_modules(*names):
    """
    Makes sure the passed salt module is available. Skips the test if not

    .. versionadded:: 0.5.2
    """
    salt.utils.versions.warn_until_date(
        "20220101",
        "Please stop using `@requires_salt_modules`, it will be removed in {date}, and instead use "
        "`@pytest.mark.requires_salt_modules`.",
        stacklevel=3,
    )
    not_available = _check_required_sminion_attributes("functions", *names)
    if not_available:
        return skip("Unavailable salt modules: {}".format(*not_available))
    return _id


def skip_if_binaries_missing(*binaries, **kwargs):
    salt.utils.versions.warn_until_date(
        "20220101",
        "Please stop using `@skip_if_binaries_missing`, it will be removed in {date}, and instead use "
        "`@pytest.mark.skip_if_binaries_missing`.",
        stacklevel=3,
    )
    import salt.utils.path

    if len(binaries) == 1:
        if isinstance(binaries[0], (list, tuple, set, frozenset)):
            binaries = binaries[0]
    check_all = kwargs.pop("check_all", False)
    message = kwargs.pop("message", None)
    if kwargs:
        raise RuntimeError(
            "The only supported keyword argument is 'check_all' and "
            "'message'. Invalid keyword arguments: {}".format(", ".join(kwargs.keys()))
        )
    if check_all:
        for binary in binaries:
            if salt.utils.path.which(binary) is None:
                return skip(
                    "{}The {!r} binary was not found".format(
                        message and "{}. ".format(message) or "", binary
                    )
                )
    elif salt.utils.path.which_bin(binaries) is None:
        return skip(
            "{}None of the following binaries was found: {}".format(
                message and "{}. ".format(message) or "", ", ".join(binaries)
            )
        )
    return _id


def skip_if_not_root(func):
    salt.utils.versions.warn_until_date(
        "20220101",
        "Please stop using `@skip_if_not_root`, it will be removed in {date}, and instead use "
        "`@pytest.mark.skip_if_not_root`.",
        stacklevel=3,
    )
    setattr(func, "__skip_if_not_root__", True)

    if not sys.platform.startswith("win"):
        if os.getuid() != 0:
            func.__unittest_skip__ = True
            func.__unittest_skip_why__ = (
                "You must be logged in as root to run this test"
            )
    else:
        current_user = salt.utils.win_functions.get_current_user()
        if current_user != "SYSTEM":
            if not salt.utils.win_functions.is_admin(current_user):
                func.__unittest_skip__ = True
                func.__unittest_skip_why__ = (
                    "You must be logged in as an Administrator to run this test"
                )
    return func


def repeat(caller=None, condition=True, times=5):
    """
    Repeat a test X amount of times until the first failure.

    .. code-block:: python

        class MyTestCase(TestCase):

        @repeat
        def test_sometimes_works(self):
            pass
    """
    if caller is None:
        return functools.partial(repeat, condition=condition, times=times)

    if isinstance(condition, bool) and condition is False:
        # Don't even decorate
        return caller
    elif callable(condition):
        if condition() is False:
            # Don't even decorate
            return caller

    if inspect.isclass(caller):
        attrs = [n for n in dir(caller) if n.startswith("test_")]
        for attrname in attrs:
            try:
                function = getattr(caller, attrname)
                if not inspect.isfunction(function) and not inspect.ismethod(function):
                    continue
                setattr(
                    caller,
                    attrname,
                    repeat(caller=function, condition=condition, times=times),
                )
            except Exception as exc:  # pylint: disable=broad-except
                log.exception(exc)
                continue
        return caller

    @functools.wraps(caller)
    def wrap(cls):
        result = None
        for attempt in range(1, times + 1):
            log.info("%s test run %d of %s times", cls, attempt, times)
            caller(cls)
        return cls

    return wrap


def http_basic_auth(login_cb=lambda username, password: False):
    """
    A crude decorator to force a handler to request HTTP Basic Authentication

    Example usage:

    .. code-block:: python

        @http_basic_auth(lambda u, p: u == 'foo' and p == 'bar')
        class AuthenticatedHandler(salt.ext.tornado.web.RequestHandler):
            pass
    """

    def wrapper(handler_class):
        def wrap_execute(handler_execute):
            def check_auth(handler, kwargs):

                auth = handler.request.headers.get("Authorization")

                if auth is None or not auth.startswith("Basic "):
                    # No username/password entered yet, we need to return a 401
                    # and set the WWW-Authenticate header to request login.
                    handler.set_status(401)
                    handler.set_header("WWW-Authenticate", "Basic realm=Restricted")

                else:
                    # Strip the 'Basic ' from the beginning of the auth header
                    # leaving the base64-encoded secret
                    username, password = base64.b64decode(auth[6:]).split(":", 1)

                    if login_cb(username, password):
                        # Authentication successful
                        return
                    else:
                        # Authentication failed
                        handler.set_status(403)

                handler._transforms = []
                handler.finish()

            def _execute(self, transforms, *args, **kwargs):
                check_auth(self, kwargs)
                return handler_execute(self, transforms, *args, **kwargs)

            return _execute

        handler_class._execute = wrap_execute(handler_class._execute)
        return handler_class

    return wrapper


def generate_random_name(prefix, size=6):
    """
    Generates a random name by combining the provided prefix with a randomly generated
    ascii string.

    .. versionadded:: 2018.3.0

    prefix
        The string to prefix onto the randomly generated ascii string.

    size
        The number of characters to generate. Default: 6.
    """
    salt.utils.versions.warn_until_date(
        "20220101",
        "Please replace your call 'generate_random_name({0})' with 'random_string({0}, lowercase=False)' as "
        "'generate_random_name' will be removed after {{date}}".format(prefix),
        stacklevel=3,
    )
    return random_string(prefix, size=size, lowercase=False)


def random_string(prefix, size=6, uppercase=True, lowercase=True, digits=True):
    """
    Generates a random string.

    ..versionadded: 3001

    Args:
        prefix(str): The prefix for the random string
        size(int): The size of the random string
        uppercase(bool): If true, include uppercased ascii chars in choice sample
        lowercase(bool): If true, include lowercased ascii chars in choice sample
        digits(bool): If true, include digits in choice sample
    Returns:
        str: The random string
    """
    if not any([uppercase, lowercase, digits]):
        raise RuntimeError(
            "At least one of 'uppercase', 'lowercase' or 'digits' needs to be true"
        )
    choices = []
    if uppercase:
        choices.extend(string.ascii_uppercase)
    if lowercase:
        choices.extend(string.ascii_lowercase)
    if digits:
        choices.extend(string.digits)

    return prefix + "".join(random.choice(choices) for _ in range(size))


class Webserver:
    """
    Starts a tornado webserver on 127.0.0.1 on a random available port

    USAGE:

    .. code-block:: python

        from tests.support.helpers import Webserver

        webserver = Webserver('/path/to/web/root')
        webserver.start()
        webserver.stop()
    """

    def __init__(self, root=None, port=None, wait=5, handler=None, ssl_opts=None):
        """
        root
            Root directory of webserver. If not passed, it will default to the
            location of the base environment of the integration suite's file
            roots (tests/integration/files/file/base/)

        port
            Port on which to listen. If not passed, a random one will be chosen
            at the time the start() function is invoked.

        wait : 5
            Number of seconds to wait for the socket to be open before raising
            an exception

        handler
            Can be used to use a subclass of tornado.web.StaticFileHandler,
            such as when enforcing authentication with the http_basic_auth
            decorator.
        """
        if port is not None and not isinstance(port, int):
            raise ValueError("port must be an integer")

        if root is None:
            root = RUNTIME_VARS.BASE_FILES
        try:
            self.root = os.path.realpath(root)
        except AttributeError:
            raise ValueError("root must be a string")

        self.port = port
        self.wait = wait
        self.handler = (
            handler if handler is not None else salt.ext.tornado.web.StaticFileHandler
        )
        self.web_root = None
        self.ssl_opts = ssl_opts

    def target(self):
        """
        Threading target which stands up the tornado application
        """
        self.ioloop = salt.ext.tornado.ioloop.IOLoop()
        self.ioloop.make_current()
        if self.handler == salt.ext.tornado.web.StaticFileHandler:
            self.application = salt.ext.tornado.web.Application(
                [(r"/(.*)", self.handler, {"path": self.root})]
            )
        else:
            self.application = salt.ext.tornado.web.Application(
                [(r"/(.*)", self.handler)]
            )
        self.application.listen(self.port, ssl_options=self.ssl_opts)
        self.ioloop.start()

    @property
    def listening(self):
        if self.port is None:
            return False
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        return sock.connect_ex(("127.0.0.1", self.port)) == 0

    def url(self, path):
        """
        Convenience function which, given a file path, will return a URL that
        points to that path. If the path is relative, it will just be appended
        to self.web_root.
        """
        if self.web_root is None:
            raise RuntimeError("Webserver instance has not been started")
        err_msg = (
            "invalid path, must be either a relative path or a path "
            "within {}".format(self.root)
        )
        try:
            relpath = (
                path if not os.path.isabs(path) else os.path.relpath(path, self.root)
            )
            if relpath.startswith(".." + os.sep):
                raise ValueError(err_msg)
            return "/".join((self.web_root, relpath))
        except AttributeError:
            raise ValueError(err_msg)

    def start(self):
        """
        Starts the webserver
        """
        if self.port is None:
            self.port = get_unused_localhost_port()

        self.web_root = "http{}://127.0.0.1:{}".format(
            "s" if self.ssl_opts else "", self.port
        )

        self.server_thread = threading.Thread(target=self.target)
        self.server_thread.daemon = True
        self.server_thread.start()

        for idx in range(self.wait + 1):
            if self.listening:
                break
            if idx != self.wait:
                time.sleep(1)
        else:
            raise Exception(
                "Failed to start tornado webserver on 127.0.0.1:{} within "
                "{} seconds".format(self.port, self.wait)
            )

    def stop(self):
        """
        Stops the webserver
        """
        self.ioloop.add_callback(self.ioloop.stop)
        self.server_thread.join()


class SaveRequestsPostHandler(salt.ext.tornado.web.RequestHandler):
    """
    Save all requests sent to the server.
    """

    received_requests = []

    def post(self, *args):  # pylint: disable=arguments-differ
        """
        Handle the post
        """
        self.received_requests.append(self.request)

    def data_received(self):  # pylint: disable=arguments-differ
        """
        Streaming not used for testing
        """
        raise NotImplementedError()


class MirrorPostHandler(salt.ext.tornado.web.RequestHandler):
    """
    Mirror a POST body back to the client
    """

    def post(self, *args):  # pylint: disable=arguments-differ
        """
        Handle the post
        """
        body = self.request.body
        log.debug("Incoming body: %s  Incoming args: %s", body, args)
        self.write(body)

    def data_received(self):  # pylint: disable=arguments-differ
        """
        Streaming not used for testing
        """
        raise NotImplementedError()


def dedent(text, linesep=os.linesep):
    """
    A wrapper around textwrap.dedent that also sets line endings.
    """
    linesep = salt.utils.stringutils.to_unicode(linesep)
    unicode_text = textwrap.dedent(salt.utils.stringutils.to_unicode(text))
    clean_text = linesep.join(unicode_text.splitlines())
    if unicode_text.endswith("\n"):
        clean_text += linesep
    if not isinstance(text, str):
        return salt.utils.stringutils.to_bytes(clean_text)
    return clean_text


class PatchedEnviron:
    def __init__(self, **kwargs):
        self.cleanup_keys = kwargs.pop("__cleanup__", ())
        self.kwargs = kwargs
        self.original_environ = None

    def __enter__(self):
        self.original_environ = os.environ.copy()
        for key in self.cleanup_keys:
            os.environ.pop(key, None)

        # Make sure there are no unicode characters in the self.kwargs if we're
        # on Python 2. These are being added to `os.environ` and causing
        # problems
        if sys.version_info < (3,):
            kwargs = self.kwargs.copy()
            clean_kwargs = {}
            for k in self.kwargs:
                key = k
                if isinstance(key, str):
                    key = key.encode("utf-8")
                if isinstance(self.kwargs[k], str):
                    kwargs[k] = kwargs[k].encode("utf-8")
                clean_kwargs[key] = kwargs[k]
            self.kwargs = clean_kwargs

        os.environ.update(**self.kwargs)
        return self

    def __exit__(self, *args):
        os.environ.clear()
        os.environ.update(self.original_environ)


patched_environ = PatchedEnviron


def _cast_to_pathlib_path(value):
    if isinstance(value, pathlib.Path):
        return value
    return pathlib.Path(str(value))


@attr.s(frozen=True, slots=True)
class VirtualEnv:
    venv_dir = attr.ib(converter=_cast_to_pathlib_path)
    env = attr.ib(default=None)
    system_site_packages = attr.ib(default=False)
    environ = attr.ib(init=False, repr=False)
    venv_python = attr.ib(init=False, repr=False)
    venv_bin_dir = attr.ib(init=False, repr=False)

    @venv_dir.default
    def _default_venv_dir(self):
        return pathlib.Path(tempfile.mkdtemp(dir=RUNTIME_VARS.TMP))

    @environ.default
    def _default_environ(self):
        environ = os.environ.copy()
        if self.env:
            environ.update(self.env)
        return environ

    @venv_python.default
    def _default_venv_python(self):
        # Once we drop Py3.5 we can stop casting to string
        if salt.utils.platform.is_windows():
            return str(self.venv_dir / "Scripts" / "python.exe")
        return str(self.venv_dir / "bin" / "python")

    @venv_bin_dir.default
    def _default_venv_bin_dir(self):
        return pathlib.Path(self.venv_python).parent

    def __enter__(self):
        try:
            self._create_virtualenv()
        except subprocess.CalledProcessError:
            raise AssertionError("Failed to create virtualenv")
        return self

    def __exit__(self, *args):
        shutil.rmtree(str(self.venv_dir), ignore_errors=True)

    def install(self, *args, **kwargs):
        return self.run(self.venv_python, "-m", "pip", "install", *args, **kwargs)

    def run(self, *args, **kwargs):
        check = kwargs.pop("check", True)
        kwargs.setdefault("cwd", str(self.venv_dir))
        kwargs.setdefault("stdout", subprocess.PIPE)
        kwargs.setdefault("stderr", subprocess.PIPE)
        kwargs.setdefault("universal_newlines", True)
        kwargs.setdefault("env", self.environ)
        proc = subprocess.run(args, check=False, **kwargs)
        ret = ProcessResult(
            exitcode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            cmdline=proc.args,
        )
        log.debug(ret)
        if check is True:
            try:
                proc.check_returncode()
            except subprocess.CalledProcessError:
                raise ProcessFailed(
                    "Command failed return code check",
                    cmdline=proc.args,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    exitcode=proc.returncode,
                )
        return ret

    @staticmethod
    def get_real_python():
        """
        The reason why the virtualenv creation is proxied by this function is mostly
        because under windows, we can't seem to properly create a virtualenv off of
        another virtualenv(we can on linux) and also because, we really don't want to
        test virtualenv creation off of another virtualenv, we want a virtualenv created
        from the original python.
        Also, on windows, we must also point to the virtualenv binary outside the existing
        virtualenv because it will fail otherwise
        """
        try:
            if salt.utils.platform.is_windows():
                return os.path.join(sys.real_prefix, os.path.basename(sys.executable))
            else:
                python_binary_names = [
                    "python{}.{}".format(*sys.version_info),
                    "python{}".format(*sys.version_info),
                    "python",
                ]
                for binary_name in python_binary_names:
                    python = os.path.join(sys.real_prefix, "bin", binary_name)
                    if os.path.exists(python):
                        break
                else:
                    raise AssertionError(
                        "Couldn't find a python binary name under '{}' matching: {}".format(
                            os.path.join(sys.real_prefix, "bin"), python_binary_names
                        )
                    )
                return python
        except AttributeError:
            return sys.executable

    def run_code(self, code_string, **kwargs):
        if code_string.startswith("\n"):
            code_string = code_string[1:]
        code_string = textwrap.dedent(code_string).rstrip()
        log.debug(
            "Code to run passed to python:\n>>>>>>>>>>\n%s\n<<<<<<<<<<", code_string
        )
        return self.run(str(self.venv_python), "-c", code_string, **kwargs)

    def get_installed_packages(self):
        data = {}
        ret = self.run(str(self.venv_python), "-m", "pip", "list", "--format", "json")
        for pkginfo in json.loads(ret.stdout):
            data[pkginfo["name"]] = pkginfo["version"]
        return data

    def _create_virtualenv(self):
        sminion = create_sminion()
        sminion.functions.virtualenv.create(
            str(self.venv_dir),
            python=self.get_real_python(),
            system_site_packages=self.system_site_packages,
        )
        self.install("-U", "pip", "setuptools!=50.*,!=51.*,!=52.*")
        log.debug("Created virtualenv in %s", self.venv_dir)


@attr.s(frozen=True, slots=True)
class SaltVirtualEnv(VirtualEnv):
    """
    This is a VirtualEnv implementation which has this salt checkout installed in it
    """

    system_site_packages = attr.ib(init=False, default=True)

    def _create_virtualenv(self):
        super()._create_virtualenv()
        self.install("--no-use-pep517", RUNTIME_VARS.CODE_DIR)


@contextmanager
def change_cwd(path):
    """
    Context manager helper to change CWD for a with code block and restore
    it at the end
    """
    old_cwd = os.getcwd()
    try:
        os.chdir(path)
        # Do stuff
        yield
    finally:
        # Restore Old CWD
        os.chdir(old_cwd)


@functools.lru_cache(maxsize=1)
def get_virtualenv_binary_path():
    # Under windows we can't seem to properly create a virtualenv off of another
    # virtualenv, we can on linux but we will still point to the virtualenv binary
    # outside the virtualenv running the test suite, if that's the case.
    try:
        real_prefix = sys.real_prefix
        # The above attribute exists, this is a virtualenv
        if salt.utils.platform.is_windows():
            virtualenv_binary = os.path.join(real_prefix, "Scripts", "virtualenv.exe")
        else:
            # We need to remove the virtualenv from PATH or we'll get the virtualenv binary
            # from within the virtualenv, we don't want that
            path = os.environ.get("PATH")
            if path is not None:
                path_items = path.split(os.pathsep)
                for item in path_items[:]:
                    if item.startswith(sys.base_prefix):
                        path_items.remove(item)
                os.environ["PATH"] = os.pathsep.join(path_items)
            virtualenv_binary = salt.utils.path.which("virtualenv")
            if path is not None:
                # Restore previous environ PATH
                os.environ["PATH"] = path
            if not virtualenv_binary.startswith(real_prefix):
                virtualenv_binary = None
        if virtualenv_binary and not os.path.exists(virtualenv_binary):
            # It doesn't exist?!
            virtualenv_binary = None
    except AttributeError:
        # We're not running inside a virtualenv
        virtualenv_binary = None
    return virtualenv_binary
