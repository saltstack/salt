# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
import textwrap
import os
import json
# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')

# Import salt libs
import integration
import salt.version
from salt import config

STATE_DIR = os.path.join(integration.FILES, 'file', 'base')

class TestModuleDockereng(integration.ModuleCase,
                     integration.AdaptedConfigurationTestCaseMixIn):

    '''
    Validate the test module
    '''

    def setUp(self):
        self.state_name = 'docker_top'
    	state_filename = self.state_name + '.sls'
    	self.state_file = os.path.join(STATE_DIR, state_filename)
        with salt.utils.fopen(self.state_file, 'w') as fb_:
            fb_.write(textwrap.dedent('''
                foo:
                  dockerng.running:
                    - image: ubuntu
                    - detach: True
                    - command: bash
                    - interactive: True
                    - environment:
                      - VAR1: value1
                      - VAR2: value2
                      - VAR3: value3
                        '''))
        self.run_function('state.sls', [self.state_name])
        super(TestModuleDockereng, self).setUp()

    def tearDown(self):
        '''
        remove files created in previous tests
        '''
        try:
            os.remove(self.state_file)
        except OSError:
            pass
        self.run_function('cmd.run',['docker kill foo'])

    def test_docker_env(self):
    	'''
    	dockerng.running environnment part.
        '''
        with salt.utils.fopen(self.state_file, 'w') as fb_:
            fb_.write(textwrap.dedent('''
                foo:
                  dockerng.running:
                    - image: ubuntu
                    - detach: True
                    - command: bash
                    - interactive: True
                    - environment:
                      - VAR1: value1
                      #- VAR2: value2
                      - VAR3: value3
                        '''))
        ret = self.run_function('state.sls', [self.state_name])
        self.assertEqual(ret['dockerng_|-foo_|-foo_|-running']['comment'],'Container \'foo\' was replaced')
        self.assertEqual(ret['dockerng_|-foo_|-foo_|-running']['changes']['diff']['environment']['old']['VAR2'],'value2')
        ret = self.run_function('cmd.run',['docker inspect foo'])
        container_json_data = json.loads(ret)
        container_data = container_json_data[0]
        self.assertIn('VAR1=value1',container_data['Config']['Env'])
        self.assertIn('VAR3=value3',container_data['Config']['Env'])
        self.assertNotIn('VAR2=value2',container_data['Config']['Env'])

        # Running same state to make sure that container should not get restarted every time
        ret = self.run_function('state.sls', [self.state_name])
        self.assertEqual(ret['dockerng_|-foo_|-foo_|-running']['comment'],'Container \'foo\' is already configured as specified')

if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestModuleDockereng)
