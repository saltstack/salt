# Import python libs
import os
import shutil
import integration


class StateModuleTest(integration.ModuleCase):
    '''
    Validate the test module
    '''

    maxDiff = None

    def test_show_highstate(self):
        '''
        state.show_highstate
        '''
        high = self.run_function('state.show_highstate')
        self.assertTrue(isinstance(high, dict))
        self.assertTrue('/testfile' in high)
        self.assertEqual(high['/testfile']['__env__'], 'base')

    def test_show_lowstate(self):
        '''
        state.show_lowstate
        '''
        low = self.run_function('state.show_lowstate')
        self.assertTrue(isinstance(low, list))
        self.assertTrue(isinstance(low[0], dict))

    def test_catch_recurse(self):
        '''
        state.show_sls used to catch a recursive ref
        '''
        err = self.run_function('state.sls', mods='recurse_fail')
        self.assertIn('recursive', err[0])

    def test_no_recurse(self):
        '''
        verify that a sls structure is NOT a recursive ref
        '''
        sls = self.run_function('state.show_sls', mods='recurse_ok')
        self.assertIn('snmpd', sls)

    def test_no_recurse_two(self):
        '''
        verify that a sls structure is NOT a recursive ref
        '''
        sls = self.run_function('state.show_sls', mods='recurse_ok_two')
        self.assertIn('/etc/nagios/nrpe.cfg', sls)

    def test_issue_1896_file_append_source(self):
        '''
        Verify that we can append a file's contents
        '''
        self.run_function('state.sls', mods='testappend')
        self.run_function('state.sls', mods='testappend.step-1')
        self.run_function('state.sls', mods='testappend.step-2')
        self.assertMultiLineEqual('''\
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

# enable bash completion in interactive shells
if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
    . /etc/bash_completion
fi

''', open('/tmp/salttest/test.append', 'r').read())

        # Re-append switching order
        self.run_function('state.sls', mods='testappend.step-2')
        self.run_function('state.sls', mods='testappend.step-1')
        self.assertMultiLineEqual('''\
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

# enable bash completion in interactive shells
if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
    . /etc/bash_completion
fi

''', open('/tmp/salttest/test.append', 'r').read())

    def test_issue_1876_syntax_error(self):
        '''
        verify that we catch the following syntax error::

            /tmp/salttest/issue-1876:

              file:
                - managed
                - source: salt://testfile

              file.append:
                - text: foo

        '''
        sls = self.run_function('state.sls', mods='issue-1876')
        self.assertIn(
            'Name "/tmp/salttest/issue-1876" in sls "issue-1876" contains '
            'multiple state decs of the same type', sls
        )

    def test_issue_1879_too_simple_contains_check(self):
        contents = '''\
# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "$debian_chroot" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

# enable bash completion in interactive shells
if [ -f /etc/bash_completion ] && ! shopt -oq posix; then
    . /etc/bash_completion
fi

'''
        # Create the file
        self.run_function('state.sls', mods='issue-1879')
        # The first append
        self.run_function('state.sls', mods='issue-1879.step-1')
        # The seccond append
        self.run_function('state.sls', mods='issue-1879.step-2')
        # Does it match?
        try:
            self.assertMultiLineEqual(
                contents, open('/tmp/salttest/issue-1879', 'r').read()
            )
            # Make sure we don't re-append existing text
            self.run_function('state.sls', mods='issue-1879.step-1')
            self.run_function('state.sls', mods='issue-1879.step-2')
            self.assertMultiLineEqual(
                contents, open('/tmp/salttest/issue-1879', 'r').read()
            )
        except Exception:
            shutil.copy('/tmp/salttest/issue-1879', '/tmp/salttest/issue-1879.bak')
            raise
        finally:
            os.unlink('/tmp/salttest/issue-1879')

    def test_include(self):
        fnames = ('/tmp/include-test', '/tmp/to-include-test')
        try:
            ret = self.run_function('state.sls', mods='include-test')
            for part in ret.itervalues():
                self.assertTrue(part['result'])
            for fname in fnames:
                self.assertTrue(os.path.isfile(fname))
            self.assertFalse(os.path.isfile('/tmp/exclude-test'))
        finally:
            for fname in list(fnames) + ['/tmp/exclude-test']:
                if os.path.isfile(fname):
                    os.remove(fname)

    def test_exclude(self):
        fnames = ('/tmp/include-test', '/tmp/exclude-test')
        try:
            ret = self.run_function('state.sls', mods='exclude-test')
            for part in ret.itervalues():
                self.assertTrue(part['result'])
            for fname in fnames:
                self.assertTrue(os.path.isfile(fname))
            self.assertFalse(os.path.isfile('/tmp/to-include-test'))
        finally:
            for fname in list(fnames) + ['/tmp/to-include-test']:
                if os.path.isfile(fname):
                    os.remove(fname)

    def test_issue_2068_template_str(self):
        venv_dir = '/tmp/issue-2068-template-str'

        try:
            ret = self.run_function(
                'state.sls', mods='issue-2068-template-str-no-dot'
            )
            self.assertTrue(isinstance(ret, dict))
            self.assertNotEqual(ret, {})
            for part in ret.itervalues():
                self.assertTrue(part['result'])
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

        # Let's load the template from the filesystem. If running this state
        # with state.sls works, so should using state.template_str
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'files', 'file', 'base', 'issue-2068-template-str-no-dot.sls'
        )

        template = open(template_path, 'r').read()
        try:
            ret = self.run_function('state.template_str', [template])

            self.assertTrue(isinstance(ret, dict)), ret
            self.assertNotEqual(ret, {})

            for key in ret.iterkeys():
                self.assertTrue(ret[key]['result'])

            self.assertTrue(
                os.path.isfile(os.path.join(venv_dir, 'bin', 'pep8'))
            )
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

        # Now using state.template
        try:
            ret = self.run_function('state.template', [template_path])
            self.assertTrue(isinstance(ret, dict))
            self.assertNotEqual(ret, {})
            for part in ret.itervalues():
                self.assertTrue(part['result'])
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

        # Now the problematic #2068 including dot's
        try:
            ret = self.run_function(
                'state.sls', mods='issue-2068-template-str'
            )
            self.assertTrue(isinstance(ret, dict))
            self.assertNotEqual(ret, {})
            for part in ret.itervalues():
                self.assertTrue(part['result'])
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

        # Let's load the template from the filesystem. If running this state
        # with state.sls works, so should using state.template_str
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'files', 'file', 'base', 'issue-2068-template-str.sls'
        )

        template = open(template_path, 'r').read()
        try:
            ret = self.run_function('state.template_str', [template])

            self.assertTrue(isinstance(ret, dict)), ret
            self.assertNotEqual(ret, {})

            for key in ret.iterkeys():
                self.assertTrue(ret[key]['result'])

            self.assertTrue(
                os.path.isfile(os.path.join(venv_dir, 'bin', 'pep8'))
            )
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

        # Now using state.template
        try:
            ret = self.run_function('state.template', [template_path])
            self.assertTrue(isinstance(ret, dict))
            self.assertNotEqual(ret, {})
            for part in ret.itervalues():
                self.assertTrue(part['result'])
        finally:
            if os.path.isdir(venv_dir):
                shutil.rmtree(venv_dir)

    def test_template_invalid_items(self):
        TEMPLATE = '''\
{0}:
  - issue-2068-template-str

/tmp/test-template-invalid-items:
  file:
    - managed
    - source: salt://testfile
'''
        for item in ('include', 'exclude', 'extends'):
            ret = self.run_function(
                'state.template_str', [TEMPLATE.format(item)]
            )
            self.assertTrue(isinstance(ret, list))
            self.assertNotEqual(ret, [])
            self.assertEqual(
                ['The \'{0}\' declaration found on \'<template-str>\' is '
                 'invalid when rendering single templates'.format(item)],
                ret
            )


if __name__ == '__main__':
    from integration import run_tests
    run_tests(StateModuleTest)
