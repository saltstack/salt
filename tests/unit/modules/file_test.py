# Import python libs
import os
import tempfile
import textwrap

# Import Salt Testing libs
from salttesting import TestCase
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

# Import Salt libs
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


class FileReplaceTestCase(TestCase):
    MULTILINE_STRING = textwrap.dedent('''\
        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nam rhoncus
        enim ac bibendum vulputate. Etiam nibh velit, placerat ac auctor in,
        lacinia a turpis. Nulla elit elit, ornare in sodales eu, aliquam sit
        amet nisl.

        Fusce ac vehicula lectus. Vivamus justo nunc, pulvinar in ornare nec,
        sollicitudin id sem. Pellentesque sed ipsum dapibus, dapibus elit id,
        malesuada nisi.

        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Donec
        venenatis tellus eget massa facilisis, in auctor ante aliquet. Sed nec
        cursus metus. Curabitur massa urna, vehicula id porttitor sed, lobortis
        quis leo.
        ''')

    def setUp(self):
        self.tfile = tempfile.NamedTemporaryFile(delete=False)
        self.tfile.write(self.MULTILINE_STRING)
        self.tfile.close()

    def tearDown(self):
        os.remove(self.tfile.name)

    def test_replace(self):
        filemod.replace(self.tfile.name, r'Etiam', 'Salticus', backup=False)

        with open(self.tfile.name, 'rb') as fp:
            self.assertIn('Salticus', fp.read())

    def test_backup(self):
        fext = '.bak'
        bak_file = '{0}{1}'.format(self.tfile.name, fext)

        filemod.replace(self.tfile.name, r'Etiam', 'Salticus', backup=fext)

        self.assertTrue(os.path.exists(bak_file))
        os.unlink(bak_file)

    def test_nobackup(self):
        fext = '.bak'
        bak_file = '{0}{1}'.format(self.tfile.name, fext)

        filemod.replace(self.tfile.name, r'Etiam', 'Salticus', backup=False)

        self.assertFalse(os.path.exists(bak_file))

    def test_dry_run(self):
        before_ctime = os.stat(self.tfile.name).st_mtime
        filemod.replace(self.tfile.name, r'Etiam', 'Salticus', dry_run=True)
        after_ctime = os.stat(self.tfile.name).st_mtime

        self.assertEqual(before_ctime, after_ctime)

    def test_show_changes(self):
        ret = filemod.replace(self.tfile.name, r'Etiam', 'Salticus',
                show_changes=True)

        self.assertTrue(ret.startswith('---')) # looks like a diff

    def test_noshow_changes(self):
        ret = filemod.replace(self.tfile.name, r'Etiam', 'Salticus',
                show_changes=False)

        self.assertIsInstance(ret, bool)

    def test_re_str_flags(self):
        # upper- & lower-case
        filemod.replace(self.tfile.name, r'Etiam', 'Salticus',
                flags=['MULTILINE', 'ignorecase'])

    def test_re_int_flags(self):
        filemod.replace(self.tfile.name, r'Etiam', 'Salticus', flags=10)


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
                self.assertEqual(
                    SED_CONTENT.replace(before, ''),
                    newfile.read()
                )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(FileModuleTestCase, needs_daemon=False)
