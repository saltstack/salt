# Import salt libs
try:
    import integration
except ImportError:
    if __name__ == '__main__':
        import os
        import sys
        sys.path.insert(
            0, os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), '../../'
                )
            )
        )
    import integration


class SaltCloudTest(integration.ShellCase,
                    integration.ShellCaseCommonTestsMixIn):

    _call_binary_ = 'salt-cloud'


if __name__ == '__main__':
    from integration import run_testcase
    run_testcase(SaltCloudTest)
