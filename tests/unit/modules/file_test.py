import tempfile

from saltunittest import TestCase, TestLoader, TextTestRunner

from salt.modules import file as filemod
from salt.modules import cmdmod

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


if __name__ == "__main__":
    loader = TestLoader()
    tests = loader.loadTestsFromTestCase(FileModuleTestCase)
    TextTestRunner(verbosity=1).run(tests)
