# -*- coding: utf-8 -*-
'''
Tests for integration with Docker's Python library

:codeauthor: :email:`C. R. Oldham <cr@saltstack.com>`
'''

# Import python libs
from __future__ import absolute_import
import os
import string
import logging

# Import Salt Testing libs
from salttesting.helpers import ensure_in_syspath, requires_salt_modules
from salttesting import skipIf
ensure_in_syspath('../../')

# Import salt libs
import integration

log = logging.getLogger(__name__)


@requires_salt_modules('docker')
class DockerTest(integration.ModuleCase):
    '''
    Test docker integration
    '''

    def _get_container_id(self, image_name=None):
        cmdstring = 'docker ps | grep {0}'.format(image_name)
        ret_cmdrun = self.run_function('cmd.run_all', cmd=cmdstring)
        ids = []
        for l in ret_cmdrun['stdout'].splitlines():
            try:
                ids.append(string.split(ret_cmdrun['stdout'])[0])
            except IndexError:
                pass
        return ids

    def test_version(self):
        '''
        dockerio.version
        '''
        ret = self.run_function('docker.version')
        ret_cmdrun = self.run_function('cmd.run_all', cmd='docker version | grep "Client version:"')
        self.assertEqual('Client version: {0}'.format(ret['out']['Version']), ret_cmdrun['stdout'])

    def test_build(self):
        '''
        dockerio.build

        Long timeout here because build will transfer many images from the Internet
        before actually creating the final container
        '''
        dockerfile_path = os.path.join(integration.INTEGRATION_TEST_DIR, 'files/file/base/')
        ret = self.run_function('docker.build', timeout=300, path=dockerfile_path, tag='testsuite_image')
        self.assertTrue(ret['status'], 'Image built')

    def test_images(self):
        '''
        dockerio.get_images
        '''
        ret = self.run_function('docker.get_images')
        foundit = False
        for i in ret['out']:
            try:
                if i['RepoTags'][0] == 'testsuite_image:latest':
                    foundit = True
                    break
            except KeyError:
                pass
        self.assertTrue(foundit, 'Could not find created image.')

    def test_create_container(self):
        '''
        dockerio.create_container
        '''

        ret = self.run_function('docker.create_container', image='testsuite_image', command='echo ping')
        self.assertTrue(ret['status'], 'Container was not created')

    @skipIf(True, "Currently broken")
    def test_stop(self):
        '''
        dockerio.stop
        '''

        container_id = self._get_container_id(image_name='testsuite_image')
        self.assertTrue(container_id, 'test_stop: found no containers running')
        for i in container_id:
            ret = self.run_function('docker.stop', i)
            self.assertFalse(self.run_function('docker.is_running', i))

    @skipIf(True, "Currently broken")
    def test_run_stdout(self):
        '''
        dockerio.run_stdout

        The testsuite Dockerfile creates a file in the image's /tmp folder called 'cheese'
        The Dockerfile is in salt/tests/integration/files/file/base/Dockerfile

        '''

        run_ret = self.run_function('docker.create_container', image='testsuite_image')
        base_container_id = run_ret['id']
        ret = self.run_function('docker.run_stdout', container=base_container_id, cmd="cat /tmp/cheese")
        run_container_id = ret['id']
        self.assertEqual(ret['out'], 'The cheese shop is open')
        self.run_function('docker.stop', base_container_id)
        self.run_function('docker.stop', run_container_id)
        self.assertFalse(self.run_function('docker.is_running', base_container_id))
        self.assertFalse(self.run_function('docker.is_running', run_container_id))

    @skipIf(True, "Currently broken")
    def test_commit(self):
        '''
        dockerio.commit
        '''

        run_ret = self.run_function('docker.create_container', image='testsuite_image')
        log.debug("first container: {0}".format(run_ret))
        base_container_id = run_ret['id']
        ret = self.run_function('docker.run_stdout', container=base_container_id, cmd='echo "The cheese shop is now closed." > /tmp/deadcheese')
        log.debug("second container: {0}".format(ret))
        run_container_id = ret['id']
        commit_ret = self.run_function('docker.commit', container=base_container_id, repository='testsuite_committed_img', message='This image was created by the testsuite')
        log.debug("post-commit: {0}".format(commit_ret))
        self.run_function('docker.stop', run_container_id)
        new_container = self.run_function('docker.create_container', image='testsuite_committed_img')
        final_ret = self.run_function('docker.run_stdout', container=new_container['id'], cmd='cat /tmp/cheese')
        self.assertEqual(final_ret['out'], 'The cheese shop is now closed.')


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DockerTest)
