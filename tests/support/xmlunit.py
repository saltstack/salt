# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)
    :copyright: Copyright 2014 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    tests.support.xmlunit
    ~~~~~~~~~~~~~~~~~~~

    XML Unit Tests
'''
# pylint: disable=wrong-import-order,wrong-import-position

# Import python libs
from __future__ import absolute_import
import io
import sys
import time
import inspect
import logging

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)


try:
    import xmlrunner.runner
    import xmlrunner.result
    import xmlrunner.unittest
    HAS_XMLRUNNER = True

    class _DelegateIO(object):
        '''
        This class defines an object that captures whatever is written to
        a stream or file.
        '''

        def __init__(self, delegate):
            self._captured = six.StringIO()
            self.delegate = delegate

        def write(self, text):
            if six.PY2 and isinstance(text, six.text_type):
                text = text.encode(__salt_system_encoding__)
            self._captured.write(text)
            self.delegate.write(text)

        def fileno(self):
            return self.delegate.fileno()

        def __getattr__(self, attr):
            try:
                return getattr(self._captured, attr)
            except (AttributeError, io.UnsupportedOperation):
                return getattr(self.delegate, attr)

    class _XMLTestResult(xmlrunner.result._XMLTestResult):
        def startTest(self, test):
            log.debug('>>>>> START >>>>> %s', test.id())
            # xmlrunner classes are NOT new-style classes
            # xmlrunner.result._XMLTestResult.startTest(self, test)

            # ----- Re-Implement startTest -------------------------------------------------------------------------->
            # The reason being that _XMLTestResult does not like tornado testing wrapping it's test class
            #   https://gist.github.com/s0undt3ch/9298a69a3492404d89a832de9efb1e68
            self.start_time = time.time()
            xmlrunner.unittest.TestResult.startTest(self, test)

            try:
                if getattr(test, '_dt_test', None) is not None:
                    # doctest.DocTestCase
                    self.filename = test._dt_test.filename
                    self.lineno = test._dt_test.lineno
                else:
                    # regular unittest.TestCase?
                    test_method = getattr(test, test._testMethodName)
                    test_class = type(test)
                    # Note: inspect can get confused with decorators, so use class.
                    self.filename = inspect.getsourcefile(test_class)
                    # Handle partial and partialmethod objects.
                    test_method = getattr(test_method, 'func', test_method)

                    # ----- Code which avoids the inspect tracebacks ------------------------------------------------>
                    try:
                        from tornado.testing import _TestMethodWrapper
                        if isinstance(test_method, _TestMethodWrapper):
                            test_method = test_method.orig_method
                    except (ImportError, AttributeError):
                        pass
                    # <---- Code which avoids the inspect tracebacks -------------------------------------------------
                    _, self.lineno = inspect.getsourcelines(test_method)
            finally:
                pass

            if self.showAll:
                self.stream.write('  ' + self.getDescription(test))
                self.stream.write(" ... ")
                self.stream.flush()
            # <---- Re-Implement startTest ---------------------------------------------------------------------------

            if self.buffer:
                # Let's override the values of self._stdXXX_buffer
                # We want a similar sys.stdXXX file like behaviour
                self._stderr_buffer = _DelegateIO(sys.__stderr__)
                self._stdout_buffer = _DelegateIO(sys.__stdout__)
                sys.stderr = self._stderr_buffer
                sys.stdout = self._stdout_buffer

        def stopTest(self, test):
            log.debug('<<<<< END <<<<<<< %s', test.id())
            # xmlrunner classes are NOT new-style classes
            return xmlrunner.result._XMLTestResult.stopTest(self, test)

    class XMLTestRunner(xmlrunner.runner.XMLTestRunner):
        def _make_result(self):
            return _XMLTestResult(
                self.stream,
                self.descriptions,
                self.verbosity,
                self.elapsed_times
            )

        def run(self, test):
            result = xmlrunner.runner.XMLTestRunner.run(self, test)
            self.stream.writeln('Finished generating XML reports')
            return result

except ImportError:
    HAS_XMLRUNNER = False

    class XMLTestRunner(object):
        '''
        This is a dumb class just so we don't break projects at import time
        '''
