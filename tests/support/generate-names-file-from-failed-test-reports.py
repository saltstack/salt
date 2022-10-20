"""
    tests.support.generate-from-names-from-failed-test-reports
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This script is meant as a stop-gap until we move to PyTest to provide a functionality similar to
    PyTest's --last-failed where PyTest only runs last failed tests.
"""
# pylint: disable=resource-leakage

import argparse
import glob
import os
import sys

try:
    import xunitparser
except ImportError:
    sys.stderr.write(
        "Please install the xunitparser python package to run this script\n"
    )
    sys.stderr.flush()
    sys.exit(1)

REPO_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reports-dir",
        default=os.path.join(REPO_ROOT, "artifacts", "xml-unittests-output"),
        help="Path to the directory where the JUnit XML reports can be found",
    )
    parser.add_argument(
        "output_file",
        help=(
            "Path to the file containing the failed tests listing to be fed to"
            " --names-files"
        ),
    )
    options = parser.parse_args()
    total_xml_reports = 0
    failures = set()
    for fname in sorted(glob.glob(os.path.join(options.reports_dir, "*.xml"))):
        total_xml_reports += 1
        with open(fname) as rfh:
            test_suite, test_result = xunitparser.parse(rfh)
            if not test_result.errors and not test_result.failures:
                continue
            for test in test_suite:
                if test.bad:
                    failures.add("{classname}.{methodname}".format(**test.__dict__))

    if not total_xml_reports:
        parser.exit(status=1, message="No JUnit XML files were parsed")

    with open(options.output_file, "w") as wfh:
        wfh.write(os.linesep.join(sorted(failures)))

    parser.exit(status=0)


if __name__ == "__main__":
    main()
