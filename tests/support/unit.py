# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`


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
'''
# pylint: disable=unused-import,blacklisted-module,deprecated-method

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import logging
from salt.ext import six
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

log = logging.getLogger(__name__)

# Set SHOW_PROC to True to show
# process details when running in verbose mode
# i.e. [CPU:15.1%|MEM:48.3%|Z:0]
SHOW_PROC = 'NO_SHOW_PROC' not in os.environ

LOREM_IPSUM = '''\
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque eget urna a arcu lacinia sagittis.
Sed scelerisque, lacus eget malesuada vestibulum, justo diam facilisis tortor, in sodales dolor
nibh eu urna. Aliquam iaculis massa risus, sed elementum risus accumsan id. Suspendisse mattis,
metus sed lacinia dictum, leo orci dapibus sapien, at porttitor sapien nulla ac velit.
Duis ac cursus leo, non varius metus. Sed laoreet felis magna, vel tempor diam malesuada nec.
Quisque cursus odio tortor. In consequat augue nisl, eget lacinia odio vestibulum eget.
Donec venenatis elementum arcu at rhoncus. Nunc pharetra erat in lacinia convallis. Ut condimentum
eu mauris sit amet convallis. Morbi vulputate vel odio non laoreet. Nullam in suscipit tellus.
Sed quis posuere urna.'''

# support python < 2.7 via unittest2
if sys.version_info < (2, 7):
    try:
        # pylint: disable=import-error
        from unittest2 import (
            TestLoader as __TestLoader,
            TextTestRunner as __TextTestRunner,
            TestCase as __TestCase,
            expectedFailure,
            TestSuite as __TestSuite,
            skip,
            skipIf,
            TestResult as _TestResult,
            TextTestResult as __TextTestResult
        )
        from unittest2.case import _id
        # pylint: enable=import-error

        class NewStyleClassMixin(object):
            '''
            Simple new style class to make pylint shut up!

            And also to avoid errors like:

                'Cannot create a consistent method resolution order (MRO) for bases'
            '''

        class _TestLoader(__TestLoader, NewStyleClassMixin):
            pass

        class _TextTestRunner(__TextTestRunner, NewStyleClassMixin):
            pass

        class _TestCase(__TestCase, NewStyleClassMixin):
            pass

        class _TestSuite(__TestSuite, NewStyleClassMixin):
            pass

        class TestResult(_TestResult, NewStyleClassMixin):
            pass

        class _TextTestResult(__TextTestResult, NewStyleClassMixin):
            pass

    except ImportError:
        raise SystemExit('You need to install unittest2 to run the salt tests')
else:
    from unittest import (
        TestLoader as _TestLoader,
        TextTestRunner as _TextTestRunner,
        TestCase as _TestCase,
        expectedFailure,
        TestSuite as _TestSuite,
        skip,
        skipIf,
        TestResult,
        TextTestResult as _TextTestResult
    )
    from unittest.case import _id


class TestSuite(_TestSuite):

    def _handleClassSetUp(self, test, result):
        previousClass = getattr(result, '_previousTestClass', None)
        currentClass = test.__class__
        if currentClass == previousClass or getattr(currentClass, 'setUpClass', None) is None:
            return super(TestSuite, self)._handleClassSetUp(test, result)

        # Store a reference to all class attributes before running the setUpClass method
        initial_class_attributes = dir(test.__class__)
        ret = super(TestSuite, self)._handleClassSetUp(test, result)
        # Store the difference in in a variable in order to check later if they were deleted
        test.__class__._prerun_class_attributes = [
                attr for attr in dir(test.__class__) if attr not in initial_class_attributes]
        return ret

    def _tearDownPreviousClass(self, test, result):
        # Run any tearDownClass code defined
        super(TestSuite, self)._tearDownPreviousClass(test, result)
        previousClass = getattr(result, '_previousTestClass', None)
        currentClass = test.__class__
        if currentClass == previousClass:
            return
        # See if the previous class attributes have been cleaned
        if previousClass and getattr(previousClass, 'tearDownClass', None):
            prerun_class_attributes = getattr(previousClass, '_prerun_class_attributes', None)
            if prerun_class_attributes is not None:
                previousClass._prerun_class_attributes = None
                del previousClass._prerun_class_attributes
                for attr in prerun_class_attributes:
                    if hasattr(previousClass, attr):
                        attr_value = getattr(previousClass, attr, None)
                        if attr_value is None:
                            continue
                        if isinstance(attr_value, (bool,) + six.string_types + six.integer_types):
                            setattr(previousClass, attr, None)
                            continue
                        log.warning('Deleting extra class attribute after test run: %s.%s(%s). '
                                    'Please consider using \'del self.%s\' on the test class '
                                    '\'tearDownClass()\' method', previousClass.__name__, attr,
                                    str(getattr(previousClass, attr))[:100], attr)
                        delattr(previousClass, attr)


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
        outcome = super(TestCase, self).run(result=result)
        for attr in dir(self):
            if attr == '_prerun_instance_attributes':
                continue
            if attr in getattr(self.__class__, '_prerun_class_attributes', ()):
                continue
            if attr not in self._prerun_instance_attributes:
                attr_value = getattr(self, attr, None)
                if attr_value is None:
                    continue
                if isinstance(attr_value, (bool,) + six.string_types + six.integer_types):
                    setattr(self, attr, None)
                    continue
                log.warning('Deleting extra class attribute after test run: %s.%s(%s). '
                            'Please consider using \'del self.%s\' on the test case '
                            '\'tearDown()\' method', self.__class__.__name__, attr,
                            getattr(self, attr), attr)
                delattr(self, attr)
        self._prerun_instance_attributes = None
        del self._prerun_instance_attributes
        return outcome

    def shortDescription(self):
        desc = _TestCase.shortDescription(self)
        if HAS_PSUTIL and SHOW_PROC:
            show_zombie_processes = 'SHOW_PROC_ZOMBIES' in os.environ
            proc_info = '[CPU:{0}%|MEM:{1}%'.format(psutil.cpu_percent(),
                                                    psutil.virtual_memory().percent)
            if show_zombie_processes:
                found_zombies = 0
                try:
                    for proc in psutil.process_iter():
                        if proc.status == psutil.STATUS_ZOMBIE:
                            found_zombies += 1
                except Exception:
                    pass
                proc_info += '|Z:{0}'.format(found_zombies)
            proc_info += '] {short_desc}'.format(short_desc=desc if desc else '')
            return proc_info
        else:
            return _TestCase.shortDescription(self)

    def assertEquals(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('assertEquals', 'assertEqual')
        )
        # return _TestCase.assertEquals(self, *args, **kwargs)

    def assertNotEquals(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('assertNotEquals', 'assertNotEqual')
        )
        # return _TestCase.assertNotEquals(self, *args, **kwargs)

    def assert_(self, *args, **kwargs):
        # The unittest2 library uses this deprecated method, we can't raise
        # the exception.
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('assert_', 'assertTrue')
        )
        # return _TestCase.assert_(self, *args, **kwargs)

    def assertAlmostEquals(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('assertAlmostEquals', 'assertAlmostEqual')
        )
        # return _TestCase.assertAlmostEquals(self, *args, **kwargs)

    def assertNotAlmostEquals(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('assertNotAlmostEquals', 'assertNotAlmostEqual')
        )
        # return _TestCase.assertNotAlmostEquals(self, *args, **kwargs)

    def failUnlessEqual(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failUnlessEqual', 'assertEqual')
        )
        # return _TestCase.failUnlessEqual(self, *args, **kwargs)

    def failIfEqual(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failIfEqual', 'assertNotEqual')
        )
        # return _TestCase.failIfEqual(self, *args, **kwargs)

    def failUnless(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failUnless', 'assertTrue')
        )
        # return _TestCase.failUnless(self, *args, **kwargs)

    def failIf(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failIf', 'assertFalse')
        )
        # return _TestCase.failIf(self, *args, **kwargs)

    def failUnlessRaises(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failUnlessRaises', 'assertRaises')
        )
        # return _TestCase.failUnlessRaises(self, *args, **kwargs)

    def failUnlessAlmostEqual(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failUnlessAlmostEqual', 'assertAlmostEqual')
        )
        # return _TestCase.failUnlessAlmostEqual(self, *args, **kwargs)

    def failIfAlmostEqual(self, *args, **kwargs):
        raise DeprecationWarning(
            'The {0}() function is deprecated. Please start using {1}() '
            'instead.'.format('failIfAlmostEqual', 'assertNotAlmostEqual')
        )
        # return _TestCase.failIfAlmostEqual(self, *args, **kwargs)

    @staticmethod
    def assert_called_once(mock):
        '''
        mock.assert_called_once only exists in PY3 in 3.6 and newer
        '''
        try:
            mock.assert_called_once()
        except AttributeError:
            log.warning('assert_called_once invoked, but not available')

    if six.PY2:
        def assertRegexpMatches(self, *args, **kwds):
            raise DeprecationWarning(
                'The {0}() function will be deprecated in python 3. Please start '
                'using {1}() instead.'.format(
                    'assertRegexpMatches',
                    'assertRegex'
                )
            )

        def assertRegex(self, text, regex, msg=None):
            # In python 2, alias to the future python 3 function
            return _TestCase.assertRegexpMatches(self, text, regex, msg=msg)

        def assertNotRegexpMatches(self, *args, **kwds):
            raise DeprecationWarning(
                'The {0}() function will be deprecated in python 3. Please start '
                'using {1}() instead.'.format(
                    'assertNotRegexpMatches',
                    'assertNotRegex'
                )
            )

        def assertNotRegex(self, text, regex, msg=None):
            # In python 2, alias to the future python 3 function
            return _TestCase.assertNotRegexpMatches(self, text, regex, msg=msg)

        def assertRaisesRegexp(self, *args, **kwds):
            raise DeprecationWarning(
                'The {0}() function will be deprecated in python 3. Please start '
                'using {1}() instead.'.format(
                    'assertRaisesRegexp',
                    'assertRaisesRegex'
                )
            )

        def assertRaisesRegex(self, exception, regexp, *args, **kwds):
            # In python 2, alias to the future python 3 function
            return _TestCase.assertRaisesRegexp(self, exception, regexp, *args, **kwds)
    else:
        def assertRegexpMatches(self, *args, **kwds):
            raise DeprecationWarning(
                'The {0}() function is deprecated. Please start using {1}() '
                'instead.'.format(
                    'assertRegexpMatches',
                    'assertRegex'
                )
            )

        def assertNotRegexpMatches(self, *args, **kwds):
            raise DeprecationWarning(
                'The {0}() function is deprecated. Please start using {1}() '
                'instead.'.format(
                    'assertNotRegexpMatches',
                    'assertNotRegex'
                )
            )

        def assertRaisesRegexp(self, *args, **kwds):
            raise DeprecationWarning(
                'The {0}() function is deprecated. Please start using {1}() '
                'instead.'.format(
                    'assertRaisesRegexp',
                    'assertRaisesRegex'
                )
            )


class TextTestResult(_TextTestResult):
    '''
    Custom TestResult class whith logs the start and the end of a test
    '''

    def startTest(self, test):
        log.debug('>>>>> START >>>>> {0}'.format(test.id()))
        return super(TextTestResult, self).startTest(test)

    def stopTest(self, test):
        log.debug('<<<<< END <<<<<<< {0}'.format(test.id()))
        return super(TextTestResult, self).stopTest(test)


class TextTestRunner(_TextTestRunner):
    '''
    Custom Text tests runner to log the start and the end of a test case
    '''
    resultclass = TextTestResult


__all__ = [
    'TestLoader',
    'TextTestRunner',
    'TestCase',
    'expectedFailure',
    'TestSuite',
    'skipIf',
    'TestResult'
]
