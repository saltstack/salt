# -tests/integration/daemons/test_masterapi.py:71*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil
import stat

# Import Salt Testing libs
from tests.support.runtests import RUNTIME_VARS
from tests.support.case import ShellCase

# Import 3rd-party libs

# Import Salt libs
import salt.utils.files
import salt.utils.stringutils


class AutosignGrainsTest(ShellCase):
    '''
    Test autosigning minions based on grain values.
    '''

    def setUp(self):
        # all read, only owner write
        self.autosign_file_permissions = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IWUSR
        if RUNTIME_VARS.PYTEST_SESSION:
            self.autosign_file_path = os.path.join(RUNTIME_VARS.TMP, 'autosign_file')
        else:
            self.autosign_file_path = os.path.join(RUNTIME_VARS.TMP, 'rootdir', 'autosign_file')
        shutil.copyfile(
            os.path.join(RUNTIME_VARS.FILES, 'autosign_grains', 'autosign_file'),
            self.autosign_file_path
        )
        os.chmod(self.autosign_file_path, self.autosign_file_permissions)

        self.run_key('-d minion -y')
        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again

        if 'minion' in self.run_key('-l acc'):
            self.tearDown()
            self.skipTest('Could not deauthorize minion')
        if 'minion' not in self.run_key('-l un'):
            self.tearDown()
            self.skipTest('minion did not try to reauthenticate itself')

        self.autosign_grains_dir = os.path.join(self.master_opts['autosign_grains_dir'])
        if not os.path.isdir(self.autosign_grains_dir):
            os.makedirs(self.autosign_grains_dir)

    def tearDown(self):
        shutil.copyfile(
            os.path.join(RUNTIME_VARS.FILES, 'autosign_file'),
            self.autosign_file_path
        )
        os.chmod(self.autosign_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to authenticate itself again

        try:
            if os.path.isdir(self.autosign_grains_dir):
                shutil.rmtree(self.autosign_grains_dir)
        except AttributeError:
            pass

    def test_autosign_grains_accept(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'test_grain')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('#invalid_value\ncheese'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertIn('minion', self.run_key('-l acc'))

    def test_autosign_grains_fail(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'test_grain')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('#cheese\ninvalid_value'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))

    def test_autosign_grains_nested_dict_accept(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_dict1:nested_dict1_0')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_dict1'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertIn('minion', self.run_key('-l acc'))

    def test_autosign_grains_nested_dict_fail_wrongvalue(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_dict1:nested_dict1_0')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('invalid_value_dict1'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))

    def test_autosign_grains_nested_dict_fail_wrongkey(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_dict1:fake')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_dict1'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))

    def test_autosign_grains_nested_list_accept(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_list1:0')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_list1'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertIn('minion', self.run_key('-l acc'))
    
    def test_autosign_grains_nested_list_fail_wrongvalue(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_list1:0')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('fake'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))

    def test_autosign_grains_nested_list_fail_wrongindex(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_list1:1')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_list0'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))

    def test_autosign_grains_nested_dict_in_list_accept(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_list2:1:nested_dict_lvl2')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_list2'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertIn('minion', self.run_key('-l acc'))

    def test_autosign_grains_nested_dict_in_list_fail_wrongvalue(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_list2:1:nested_dict_lvl2')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('fake'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))
    
    def test_autosign_grains_nested_dict_in_list_fail_wrongindex(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_list2:0:nested_dict_lvl2')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_dict3'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))

    def test_autosign_grains_nested_dict_in_list_fail_wrongkey(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_list2:1:fake')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_dict3'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))
    
    def test_autosign_grains_nested_list_in_dict_accept(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_dict2:nested_dict2_1:1')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_dict2'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertIn('minion', self.run_key('-l acc'))

    def test_autosign_grains_nested_list_in_dict_fail_wrongvalue(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_dict2:nested_dict2_1:1')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('fake'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))
    
    def test_autosign_grains_nested_list_in_dict_fail_wrongindex(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_dict2:nested_dict2_1:0')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_nested_dict2_2'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))

    def test_autosign_grains_nested_list_in_dict_fail_wrongkey(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_dict2:nested_dict2_0:0')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_dict3'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))

    def test_autosign_grains_nested_list_in_list_accept(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_list3:1:1')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_list3'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertIn('minion', self.run_key('-l acc'))

    def test_autosign_grains_nested_list_in_list_fail_wrongvalue(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_list3:1:1')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('fake'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))
    
    def test_autosign_grains_nested_list_in_list_fail_wrongindex(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_list3:1:0')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('nested_list3_1_1'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))

    def test_autosign_grains_nested_dict_in_dict_accept(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_dict2:nested_dict2_2:nested_dict2_2_0')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_dict2'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertIn('minion', self.run_key('-l acc'))

    def test_autosign_grains_nested_dict_in_dict_fail_wrongvalue(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_dict2:nested_dict2_2:nested_dict2_2_0')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('fake'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))
    
    def test_autosign_grains_nested_dict_in_dict_fail_wrongkey(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_dict2:nested_dict2_2:fake')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_dict2'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertNotIn('minion', self.run_key('-l acc'))
        self.assertIn('minion', self.run_key('-l un'))

    def test_autosign_grains_nested_complex_accept(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_list3:2:1:nested_list3_2_0')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_list3'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertIn('minion', self.run_key('-l acc'))

    def test_autosign_grains_nested_complex2_accept(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'nested_dict2:nested_dict2_1:2:nested_dict2_1_0')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('valid_value_dict2'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertIn('minion', self.run_key('-l acc'))
    
    def test_autosign_grains_key_with_columns(self):
        grain_file_path = os.path.join(self.autosign_grains_dir, 'file:with:columns')
        with salt.utils.files.fopen(grain_file_path, 'w') as f:
            f.write(salt.utils.stringutils.to_str('value_value_columns_key'))
        os.chmod(grain_file_path, self.autosign_file_permissions)

        self.run_call('test.ping -l quiet')  # get minon to try to authenticate itself again
        self.assertIn('minion', self.run_key('-l acc'))