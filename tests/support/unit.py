"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    ============================
    Unittest Compatibility Layer
    ============================

    Compatibility layer to use :mod:`unittest <python2:unittest>` under Python
    2.7 or `unittest2`_ under Python 2.6 without having to worry about which is
    in use.

    .. attention::

        Please refer to Python's :mod:`unittest <python2:unittest>`
        documentation as the ultimate source of information, this is just a
        compatibility layer.

    .. _`unittest2`: https://pypi.python.org/pypi/unittest2
"""
# pylint: disable=unused-import,blacklisted-module,deprecated-method


import inspect
import logging
import os
import sys
import types
from unittest import TestCase as _TestCase
from unittest import TestLoader as _TestLoader
from unittest import TestResult
from unittest import TestSuite as _TestSuite
from unittest import TextTestResult as _TextTestResult
from unittest import TextTestRunner as _TextTestRunner
from unittest import expectedFailure, skip, skipIf
from unittest.case import SkipTest, _id

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

log = logging.getLogger(__name__)

# Set SHOW_PROC to True to show
# process details when running in verbose mode
# i.e. [CPU:15.1%|MEM:48.3%|Z:0]
SHOW_PROC = "NO_SHOW_PROC" not in os.environ

LOREM_IPSUM = """\
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque eget urna a arcu lacinia sagittis.
Sed scelerisque, lacus eget malesuada vestibulum, justo diam facilisis tortor, in sodales dolor
nibh eu urna. Aliquam iaculis massa risus, sed elementum risus accumsan id. Suspendisse mattis,
metus sed lacinia dictum, leo orci dapibus sapien, at porttitor sapien nulla ac velit.
Duis ac cursus leo, non varius metus. Sed laoreet felis magna, vel tempor diam malesuada nec.
Quisque cursus odio tortor. In consequat augue nisl, eget lacinia odio vestibulum eget.
Donec venenatis elementum arcu at rhoncus. Nunc pharetra erat in lacinia convallis. Ut condimentum
eu mauris sit amet convallis. Morbi vulputate vel odio non laoreet. Nullam in suscipit tellus.
Sed quis posuere urna."""


class TestSuite(_TestSuite):
    def _handleClassSetUp(self, test, result):
        previousClass = getattr(result, "_previousTestClass", None)
        currentClass = test.__class__
        if (
            currentClass == previousClass
            or getattr(currentClass, "setUpClass", None) is None
        ):
            return super()._handleClassSetUp(test, result)

        # Store a reference to all class attributes before running the setUpClass method
        initial_class_attributes = dir(test.__class__)
        super()._handleClassSetUp(test, result)
        # Store the difference in in a variable in order to check later if they were deleted
        test.__class__._prerun_class_attributes = [
            attr for attr in dir(test.__class__) if attr not in initial_class_attributes
        ]

    def _tearDownPreviousClass(self, test, result):
        # Run any tearDownClass code defined
        super()._tearDownPreviousClass(test, result)
        previousClass = getattr(result, "_previousTestClass", None)
        currentClass = test.__class__
        if currentClass == previousClass:
            return
        # See if the previous class attributes have been cleaned
        if previousClass and getattr(previousClass, "tearDownClass", None):
            prerun_class_attributes = getattr(
                previousClass, "_prerun_class_attributes", None
            )
            if prerun_class_attributes is not None:
                previousClass._prerun_class_attributes = None
                del previousClass._prerun_class_attributes
                for attr in prerun_class_attributes:
                    if hasattr(previousClass, attr):
                        attr_value = getattr(previousClass, attr, None)
                        if attr_value is None:
                            continue
                        if isinstance(attr_value, (bool, str, int)):
                            setattr(previousClass, attr, None)
                            continue
                        log.warning(
                            "Deleting extra class attribute after test run: %s.%s(%s). "
                            "Please consider using 'del self.%s' on the test class "
                            "'tearDownClass()' method",
                            previousClass.__name__,
                            attr,
                            str(getattr(previousClass, attr))[:100],
                            attr,
                        )
                        delattr(previousClass, attr)

    def _handleModuleFixture(self, test, result):
        # We override _handleModuleFixture so that we can inspect all test classes in the module.
        # If all tests in a test class are going to be skipped, mark the class to skip.
        # This avoids running setUpClass and tearDownClass unnecessarily
        currentModule = test.__class__.__module__
        try:
            module = sys.modules[currentModule]
        except KeyError:
            return
        for attr in dir(module):
            klass = getattr(module, attr)
            if not inspect.isclass(klass):
                # Not even a class? Carry on...
                continue
            if klass.__module__ != currentModule:
                # This class is not defined in the module being tested? Carry on...
                continue
            if not issubclass(klass, TestCase):
                # This class is not a subclass of TestCase, carry on
                continue

            skip_klass = True
            test_functions = [name for name in dir(klass) if name.startswith("test_")]
            for name in test_functions:
                func = getattr(klass, name)
                if not isinstance(func, types.FunctionType):
                    # Not even a function, carry on
                    continue
                if getattr(func, "__unittest_skip__", False) is False:
                    # At least one test is not going to be skipped.
                    # Stop searching.
                    skip_klass = False
                    break
            if skip_klass is True:
                klass.__unittest_skip__ = True
        return super()._handleModuleFixture(test, result)


class TestLoader(_TestLoader):
    # We're just subclassing to make sure tha tour TestSuite class is the one used
    suiteClass = TestSuite


class TestCase(_TestCase):

    # pylint: disable=expected-an-indented-block-comment,too-many-leading-hastag-for-block-comment
    ##   Commented out because it may be causing tests to hang
    ##   at the end of the run
    #
    #    _cwd = os.getcwd()
    #    _chdir_counter = 0

    #    @classmethod
    #    def tearDownClass(cls):
    #        '''
    #        Overriden method for tearing down all classes in salttesting
    #
    #        This hard-resets the environment between test classes
    #        '''
    #        # Compare where we are now compared to where we were when we began this family of tests
    #        if not cls._cwd == os.getcwd() and cls._chdir_counter > 0:
    #            os.chdir(cls._cwd)
    #            print('\nWARNING: A misbehaving test has modified the working directory!\nThe test suite has reset the working directory '
    #                    'on tearDown() to {0}\n'.format(cls._cwd))
    #            cls._chdir_counter += 1
    # pylint: enable=expected-an-indented-block-comment,too-many-leading-hastag-for-block-comment

    def run(self, result=None):
        self._prerun_instance_attributes = dir(self)
        self.maxDiff = None
        outcome = super().run(result=result)
        for attr in dir(self):
            if attr == "_prerun_instance_attributes":
                continue
            if attr in getattr(self.__class__, "_prerun_class_attributes", ()):
                continue
            if attr not in self._prerun_instance_attributes:
                attr_value = getattr(self, attr, None)
                if attr_value is None:
                    continue
                if isinstance(attr_value, (bool, str, int)):
                    setattr(self, attr, None)
                    continue
                log.warning(
                    "Deleting extra class attribute after test run: %s.%s(%s). "
                    "Please consider using 'del self.%s' on the test case "
                    "'tearDown()' method",
                    self.__class__.__name__,
                    attr,
                    getattr(self, attr),
                    attr,
                )
                delattr(self, attr)
        self._prerun_instance_attributes = None
        del self._prerun_instance_attributes
        return outcome

    def shortDescription(self):
        desc = _TestCase.shortDescription(self)
        if HAS_PSUTIL and SHOW_PROC:
            show_zombie_processes = "SHOW_PROC_ZOMBIES" in os.environ
            proc_info = "[CPU:{}%|MEM:{}%".format(
                psutil.cpu_percent(), psutil.virtual_memory().percent
            )
            if show_zombie_processes:
                found_zombies = 0
                try:
                    for proc in psutil.process_iter():
                        if proc.status == psutil.STATUS_ZOMBIE:
                            found_zombies += 1
                except Exception:  # pylint: disable=broad-except
                    pass
                proc_info += "|Z:{}".format(found_zombies)
            proc_info += "] {short_desc}".format(short_desc=desc if desc else "")
            return proc_info
        else:
            return _TestCase.shortDescription(self)

    def repack_state_returns(self, state_ret):
        """
        Accepts a state return dict and returns it back with the top level key
        names rewritten such that the ID declaration is the key instead of the
        State's unique tag. For example: 'foo' instead of
        'file_|-foo_|-/etc/foo.conf|-managed'

        This makes it easier to work with state returns when crafting asserts
        after running states.
        """
        assert isinstance(state_ret, dict), state_ret
        return {x.split("_|-")[1]: y for x, y in state_ret.items()}


class TextTestResult(_TextTestResult):
    """
    Custom TestResult class whith logs the start and the end of a test
    """

    def startTest(self, test):
        log.debug(">>>>> START >>>>> %s", test.id())
        return super().startTest(test)

    def stopTest(self, test):
        log.debug("<<<<< END <<<<<<< %s", test.id())
        return super().stopTest(test)


class TextTestRunner(_TextTestRunner):
    """
    Custom Text tests runner to log the start and the end of a test case
    """

    resultclass = TextTestResult


__all__ = [
    "TestLoader",
    "TextTestRunner",
    "TestCase",
    "expectedFailure",
    "TestSuite",
    "skipIf",
    "TestResult",
]
