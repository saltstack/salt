# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Nicole Thomas <nicole@saltstack.com>`
'''

# Import Salt Libs
from salt.output import grains

# Import Salt Testing Libs
from salttesting import TestCase
from salttesting.mock import patch
from salttesting.helpers import ensure_in_syspath

ensure_in_syspath('../../')

grains.__opts__ = {}
colors = {'LIGHT_GREEN': '\x1b[1;32m',
          'ENDC': '\x1b[0m',
          'CYAN': '\x1b[0;36m',
          'GREEN': '\x1b[0;32m'}


class GrainsTestCase(TestCase):
    '''
    TestCase for salt.output.grains module
    '''

    def test_output_unicode(self):
        '''
        Tests grains output when using unicode characters like ®
        '''
        test_grains = {'locale_info': {'defaultencoding': 'unknown'},
                       'test': {'bad_string': 'Windows®'}}
        ret = u'\x1b[0;32mtest\x1b[0m:\n  \x1b' \
              u'[0;36mbad_string\x1b[0m: \x1b[1;32mWindows\xae\x1b' \
              u'[0m\n\x1b[0;32mlocale_info\x1b[0m:\n  \x1b' \
              u'[0;36mdefaultencoding\x1b[0m: \x1b[1;32munknown\x1b[0m\n'
        with patch.dict(grains.__opts__, {'color': colors}):
            self.assertEqual(grains.output(test_grains), ret)


if __name__ == '__main__':
    from integration import run_tests
    run_tests(GrainsTestCase, needs_daemon=False)
