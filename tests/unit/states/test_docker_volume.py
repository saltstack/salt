# -*- coding: utf-8 -*-
'''
Unit tests for the docker state
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    Mock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt Libs
import salt.modules.dockermod as docker_mod
import salt.states.docker_volume as docker_state


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DockerVolumeTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test docker_volume states
    '''
    def setup_loader_modules(self):
        return {
            docker_mod: {
                '__context__': {'docker.docker_version': ''}
            },
            docker_state: {
                '__opts__': {'test': False}
            }
        }

    def test_present(self):
        '''
        Test docker_volume.present
        '''
        volumes = []
        default_driver = 'dummy_default'

        def create_volume(name, driver=None, driver_opts=None):
            for v in volumes:
                # present should never try to add a conflicting
                # volume
                self.assertNotEqual(v['Name'], name)
            if driver is None:
                driver = default_driver
            new = {'Name': name, 'Driver': driver}
            volumes.append(new)
            return new

        def remove_volume(name):
            old_len = len(volumes)
            removed = [v for v in volumes if v['Name'] == name]
            # present should not have tried to remove a volume
            # that didn't exist
            self.assertEqual(1, len(removed))
            volumes.remove(removed[0])
            return removed[0]

        docker_create_volume = Mock(side_effect=create_volume)
        __salt__ = {
            'docker.create_volume': docker_create_volume,
            'docker.volumes': Mock(return_value={'Volumes': volumes}),
            'docker.remove_volume': Mock(side_effect=remove_volume)
        }
        with patch.dict(docker_state.__dict__, {'__salt__': __salt__}):
            ret = docker_state.present('volume_foo')
            docker_create_volume.assert_called_with('volume_foo',
                                                    driver=None,
                                                    driver_opts=None)
            self.assertEqual(
                {
                    'name': 'volume_foo',
                    'comment': '',
                    'changes': {
                        'created': {
                            'Driver': default_driver,
                            'Name': 'volume_foo',
                        },
                    },
                    'result': True,
                },
                ret)
            self.assertEqual(len(volumes), 1)
            self.assertEqual(volumes[0]['Name'], 'volume_foo')
            self.assertIs(volumes[0]['Driver'], default_driver)

            # run it again with the same arguments
            orig_volumes = [volumes[0].copy()]
            ret = docker_state.present('volume_foo')
            self.assertEqual(
                {
                    'name': 'volume_foo',
                    'comment': "Volume 'volume_foo' already exists.",
                    'changes': {},
                    'result': True,
                },
                ret)
            self.assertEqual(orig_volumes, volumes)

            # run it again with a different driver but don't force
            ret = docker_state.present('volume_foo', driver='local')
            self.assertEqual(
                {
                    'name': 'volume_foo',
                    'comment': ("Driver for existing volume 'volume_foo'"
                                " ('dummy_default') does not match specified"
                                " driver ('local') and force is False"),
                    'changes': {},
                    'result': False,
                },
                ret)
            self.assertEqual(orig_volumes, volumes)

            # run it again with a different driver and force
            ret = docker_state.present(
                'volume_foo', driver='local', force=True)
            self.assertEqual(
                {
                    'name': 'volume_foo',
                    'comment': "",
                    'changes': {
                        'removed': {
                            'Driver': default_driver,
                            'Name': 'volume_foo',
                        },
                        'created': {
                            'Driver': 'local',
                            'Name': 'volume_foo',
                        },
                    },
                    'result': True,
                },
                ret)
            mod_orig_volumes = [orig_volumes[0].copy()]
            mod_orig_volumes[0]['Driver'] = 'local'
            self.assertEqual(mod_orig_volumes, volumes)

    def test_present_with_another_driver(self):
        '''
        Test docker_volume.present
        '''
        docker_create_volume = Mock(return_value='created')
        docker_remove_volume = Mock(return_value='removed')
        __salt__ = {'docker.create_volume': docker_create_volume,
                    'docker.remove_volume': docker_remove_volume,
                    'docker.volumes': Mock(return_value={
                        'Volumes': [{'Name': 'volume_foo',
                                     'Driver': 'foo'}]}),
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.present(
                'volume_foo',
                driver='bar',
                force=True,
                )
        docker_remove_volume.assert_called_with('volume_foo')
        docker_create_volume.assert_called_with('volume_foo',
                                                  driver='bar',
                                                  driver_opts=None)
        self.assertEqual(ret, {'name': 'volume_foo',
                               'comment': '',
                               'changes': {'created': 'created',
                                           'removed': 'removed'},
                               'result': True})

    def test_present_wo_existing_volumes(self):
        '''
        Test docker_volume.present without existing volumes.
        '''
        docker_create_volume = Mock(return_value='created')
        docker_remove_volume = Mock(return_value='removed')
        __salt__ = {'docker.create_volume': docker_create_volume,
                    'docker.remove_volume': docker_remove_volume,
                    'docker.volumes': Mock(return_value={'Volumes': None}),
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.present(
                'volume_foo',
                driver='bar',
                force=True,
                )
        docker_create_volume.assert_called_with('volume_foo',
                                                  driver='bar',
                                                  driver_opts=None)
        self.assertEqual(ret, {'name': 'volume_foo',
                               'comment': '',
                               'changes': {'created': 'created'},
                               'result': True})

    def test_absent(self):
        '''
        Test docker_volume.absent
        '''
        docker_remove_volume = Mock(return_value='removed')
        __salt__ = {'docker.remove_volume': docker_remove_volume,
                    'docker.volumes': Mock(return_value={
                        'Volumes': [{'Name': 'volume_foo'}]}),
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.absent(
                'volume_foo',
                )
        docker_remove_volume.assert_called_with('volume_foo')
        self.assertEqual(ret, {'name': 'volume_foo',
                               'comment': '',
                               'changes': {'removed': 'removed'},
                               'result': True})
