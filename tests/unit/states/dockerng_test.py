# -*- coding: utf-8 -*-
'''
Unit tests for the dockerng state
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    Mock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

ensure_in_syspath('../../')

# Import Salt Libs
from salt.exceptions import CommandExecutionError
from salt.modules import dockerng as dockerng_mod
from salt.states import dockerng as dockerng_state

dockerng_mod.__context__ = {'docker.docker_version': ''}
dockerng_mod.__salt__ = {}
dockerng_state.__context__ = {}
dockerng_state.__opts__ = {'test': False}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DockerngTestCase(TestCase):
    '''
    Validate dockerng state
    '''

    def test_running_with_no_predifined_volume(self):
        '''
        Test dockerng.running function with an image
        that doens't have VOLUME defined.

        The ``binds`` argument, should create a container
        with respective volumes extracted from ``binds``.
        '''
        dockerng_create = Mock()
        dockerng_start = Mock()
        dockerng_history = MagicMock(return_value=[])
        __salt__ = {'dockerng.list_containers': MagicMock(),
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.pull': MagicMock(),
                    'dockerng.state': MagicMock(),
                    'dockerng.inspect_image': MagicMock(),
                    'dockerng.create': dockerng_create,
                    'dockerng.start': dockerng_start,
                    'dockerng.history': dockerng_history,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            dockerng_state.running(
                'cont',
                image='image:latest',
                binds=['/host-0:/container-0:ro'])
        dockerng_create.assert_called_with(
            'image:latest',
            validate_input=False,
            name='cont',
            binds={'/host-0': {'bind': '/container-0', 'ro': True}},
            volumes=['/container-0'],
            validate_ip_addrs=False,
            client_timeout=60)
        dockerng_start.assert_called_with('cont')

    def test_running_with_predifined_volume(self):
        '''
        Test dockerng.running function with an image
        that already have VOLUME defined.

        The ``binds`` argument, shouldn't have side effects on
        container creation.
        '''
        dockerng_create = Mock()
        dockerng_start = Mock()
        dockerng_history = MagicMock(return_value=['VOLUME /container-0'])
        __salt__ = {'dockerng.list_containers': MagicMock(),
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.pull': MagicMock(),
                    'dockerng.state': MagicMock(),
                    'dockerng.inspect_image': MagicMock(),
                    'dockerng.create': dockerng_create,
                    'dockerng.start': dockerng_start,
                    'dockerng.history': dockerng_history,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            dockerng_state.running(
                'cont',
                image='image:latest',
                binds=['/host-0:/container-0:ro'])
        dockerng_create.assert_called_with(
            'image:latest',
            validate_input=False,
            binds={'/host-0': {'bind': '/container-0', 'ro': True}},
            validate_ip_addrs=False,
            name='cont',
            client_timeout=60)
        dockerng_start.assert_called_with('cont')

    def test_running_with_no_predifined_ports(self):
        '''
        Test dockerng.running function with an image
        that doens't have EXPOSE defined.

        The ``port_bindings`` argument, should create a container
        with respective ``ports`` extracted from ``port_bindings``.
        '''
        dockerng_create = Mock()
        dockerng_start = Mock()
        dockerng_history = MagicMock(return_value=[])
        __salt__ = {'dockerng.list_containers': MagicMock(),
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.pull': MagicMock(),
                    'dockerng.state': MagicMock(),
                    'dockerng.inspect_image': MagicMock(),
                    'dockerng.create': dockerng_create,
                    'dockerng.start': dockerng_start,
                    'dockerng.history': dockerng_history,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            dockerng_state.running(
                'cont',
                image='image:latest',
                port_bindings=['9090:9797/tcp'])
        dockerng_create.assert_called_with(
            'image:latest',
            validate_input=False,
            name='cont',
            ports=[9797],
            port_bindings={9797: [9090]},
            validate_ip_addrs=False,
            client_timeout=60)
        dockerng_start.assert_called_with('cont')

    def test_running_with_predifined_ports(self):
        '''
        Test dockerng.running function with an image
        that contains EXPOSE statements.

        The ``port_bindings`` argument, shouldn't have side effect on container
        creation.
        '''
        dockerng_create = Mock()
        dockerng_start = Mock()
        dockerng_history = MagicMock(return_value=['EXPOSE 9797/tcp'])
        __salt__ = {'dockerng.list_containers': MagicMock(),
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.pull': MagicMock(),
                    'dockerng.state': MagicMock(),
                    'dockerng.inspect_image': MagicMock(),
                    'dockerng.create': dockerng_create,
                    'dockerng.start': dockerng_start,
                    'dockerng.history': dockerng_history,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            dockerng_state.running(
                'cont',
                image='image:latest',
                port_bindings=['9090:9797/tcp'])
        dockerng_create.assert_called_with(
            'image:latest',
            validate_input=False,
            name='cont',
            port_bindings={9797: [9090]},
            validate_ip_addrs=False,
            client_timeout=60)
        dockerng_start.assert_called_with('cont')

    def test_running_compare_images_by_id(self):
        '''
        Make sure the container is running
        against expected image.

        Here the local image is named 'image:latest' and the container
        is also running against an image called 'image:latest'.
        Therefore the image ids are diverging because the tag 'image:latest'
        moved to a fresher image.
        Thus this test make sure the old container is droped and recreated.
        '''
        new_fake_image_id = 'abcdefgh'
        old_fake_image_id = '123456789'
        dockerng_inspect_image = Mock(return_value={'Id': new_fake_image_id})
        dockerng_inspect_container = Mock(
            return_value={'Image': old_fake_image_id,
                          'Config': {'Image': 'image:latest'}})
        dockerng_list_containers = Mock(return_value=['cont'])
        dockerng__state = Mock(return_value='running')
        dockerng_stop = Mock(return_value={'result': True})
        dockerng_rm = Mock(return_value=['container-id'])
        __salt__ = {'dockerng.list_containers': dockerng_list_containers,
                    'dockerng.inspect_container': dockerng_inspect_container,
                    'dockerng.inspect_image': dockerng_inspect_image,
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.state': dockerng__state,
                    'dockerng.pull': MagicMock(return_value=new_fake_image_id),
                    'dockerng.create': MagicMock(return_value='new_container'),
                    'dockerng.start': MagicMock(),
                    'dockerng.stop': dockerng_stop,
                    'dockerng.rm': dockerng_rm,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            ret = dockerng_state.running(
                'cont',
                image='image:latest',
                )
            dockerng_stop.assert_called_with('cont', timeout=10, unpause=True)
            dockerng_rm.assert_called_with('cont')
        self.assertEqual(ret, {'name': 'cont',
                               'comment': "Container 'cont' was replaced",
                               'result': True,
                               'changes': {'added': 'new_container',
                                           'image': new_fake_image_id,
                                           'removed': ['container-id']}
                               })

    def test_image_present_already_local(self):
        '''
        According following sls,

        .. code-block:: yaml

            image:latest:
              dockerng.image_present:
                - force: true

        if ``image:latest`` is already downloaded locally the state
        should not report changes.
        '''
        dockerng_inspect_image = Mock(
            return_value={'Id': 'abcdefghijk'})
        dockerng_pull = Mock(
            return_value={'Layers':
                          {'Already_Pulled': ['abcdefghijk'],
                           'Pulled': []},
                          'Status': 'Image is up to date for image:latest',
                          'Time_Elapsed': 1.1})
        dockerng_list_tags = Mock(
            return_value=['image:latest']
        )
        __salt__ = {'dockerng.list_tags': dockerng_list_tags,
                    'dockerng.pull': dockerng_pull,
                    'dockerng.inspect_image': dockerng_inspect_image,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            ret = dockerng_state.image_present('image:latest', force=True)
            self.assertEqual(ret,
                             {'changes': {},
                              'result': True,
                              'comment': "Image 'image:latest' was pulled, "
                              "but there were no changes",
                              'name': 'image:latest',
                              })

    def test_image_present_and_force(self):
        '''
        According following sls,

        .. code-block:: yaml

            image:latest:
              dockerng.image_present:
                - force: true

        if ``image:latest`` is not downloaded and force is true
        should pull a new image successfuly.
        '''
        dockerng_inspect_image = Mock(
            side_effect=CommandExecutionError(
                'Error 404: No such image/container: image:latest'))
        dockerng_pull = Mock(
            return_value={'Layers':
                          {'Already_Pulled': ['abcdefghijk'],
                           'Pulled': ['abcdefghijk']},
                          'Status': "Image 'image:latest' was pulled",
                          'Time_Elapsed': 1.1})
        dockerng_list_tags = Mock(
            side_effect=[[], ['image:latest']]
        )
        __salt__ = {'dockerng.list_tags': dockerng_list_tags,
                    'dockerng.pull': dockerng_pull,
                    'dockerng.inspect_image': dockerng_inspect_image,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            ret = dockerng_state.image_present('image:latest', force=True)
        self.assertEqual(ret,
                         {'changes': {
                             'Layers': {'Already_Pulled': ['abcdefghijk'],
                                        'Pulled': ['abcdefghijk']},
                             'Status': "Image 'image:latest' was pulled",
                             'Time_Elapsed': 1.1},
                             'result': True,
                             'comment': "Image 'image:latest' was pulled",
                             'name': 'image:latest',
                         })

    def test_check_start_false(self):
        '''
        If start is False, then dockerng.running will not try
        to start a container that is stopped.
        '''
        image_id = 'abcdefg'
        dockerng_create = Mock()
        dockerng_start = Mock()
        dockerng_list_containers = Mock(return_value=['cont'])
        dockerng_inspect_container = Mock(
            return_value={'Config': {'Image': 'image:latest'},
                          'Image': image_id})
        __salt__ = {'dockerng.list_containers': dockerng_list_containers,
                    'dockerng.inspect_container': dockerng_inspect_container,
                    'dockerng.inspect_image': MagicMock(
                        return_value={'Id': image_id}),
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.pull': MagicMock(),
                    'dockerng.state': MagicMock(side_effect=['stopped',
                                                             'running']),
                    'dockerng.create': dockerng_create,
                    'dockerng.start': dockerng_start,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            ret = dockerng_state.running(
                'cont',
                image='image:latest',
                start=False,
                )
        self.assertEqual(ret, {'name': 'cont',
                               'comment': "Container 'cont' is already "
                               "configured as specified",
                               'changes': {},
                               'result': True,
                               })

    def test_check_start_true(self):
        '''
        If start is True, then dockerng.running will try
        to start a container that is stopped.
        '''
        image_id = 'abcdefg'
        dockerng_create = Mock()
        dockerng_start = Mock()
        dockerng_list_containers = Mock(return_value=['cont'])
        dockerng_inspect_container = Mock(
            return_value={'Config': {'Image': 'image:latest'},
                          'Image': image_id})
        __salt__ = {'dockerng.list_containers': dockerng_list_containers,
                    'dockerng.inspect_container': dockerng_inspect_container,
                    'dockerng.inspect_image': MagicMock(
                        return_value={'Id': image_id}),
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.pull': MagicMock(),
                    'dockerng.state': MagicMock(side_effect=['stopped',
                                                             'running']),
                    'dockerng.create': dockerng_create,
                    'dockerng.start': dockerng_start,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            ret = dockerng_state.running(
                'cont',
                image='image:latest',
                start=True,
                )
        self.assertEqual(ret, {'name': 'cont',
                               'comment': "Container 'cont' changed state.",
                               'changes': {'state': {'new': 'running',
                                                     'old': 'stopped'}},
                               'result': True,
                               })

    def test_running_discard_wrong_environemnt_values(self):
        '''
        environment values should be string.
        It is easy to write wrong sls this way

        .. code-block:: yaml

            container:
                dockerng.running:
                    - environment:
                        - KEY: 1

        instead of:

        .. code-block:: yaml

            container:
                dockerng.running:
                    - environment:
                        - KEY: "1"
        '''
        __salt__ = {'dockerng.list_containers': MagicMock(),
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.inspect_image': MagicMock(),
                    'dockerng.pull': MagicMock(),
                    'dockerng.state': MagicMock(),
                    'dockerng.create': MagicMock(),
                    'dockerng.start': MagicMock(),
                    'dockerng.history': MagicMock(),
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            for wrong_value in (1, .2, (), [], {}):
                ret = dockerng_state.running(
                    'cont',
                    image='image:latest',
                    environment=[{'KEY': wrong_value}])
                self.assertEqual(ret,
                                 {'changes': {},
                                  'comment': 'Environment values must'
                                  ' be strings KEY=\'{0}\''.format(wrong_value),
                                  'name': 'cont',
                                  'result': False})

    def test_running_with_labels(self):
        '''
        Test dockerng.running with labels parameter.
        '''
        dockerng_create = Mock()
        __salt__ = {'dockerng.list_containers': MagicMock(),
                    'dockerng.list_tags': MagicMock(),
                    'dockerng.pull': MagicMock(),
                    'dockerng.state': MagicMock(),
                    'dockerng.inspect_image': MagicMock(),
                    'dockerng.create': dockerng_create,
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            dockerng_state.running(
                'cont',
                image='image:latest',
                labels=['LABEL1', 'LABEL2'],
                )
        dockerng_create.assert_called_with(
            'image:latest',
            validate_input=False,
            validate_ip_addrs=False,
            name='cont',
            labels=['LABEL1', 'LABEL2'],
            client_timeout=60)

    def test_network_present(self):
        '''
        Test dockerng.network_present
        '''
        dockerng_create_network = Mock(return_value='created')
        dockerng_connect_container_to_network = Mock(return_value='connected')
        __salt__ = {'dockerng.create_network': dockerng_create_network,
                    'dockerng.connect_container_to_network': dockerng_connect_container_to_network,
                    'dockerng.networks': Mock(return_value=[]),
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            ret = dockerng_state.network_present(
                'network_foo',
                containers=['container'],
                )
        dockerng_create_network.assert_called_with('network_foo', driver=None)
        dockerng_connect_container_to_network.assert_called_with('container',
                                                                 'network_foo')
        self.assertEqual(ret, {'name': 'network_foo',
                               'comment': '',
                               'changes': {'connected': 'connected',
                                           'created': 'created'},
                               'result': True})

    def test_network_absent(self):
        '''
        Test dockerng.network_absent
        '''
        dockerng_remove_network = Mock(return_value='removed')
        dockerng_disconnect_container_from_network = Mock(return_value='disconnected')
        __salt__ = {'dockerng.remove_network': dockerng_remove_network,
                    'dockerng.disconnect_container_from_network': dockerng_disconnect_container_from_network,
                    'dockerng.networks': Mock(return_value=[{'Containers': {'container': {}}}]),
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            ret = dockerng_state.network_absent(
                'network_foo',
                )
        dockerng_disconnect_container_from_network.assert_called_with('container',
                                                                      'network_foo')
        dockerng_remove_network.assert_called_with('network_foo')
        self.assertEqual(ret, {'name': 'network_foo',
                               'comment': '',
                               'changes': {'disconnected': 'disconnected',
                                           'removed': 'removed'},
                               'result': True})

    def test_volume_present(self):
        '''
        Test dockerng.volume_present
        '''
        volumes = []
        default_driver = 'dummy_default'

        def create_volume(name, driver=None, driver_opts=None):
            for v in volumes:
                # volume_present should never try to add a conflicting
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
            # volume_present should not have tried to remove a volume
            # that didn't exist
            self.assertEqual(1, len(removed))
            volumes.remove(removed[0])
            return removed[0]

        dockerng_create_volume = Mock(side_effect=create_volume)
        __salt__ = {'dockerng.create_volume': dockerng_create_volume,
                    'dockerng.volumes': Mock(return_value={'Volumes': volumes}),
                    'dockerng.remove_volume': Mock(side_effect=remove_volume),
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            ret = dockerng_state.volume_present(
                'volume_foo',
                )
            dockerng_create_volume.assert_called_with('volume_foo',
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
            ret = dockerng_state.volume_present('volume_foo')
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
            ret = dockerng_state.volume_present('volume_foo', driver='local')
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
            ret = dockerng_state.volume_present(
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

    def test_volume_present_with_another_driver(self):
        '''
        Test dockerng.volume_present
        '''
        dockerng_create_volume = Mock(return_value='created')
        dockerng_remove_volume = Mock(return_value='removed')
        __salt__ = {'dockerng.create_volume': dockerng_create_volume,
                    'dockerng.remove_volume': dockerng_remove_volume,
                    'dockerng.volumes': Mock(return_value={
                        'Volumes': [{'Name': 'volume_foo',
                                     'Driver': 'foo'}]}),
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            ret = dockerng_state.volume_present(
                'volume_foo',
                driver='bar',
                force=True,
                )
        dockerng_remove_volume.assert_called_with('volume_foo')
        dockerng_create_volume.assert_called_with('volume_foo',
                                                  driver='bar',
                                                  driver_opts=None)
        self.assertEqual(ret, {'name': 'volume_foo',
                               'comment': '',
                               'changes': {'created': 'created',
                                           'removed': 'removed'},
                               'result': True})

    def test_volume_absent(self):
        '''
        Test dockerng.volume_absent
        '''
        dockerng_remove_volume = Mock(return_value='removed')
        __salt__ = {'dockerng.remove_volume': dockerng_remove_volume,
                    'dockerng.volumes': Mock(return_value={
                        'Volumes': [{'Name': 'volume_foo'}]}),
                    }
        with patch.dict(dockerng_state.__dict__,
                        {'__salt__': __salt__}):
            ret = dockerng_state.volume_absent(
                'volume_foo',
                )
        dockerng_remove_volume.assert_called_with('volume_foo')
        self.assertEqual(ret, {'name': 'volume_foo',
                               'comment': '',
                               'changes': {'removed': 'removed'},
                               'result': True})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DockerngTestCase, needs_daemon=False)
