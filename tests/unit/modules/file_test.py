import tempfile

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
from salt.modules import file as filemod
from salt.modules import cmdmod

# Import Salt Testing libs
from salttesting import TestCase

filemod.__salt__ = {
    'cmd.run': cmdmod.run,
    'cmd.run_all': cmdmod.run_all
}

SED_CONTENT = """test
some
content
/var/lib/foo/app/test
here
"""


class FileModuleTestCase(TestCase):
    def test_sed_limit_escaped(self):
        with tempfile.NamedTemporaryFile() as tfile:
            tfile.write(SED_CONTENT)
            tfile.seek(0, 0)

            path = tfile.name
            before = '/var/lib/foo'
            after = ''
            limit = '^{0}'.format(before)

            filemod.sed(path, before, after, limit=limit)

            with open(path, 'rb') as newfile:
                self.assertEquals(
                    SED_CONTENT.replace(before, ''),
                    newfile.read()
                )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(FileModuleTestCase, needs_daemon=False)
