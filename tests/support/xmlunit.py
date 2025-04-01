"""
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)
    :copyright: Copyright 2014 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    tests.support.xmlunit
    ~~~~~~~~~~~~~~~~~~~

    XML Unit Tests
"""

# pylint: disable=wrong-import-order,wrong-import-position


import io
import logging

log = logging.getLogger(__name__)


try:
    import xmlrunner.result
    import xmlrunner.runner

    HAS_XMLRUNNER = True

    class _DuplicateWriter(io.TextIOBase):
        """
        Duplicate output from the first handle to the second handle
        The second handle is expected to be a StringIO and not to block.
        """

        def __init__(self, first, second):
            super().__init__()
            self._first = first
            self._second = second

        def flush(self):
            self._first.flush()
            self._second.flush()

        def writable(self):
            return True

        def writelines(self, lines):
            self._first.writelines(lines)
            self._second.writelines(lines)

        def write(self, b):
            if isinstance(self._first, io.TextIOBase):
                wrote = self._first.write(b)

                if wrote is not None:
                    # expected to always succeed to write
                    self._second.write(b[:wrote])

                return wrote
            else:
                # file-like object in Python2
                # It doesn't return wrote bytes.
                self._first.write(b)
                self._second.write(b)
                return len(b)

        def fileno(self):
            return self._first.fileno()

    xmlrunner.result._DuplicateWriter = _DuplicateWriter

    class _XMLTestResult(xmlrunner.result._XMLTestResult):
        def startTest(self, test):
            log.debug(">>>>> START >>>>> %s", test.id())
            # xmlrunner classes are NOT new-style classes
            xmlrunner.result._XMLTestResult.startTest(self, test)

        def stopTest(self, test):
            log.debug("<<<<< END <<<<<<< %s", test.id())
            # xmlrunner classes are NOT new-style classes
            return xmlrunner.result._XMLTestResult.stopTest(self, test)

    class XMLTestRunner(xmlrunner.runner.XMLTestRunner):
        def _make_result(self):
            return _XMLTestResult(
                self.stream, self.descriptions, self.verbosity, self.elapsed_times
            )

        def run(self, test):
            result = xmlrunner.runner.XMLTestRunner.run(self, test)
            self.stream.writeln("Finished generating XML reports")
            return result

except ImportError:
    HAS_XMLRUNNER = False

    class XMLTestRunner:
        """
        This is a dumb class just so we don't break projects at import time
        """
