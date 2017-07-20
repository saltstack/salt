# -*- coding: utf-8 -*-

'''
For use with OpenEmbedded ptest.
Based on the API in Python's TextTestRunner.
'''

# Import Python libs
from __future__ import absolute_import, print_function
import sys

# Import tests support libs
from tests.support.unit import TestResult


class _WritelnWrapper(object):
    '''
    Wrapper that adds a 'writeln' method to a passed in file object.

    Used by PTestRunner.
    '''
    def __init__(self, stream):
        self.stream = stream

    def __getattr__(self, attr):
        if attr in ('stream', '__getstate__'):
            raise AttributeError(attr)
        return getattr(self.stream, attr)

    def writeln(self, arg=None):
        '''
        Wrapper 'writeln' method.
        '''
        if arg:
            self.write(arg)
        # text-mode streams translate to \r\n if needed
        self.write('\n')


class _PTestResult(TestResult):
    '''
    A test result class that can print formatted text results to a stream.
    Function names based on TextTestResult which are camelCase.

    Used by PTestRunner.
    '''
    def __init__(self, stream, descriptions, verbosity):  # pylint: disable=unused-argument
        TestResult.__init__(self)
        self.stream = stream
        self.descriptions = descriptions

    def getDescription(self, test):  # pylint: disable=invalid-name,no-self-use
        return str(test)

    def startTest(self, test):  # pylint: disable=invalid-name
        TestResult.startTest(self, test)

    def addSuccess(self, test):  # pylint: disable=invalid-name
        TestResult.addSuccess(self, test)
        self.stream.writeln('PASS: {0}'.format(self.getDescription(test)))

    def addError(self, test, err):  # pylint: disable=invalid-name
        TestResult.addError(self, test, err)
        self.stream.writeln('FAIL: {0}'.format(self.getDescription(test)))
        self.stream.writeln('{0}'.format(err))

    def addFailure(self, test, err):  # pylint: disable=invalid-name
        TestResult.addFailure(self, test, err)
        self.stream.writeln('FAIL: {0}'.format(self.getDescription(test)))
        self.stream.writeln('{0}'.format(err))

    def addSkip(self, test, reason):  # pylint: disable=invalid-name
        TestResult.addSkip(self, test, reason)
        self.stream.writeln('SKIP: {0}'.format(self.getDescription(test)))
        self.stream.writeln('{0}'.format(reason))


class PTestRunner(object):
    '''
    A test runner class that displays results in OpenEmbedded ptest format.
    '''
    def __init__(self, stream=sys.stderr, descriptions=1, verbosity=1):
        self.stream = _WritelnWrapper(stream)
        self.descriptions = descriptions
        self.verbosity = verbosity

    def _make_result(self):
        return _PTestResult(self.stream, self.descriptions, self.verbosity)

    def run(self, test):
        '''
        Run the given test case or test suite.
        '''
        result = self._make_result()
        test(result)
        return result
