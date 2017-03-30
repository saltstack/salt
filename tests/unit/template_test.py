# -*- coding: utf-8 -*-
'''
    :codeauthor: :email: `Mike Place <mp@saltstack.com>`
'''

# Import Python libs
from __future__ import absolute_import

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock

ensure_in_syspath('../')

# Import Salt libs
from salt import template


class TemplateTestCase(TestCase):

    render_dict = {'jinja': 'fake_jinja_func',
               'json': 'fake_json_func',
               'mako': 'fake_make_func'}

    def test_compile_template_bad_type(self):
        '''
        Test to ensure that unsupported types cannot be passed to the template compiler
        '''
        ret = template.compile_template(['1', '2', '3'], None, None, None, None)
        self.assertDictEqual(ret, {})

    @skipIf(NO_MOCK, NO_MOCK_REASON)
    def test_compile_template_preserves_windows_newlines(self):
        '''
        Test to ensure that unsupported types cannot be passed to the template compiler
        '''
        input_data_windows = 'foo\r\nbar\r\nbaz\r\n'
        input_data_non_windows = input_data_windows.replace('\r\n', '\n')
        renderer = 'test'
        rend = {renderer: MagicMock(return_value=input_data_non_windows)}
        blacklist = whitelist = []

        ret = template.compile_template(
            ':string:',
            rend,
            renderer,
            blacklist,
            whitelist,
            input_data=input_data_windows)
        # Even though the mocked renderer returned a string without the windows
        # newlines, the compiled template should still have them.
        self.assertEqual(ret, input_data_windows)

        # Now test that we aren't adding them in unnecessarily.
        ret = template.compile_template(
            ':string:',
            rend,
            renderer,
            blacklist,
            whitelist,
            input_data=input_data_non_windows)
        self.assertEqual(ret, input_data_non_windows)

        # Finally, ensure that we're not unnecessarily replacing the \n with
        # \r\n in the event that the renderer returned a string with the
        # windows newlines intact.
        rend[renderer] = MagicMock(return_value=input_data_windows)
        ret = template.compile_template(
            ':string:',
            rend,
            renderer,
            blacklist,
            whitelist,
            input_data=input_data_windows)
        self.assertEqual(ret, input_data_windows)

    def test_check_render_pipe_str(self):
        '''
        Check that all renderers specified in the pipe string are available.
        '''
        ret = template.check_render_pipe_str('jinja|json', self.render_dict, None, None)
        self.assertIn(('fake_jinja_func', ''), ret)
        self.assertIn(('fake_json_func', ''), ret)
        self.assertNotIn(('OBVIOUSLY_NOT_HERE', ''), ret)

    def test_check_renderer_blacklisting(self):
        '''
        Check that all renderers specified in the pipe string are available.
        '''
        ret = template.check_render_pipe_str('jinja|json', self.render_dict, ['jinja'], None)
        self.assertListEqual([('fake_json_func', '')], ret)
        ret = template.check_render_pipe_str('jinja|json', self.render_dict, None, ['jinja'])
        self.assertListEqual([('fake_jinja_func', '')], ret)
        ret = template.check_render_pipe_str('jinja|json', self.render_dict, ['jinja'], ['jinja'])
        self.assertListEqual([], ret)
        ret = template.check_render_pipe_str('jinja|json', self.render_dict, ['jinja'], ['jinja', 'json'])
        self.assertListEqual([('fake_json_func', '')], ret)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(TemplateTestCase, needs_daemon=False)
