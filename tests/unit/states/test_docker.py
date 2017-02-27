# -*- coding: utf-8 -*-
'''
Unit tests for the docker state
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from salt.exceptions import SaltInvocationError
from tests.support.mock import (
    MagicMock,
    Mock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt Libs
from salt.exceptions import CommandExecutionError
from salt.modules import docker as docker_mod
from salt.states import docker as docker_state

docker_mod.__context__ = {'docker.docker_version': ''}
docker_mod.__salt__ = {}
docker_state.__context__ = {}
docker_state.__opts__ = {'test': False}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DockerTestCase(TestCase):
    '''
    Validate docker state
    '''

    def test_running_with_no_predifined_volume(self):
        '''
        Test docker.running function with an image
        that doens't have VOLUME defined.

        The ``binds`` argument, should create a container
        with respective volumes extracted from ``binds``.
        '''
        docker_create = Mock()
        docker_start = Mock()
        __salt__ = {'docker.list_containers': MagicMock(),
                    'docker.list_tags': MagicMock(),
                    'docker.pull': MagicMock(),
                    'docker.state': MagicMock(),
                    'docker.inspect_image': MagicMock(),
                    'docker.create': docker_create,
                    'docker.start': docker_start,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            docker_state.running(
                'cont',
                image='image:latest',
                binds=['/host-0:/container-0:ro'])
        docker_create.assert_called_with(
            'image:latest',
            validate_input=False,
            name='cont',
            binds={'/host-0': {'bind': '/container-0', 'ro': True}},
            volumes=['/container-0'],
            validate_ip_addrs=False,
            client_timeout=60)
        docker_start.assert_called_with('cont')

    def test_running_with_predifined_volume(self):
        '''
        Test docker.running function with an image
        that already have VOLUME defined.

        The ``binds`` argument, should create a container
        with ``volumes`` extracted from ``binds``.
        '''
        docker_create = Mock()
        docker_start = Mock()
        docker_inspect_image = Mock(return_value={
            'Id': 'abcd',
            'Config': {'Config': {'Volumes': ['/host-1']}},
        })
        __salt__ = {'docker.list_containers': MagicMock(),
                    'docker.list_tags': MagicMock(),
                    'docker.pull': MagicMock(),
                    'docker.state': MagicMock(),
                    'docker.inspect_image': docker_inspect_image,
                    'docker.create': docker_create,
                    'docker.start': docker_start,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            docker_state.running(
                'cont',
                image='image:latest',
                binds=['/host-0:/container-0:ro'])
        docker_create.assert_called_with(
            'image:latest',
            validate_input=False,
            binds={'/host-0': {'bind': '/container-0', 'ro': True}},
            volumes=['/container-0'],
            validate_ip_addrs=False,
            name='cont',
            client_timeout=60)
        docker_start.assert_called_with('cont')

    def test_running_with_no_predifined_ports(self):
        '''
        Test docker.running function with an image
        that doens't have EXPOSE defined.

        The ``port_bindings`` argument, should create a container
        with ``ports`` extracted from ``port_bindings``.
        '''
        docker_create = Mock()
        docker_start = Mock()
        docker_inspect_image = Mock(return_value={
            'Id': 'abcd',
            'Config': {'Config': {'ExposedPorts': {}}},
        })
        __salt__ = {'docker.list_containers': MagicMock(),
                    'docker.list_tags': MagicMock(),
                    'docker.pull': MagicMock(),
                    'docker.state': MagicMock(),
                    'docker.inspect_image': docker_inspect_image,
                    'docker.create': docker_create,
                    'docker.start': docker_start,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            docker_state.running(
                'cont',
                image='image:latest',
                port_bindings=['9090:9797/tcp'])
        docker_create.assert_called_with(
            'image:latest',
            validate_input=False,
            name='cont',
            ports=[9797],
            port_bindings={9797: [9090]},
            validate_ip_addrs=False,
            client_timeout=60)
        docker_start.assert_called_with('cont')

    def test_running_with_predifined_ports(self):
        '''
        Test docker.running function with an image
        that expose ports (via Dockerfile EXPOSE statement).

        Check that `ports` contains ports defined on Image and by
        `port_bindings` argument.

        Inside Dockerfile:

        .. code-block::

            EXPOSE 9898

        In sls:

        .. code-block:: yaml

            container:
                docker.running:
                    - port_bindings:
                        - '9090:9797/tcp'

        '''
        docker_create = Mock()
        docker_start = Mock()
        docker_inspect_image = Mock(return_value={
            'Id': 'abcd',
            'Config': {'ExposedPorts': {'9898/tcp': {}}}
        })
        __salt__ = {'docker.list_containers': MagicMock(),
                    'docker.list_tags': MagicMock(),
                    'docker.pull': MagicMock(),
                    'docker.state': MagicMock(),
                    'docker.inspect_image': docker_inspect_image,
                    'docker.create': docker_create,
                    'docker.start': docker_start,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            docker_state.running(
                'cont',
                image='image:latest',
                port_bindings=['9090:9797/tcp'])
        docker_create.assert_called_with(
            'image:latest',
            validate_input=False,
            name='cont',
            ports=[9797],
            port_bindings={9797: [9090]},
            validate_ip_addrs=False,
            client_timeout=60)
        docker_start.assert_called_with('cont')

    def test_running_with_udp_bindings(self):
        '''
        Check that `ports` contains ports defined from `port_bindings` with
        protocol declaration passed as tuple. As stated by docker-py
        documentation

        https://docker-py.readthedocs.io/en/latest/port-bindings/

        In sls:

        .. code-block:: yaml

            container:
                docker.running:
                    - port_bindings:
                        - '9090:9797/udp'

        is equivalent of:

        .. code-block:: yaml

            container:
                docker.running:
                    - ports:
                        - 9797/udp
                    - port_bindings:
                        - '9090:9797/udp'
        '''
        docker_create = Mock()
        docker_start = Mock()
        docker_inspect_image = Mock(return_value={
            'Id': 'abcd',
            'Config': {'ExposedPorts': {}}
        })
        __salt__ = {'docker.list_containers': MagicMock(),
                    'docker.list_tags': MagicMock(),
                    'docker.pull': MagicMock(),
                    'docker.state': MagicMock(),
                    'docker.inspect_image': docker_inspect_image,
                    'docker.create': docker_create,
                    'docker.start': docker_start,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            docker_state.running(
                'cont',
                image='image:latest',
                port_bindings=['9090:9797/udp'])
        docker_create.assert_called_with(
            'image:latest',
            validate_input=False,
            name='cont',
            ports=[(9797, 'udp')],
            port_bindings={'9797/udp': [9090]},
            validate_ip_addrs=False,
            client_timeout=60)
        docker_start.assert_called_with('cont')

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
        docker_inspect_image = Mock(return_value={'Id': new_fake_image_id})
        docker_inspect_container = Mock(
            return_value={'Image': old_fake_image_id,
                          'Config': {'Image': 'image:latest'}})
        docker_list_containers = Mock(return_value=['cont'])
        docker__state = Mock(return_value='running')
        docker_stop = Mock(return_value={'result': True})
        docker_rm = Mock(return_value=['container-id'])
        __salt__ = {'docker.list_containers': docker_list_containers,
                    'docker.inspect_container': docker_inspect_container,
                    'docker.inspect_image': docker_inspect_image,
                    'docker.list_tags': MagicMock(),
                    'docker.state': docker__state,
                    'docker.pull': MagicMock(return_value=new_fake_image_id),
                    'docker.create': MagicMock(return_value='new_container'),
                    'docker.start': MagicMock(),
                    'docker.stop': docker_stop,
                    'docker.rm': docker_rm,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.running(
                'cont',
                image='image:latest',
                )
            docker_stop.assert_called_with('cont', timeout=10, unpause=True)
            docker_rm.assert_called_with('cont')
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
              docker.image_present:
                - force: true

        if ``image:latest`` is already downloaded locally the state
        should not report changes.
        '''
        docker_inspect_image = Mock(
            return_value={'Id': 'abcdefghijk'})
        docker_pull = Mock(
            return_value={'Layers':
                          {'Already_Pulled': ['abcdefghijk'],
                           'Pulled': []},
                          'Status': 'Image is up to date for image:latest',
                          'Time_Elapsed': 1.1})
        docker_list_tags = Mock(
            return_value=['image:latest']
        )
        __salt__ = {'docker.list_tags': docker_list_tags,
                    'docker.pull': docker_pull,
                    'docker.inspect_image': docker_inspect_image,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.image_present('image:latest', force=True)
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
              docker.image_present:
                - force: true

        if ``image:latest`` is not downloaded and force is true
        should pull a new image successfuly.
        '''
        docker_inspect_image = Mock(
            side_effect=CommandExecutionError(
                'Error 404: No such image/container: image:latest'))
        docker_pull = Mock(
            return_value={'Layers':
                          {'Already_Pulled': ['abcdefghijk'],
                           'Pulled': ['abcdefghijk']},
                          'Status': "Image 'image:latest' was pulled",
                          'Time_Elapsed': 1.1})
        docker_list_tags = Mock(
            side_effect=[[], ['image:latest']]
        )
        __salt__ = {'docker.list_tags': docker_list_tags,
                    'docker.pull': docker_pull,
                    'docker.inspect_image': docker_inspect_image,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.image_present('image:latest', force=True)
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
        If start is False, then docker.running will not try
        to start a container that is stopped.
        '''
        image_id = 'abcdefg'
        docker_create = Mock()
        docker_start = Mock()
        docker_list_containers = Mock(return_value=['cont'])
        docker_inspect_container = Mock(
            return_value={
                'Config': {
                    'Image': 'image:latest',
                    'Tty': False,
                    'Labels': {},
                    'Domainname': '',
                    'User': '',
                    'AttachStderr': True,
                    'AttachStdout': True,
                    'Hostname': 'saltstack-container',
                    'Env': [],
                    'WorkingDir': '/',
                    'Cmd': ['bash'],
                    'Volumes': {},
                    'Entrypoint': None,
                    'ExposedPorts': {},
                    'OpenStdin': False,
                },
                'HostConfig': {
                    'PublishAllPorts': False,
                    'Dns': [],
                    'Links': None,
                    'CpusetCpus': '',
                    'RestartPolicy': {'MaximumRetryCount': 0, 'Name': ''},
                    'CapAdd': None,
                    'NetworkMode': 'default',
                    'PidMode': '',
                    'MemorySwap': 0,
                    'ExtraHosts': None,
                    'PortBindings': None,
                    'LxcConf': None,
                    'DnsSearch': [],
                    'Privileged': False,
                    'Binds': None,
                    'Memory': 0,
                    'VolumesFrom': None,
                    'CpuShares': 0,
                    'CapDrop': None,
                },
                'NetworkSettings': {
                    'MacAddress': '00:00:00:00:00:01',
                },
                'Image': image_id})
        docker_inspect_image = MagicMock(
            return_value={
                'Id': image_id,
                'Config': {
                    'Hostname': 'saltstack-container',
                    'WorkingDir': '/',
                    'Cmd': ['bash'],
                    'Volumes': {},
                    'Entrypoint': None,
                    'ExposedPorts': {},
                },
                })
        __salt__ = {'docker.list_containers': docker_list_containers,
                    'docker.inspect_container': docker_inspect_container,
                    'docker.inspect_image': docker_inspect_image,
                    'docker.list_tags': MagicMock(
                        return_value=['image:latest']),
                    'docker.pull': MagicMock(),
                    'docker.state': MagicMock(side_effect=['stopped',
                                                             'running']),
                    'docker.create': docker_create,
                    'docker.start': docker_start,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.running(
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
        If start is True, then docker.running will try
        to start a container that is stopped.
        '''
        image_id = 'abcdefg'
        docker_create = Mock()
        docker_start = Mock()
        docker_list_containers = Mock(return_value=['cont'])
        docker_inspect_container = Mock(
            return_value={
                'Config': {
                    'Image': 'image:latest',
                    'Tty': False,
                    'Labels': {},
                    'Domainname': '',
                    'User': '',
                    'AttachStderr': True,
                    'AttachStdout': True,
                    'Hostname': 'saltstack-container',
                    'Env': [],
                    'WorkingDir': '/',
                    'Cmd': ['bash'],
                    'Volumes': {},
                    'Entrypoint': None,
                    'ExposedPorts': {},
                    'OpenStdin': False,
                },
                'HostConfig': {
                    'PublishAllPorts': False,
                    'Dns': [],
                    'Links': None,
                    'CpusetCpus': '',
                    'RestartPolicy': {'MaximumRetryCount': 0, 'Name': ''},
                    'CapAdd': None,
                    'NetworkMode': 'default',
                    'PidMode': '',
                    'MemorySwap': 0,
                    'ExtraHosts': None,
                    'PortBindings': None,
                    'LxcConf': None,
                    'DnsSearch': [],
                    'Privileged': False,
                    'Binds': None,
                    'Memory': 0,
                    'VolumesFrom': None,
                    'CpuShares': 0,
                    'CapDrop': None,
                },
                'NetworkSettings': {
                    'MacAddress': '00:00:00:00:00:01',
                },
                'Image': image_id})
        docker_inspect_image = MagicMock(
            return_value={
                'Id': image_id,
                'Config': {
                    'Hostname': 'saltstack-container',
                    'WorkingDir': '/',
                    'Cmd': ['bash'],
                    'Volumes': {},
                    'Entrypoint': None,
                    'ExposedPorts': {},
                },
                })
        __salt__ = {'docker.list_containers': docker_list_containers,
                    'docker.inspect_container': docker_inspect_container,
                    'docker.inspect_image': docker_inspect_image,
                    'docker.list_tags': MagicMock(),
                    'docker.pull': MagicMock(return_value=True),
                    'docker.state': MagicMock(side_effect=['stopped',
                                                             'running']),
                    'docker.create': docker_create,
                    'docker.start': docker_start,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.running(
                'cont',
                image='image:latest',
                start=True,
                )
        self.assertEqual(ret, {'name': 'cont',
                               'comment': "Container 'cont' changed state.",
                               'changes': {'state': {'new': 'running',
                                                     'old': 'stopped'},
                                           'image': True},
                               'result': True,
                               })

    def test_running_discard_wrong_environment_values(self):
        '''
        environment values should be string.
        It is easy to write wrong sls this way

        .. code-block:: yaml

            container:
                docker.running:
                    - environment:
                        - KEY: 1

        instead of:

        .. code-block:: yaml

            container:
                docker.running:
                    - environment:
                        - KEY: "1"
        '''
        __salt__ = {'docker.list_containers': MagicMock(),
                    'docker.list_tags': MagicMock(
                        return_value=['image:latest']),
                    'docker.inspect_image': MagicMock(),
                    'docker.pull': MagicMock(),
                    'docker.state': MagicMock(),
                    'docker.create': MagicMock(),
                    'docker.start': MagicMock(),
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            for wrong_value in (1, .2, (), [], {}):
                ret = docker_state.running(
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
        Test docker.running with labels parameter.
        '''
        docker_create = Mock()
        __salt__ = {'docker.list_containers': MagicMock(),
                    'docker.list_tags': MagicMock(),
                    'docker.pull': MagicMock(),
                    'docker.state': MagicMock(),
                    'docker.inspect_image': MagicMock(),
                    'docker.create': docker_create,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            docker_state.running(
                'cont',
                image='image:latest',
                labels=['LABEL1', 'LABEL2'],
                )
        docker_create.assert_called_with(
            'image:latest',
            validate_input=False,
            validate_ip_addrs=False,
            name='cont',
            labels=['LABEL1', 'LABEL2'],
            client_timeout=60)

    def test_running_with_labels_from_image(self):
        '''
        Test docker.running with labels parameter supports also
        labels carried by the image.
        '''
        docker_create = Mock()

        image_id = 'a' * 128
        docker_inspect_image = MagicMock(
            return_value={
                'Id': image_id,
                'Config': {
                    'Hostname': 'saltstack-container',
                    'WorkingDir': '/',
                    'Cmd': ['bash'],
                    'Volumes': {'/path': {}},
                    'Entrypoint': None,
                    'ExposedPorts': {},
                    'Labels': {'IMAGE_LABEL': 'image_foo',
                               'LABEL1': 'label1'},
                },
                })
        __salt__ = {'docker.list_containers': MagicMock(),
                    'docker.list_tags': MagicMock(),
                    'docker.pull': MagicMock(),
                    'docker.state': MagicMock(),
                    'docker.inspect_image': docker_inspect_image,
                    'docker.create': docker_create,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            docker_state.running(
                'cont',
                image='image:latest',
                labels=[{'LABEL1': 'foo1'}, {'LABEL2': 'foo2'}],
                )
        docker_create.assert_called_with(
            'image:latest',
            validate_input=False,
            validate_ip_addrs=False,
            name='cont',
            labels={'LABEL1': 'foo1', 'LABEL2': 'foo2'},
            client_timeout=60)

    def test_network_present(self):
        '''
        Test docker.network_present
        '''
        docker_create_network = Mock(return_value='created')
        docker_connect_container_to_network = Mock(return_value='connected')
        docker_inspect_container = Mock(return_value={'Id': 'abcd'})
        __salt__ = {'docker.create_network': docker_create_network,
                    'docker.inspect_container': docker_inspect_container,
                    'docker.connect_container_to_network': docker_connect_container_to_network,
                    'docker.networks': Mock(return_value=[]),
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.network_present(
                'network_foo',
                containers=['container'],
                )
        docker_create_network.assert_called_with('network_foo', driver=None)
        docker_connect_container_to_network.assert_called_with('abcd',
                                                                 'network_foo')
        self.assertEqual(ret, {'name': 'network_foo',
                               'comment': '',
                               'changes': {'connected': 'connected',
                                           'created': 'created'},
                               'result': True})

    def test_network_absent(self):
        '''
        Test docker.network_absent
        '''
        docker_remove_network = Mock(return_value='removed')
        docker_disconnect_container_from_network = Mock(return_value='disconnected')
        __salt__ = {'docker.remove_network': docker_remove_network,
                    'docker.disconnect_container_from_network': docker_disconnect_container_from_network,
                    'docker.networks': Mock(return_value=[{'Containers': {'container': {}}}]),
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.network_absent(
                'network_foo',
                )
        docker_disconnect_container_from_network.assert_called_with('container',
                                                                      'network_foo')
        docker_remove_network.assert_called_with('network_foo')
        self.assertEqual(ret, {'name': 'network_foo',
                               'comment': '',
                               'changes': {'disconnected': 'disconnected',
                                           'removed': 'removed'},
                               'result': True})

    def test_volume_present(self):
        '''
        Test docker.volume_present
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

        docker_create_volume = Mock(side_effect=create_volume)
        __salt__ = {'docker.create_volume': docker_create_volume,
                    'docker.volumes': Mock(return_value={'Volumes': volumes}),
                    'docker.remove_volume': Mock(side_effect=remove_volume),
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.volume_present(
                'volume_foo',
                )
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
            ret = docker_state.volume_present('volume_foo')
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
            ret = docker_state.volume_present('volume_foo', driver='local')
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
            ret = docker_state.volume_present(
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
        Test docker.volume_present
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
            ret = docker_state.volume_present(
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

    def test_volume_present_wo_existing_volumes(self):
        '''
        Test docker.volume_present without existing volumes.
        '''
        docker_create_volume = Mock(return_value='created')
        docker_remove_volume = Mock(return_value='removed')
        __salt__ = {'docker.create_volume': docker_create_volume,
                    'docker.remove_volume': docker_remove_volume,
                    'docker.volumes': Mock(return_value={'Volumes': None}),
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.volume_present(
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

    def test_volume_absent(self):
        '''
        Test docker.volume_absent
        '''
        docker_remove_volume = Mock(return_value='removed')
        __salt__ = {'docker.remove_volume': docker_remove_volume,
                    'docker.volumes': Mock(return_value={
                        'Volumes': [{'Name': 'volume_foo'}]}),
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.volume_absent(
                'volume_foo',
                )
        docker_remove_volume.assert_called_with('volume_foo')
        self.assertEqual(ret, {'name': 'volume_foo',
                               'comment': '',
                               'changes': {'removed': 'removed'},
                               'result': True})

    def test_removal_of_parameter_is_detected(self):
        '''
        Test docker.running with deleted parameter.

        1. define your sls

        .. code-block:: yaml

            container:
                docker.running:
                    - name: super-container
                    - binds:
                        - /path:/path:ro

        2. run state.highstate

        3. modify your sls by removing `- binds:`

        .. code-block:: yaml

            container:
                docker.running:
                    - name: super-container

        4. enjoy your new created container without mounted volumes.
        '''
        image_id = 'abcdefg'
        docker_create = Mock(return_value=True)
        docker_start = Mock()
        docker_list_containers = Mock(return_value=['cont'])
        docker_inspect_container = Mock(
            side_effect=[{
                'Config': {
                    'Image': 'image:latest',
                    'Tty': False,
                    'Labels': {},
                    'Domainname': '',
                    'User': '',
                    'AttachStderr': True,
                    'AttachStdout': True,
                    'Hostname': 'saltstack-container',
                    'Env': [],
                    'WorkingDir': '/',
                    'Cmd': ['bash'],
                    'Volumes': {'/path': {}},
                    'Entrypoint': None,
                    'ExposedPorts': {},
                    'OpenStdin': False,
                },
                'HostConfig': {
                    'PublishAllPorts': False,
                    'Dns': [],
                    'Links': None,
                    'CpusetCpus': '',
                    'RestartPolicy': {'MaximumRetryCount': 0, 'Name': ''},
                    'CapAdd': None,
                    'NetworkMode': 'default',
                    'PidMode': '',
                    'MemorySwap': 0,
                    'ExtraHosts': None,
                    'PortBindings': None,
                    'LxcConf': None,
                    'DnsSearch': [],
                    'Privileged': False,
                    'Binds': ['/path:/path:ro'],
                    'Memory': 0,
                    'VolumesFrom': None,
                    'CpuShares': 0,
                    'CapDrop': None,
                },
                'NetworkSettings': {
                    'MacAddress': '00:00:00:00:00:01',
                },
                'Image': image_id},
                {'Config': {
                    'Image': 'image:latest',
                    'Tty': False,
                    'Labels': {},
                    'Domainname': '',
                    'User': '',
                    'AttachStderr': True,
                    'AttachStdout': True,
                    'Hostname': 'saltstack-container',
                    'Env': [],
                    'WorkingDir': '/',
                    'Cmd': ['bash'],
                    'Volumes': {'/path': {}},
                    'Entrypoint': None,
                    'ExposedPorts': {},
                    'OpenStdin': False,
                },
                'HostConfig': {
                    'PublishAllPorts': False,
                    'Dns': [],
                    'Links': None,
                    'CpusetCpus': '',
                    'RestartPolicy': {'MaximumRetryCount': 0, 'Name': ''},
                    'CapAdd': None,
                    'NetworkMode': 'default',
                    'PidMode': '',
                    'MemorySwap': 0,
                    'ExtraHosts': None,
                    'PortBindings': None,
                    'LxcConf': None,
                    'DnsSearch': [],
                    'Privileged': False,
                    'Binds': None,
                    'Memory': 0,
                    'VolumesFrom': None,
                    'CpuShares': 0,
                    'CapDrop': None,
                },
                'NetworkSettings': {
                    'MacAddress': '00:00:00:00:00:01',
                },
                'Image': image_id}]
        )
        docker_inspect_image = MagicMock(
            return_value={
                'Id': image_id,
                'Config': {
                    'Hostname': 'saltstack-container',
                    'WorkingDir': '/',
                    'Cmd': ['bash'],
                    'Volumes': {'/path': {}},
                    'Entrypoint': None,
                    'ExposedPorts': {},
                },
                })
        __salt__ = {'docker.list_containers': docker_list_containers,
                    'docker.inspect_container': docker_inspect_container,
                    'docker.inspect_image': docker_inspect_image,
                    'docker.list_tags': MagicMock(),
                    'docker.pull': MagicMock(return_value=True),
                    'docker.state': MagicMock(side_effect=['stopped',
                                                             'running']),
                    'docker.rm': MagicMock(return_value='cont'),
                    'docker.create': docker_create,
                    'docker.start': docker_start,
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.running(
                'cont',
                image='image:latest',
                )
        self.assertEqual(ret, {'name': 'cont',
                               'comment': "Container 'cont' changed state.."
                               " Container 'cont' was replaced.",
                               'changes': {
                                   'diff': {'binds':
                                            {'new': [],
                                             'old': ['/path:/path:ro']}},
                                   'image': True,
                                   'removed': 'cont',
                                   'state': {'new': 'running',
                                             'old': 'stopped'},
                                   'added': True,
                               },
                               'result': True,
                               })
        docker_create.assert_called_with('image:latest',
                                           validate_ip_addrs=False,
                                           validate_input=False,
                                           name='cont',
                                           client_timeout=60)

    def test_validate_input_min_docker_py(self):
        docker_mock = Mock()
        docker_mock.version_info = (1, 0, 0)
        docker_mod.docker = None
        with patch.dict(docker_mod.VALID_CREATE_OPTS['command'],
                        {'path': 'Config:Cmd',
                         'image_path': 'Config:Cmd',
                         'min_docker_py': (999, 0, 0)}):
            with patch.object(docker_mod, 'docker', docker_mock):
                self.assertRaisesRegexp(SaltInvocationError,
                                        "The 'command' parameter requires at"
                                        " least docker-py 999.0.0.*$",
                                        docker_state._validate_input,
                                        {'command': 'echo boom'})

    def test_command_defined_on_image_layer_dont_diff_if_attempted_to_blank(self):
        '''
        Assuming the docker image has a command defined, like ``sh``.
        Erasing this value on sls level will not delete the command
        in the container. And such the diff shouldn't be reported.
        Assuming also the container is already running.

        1. define your sls

        .. code-block:: yaml

            cont:
                docker.running:
                    - image: image:latest


        2. run state.highstate

        No diff should be reported
        '''
        image_id = 'abcdefg'
        docker_create = Mock(return_value=True)
        docker_start = Mock()
        docker_list_containers = Mock(return_value=['cont'])
        docker_inspect_container = Mock(
            side_effect=[{
                'Config': {
                    'Image': 'image:latest',
                    'Tty': False,
                    'Labels': {},
                    'Domainname': '',
                    'User': '',
                    'AttachStderr': True,
                    'AttachStdout': True,
                    'Hostname': 'saltstack-container',
                    'Env': [],
                    'WorkingDir': '/',
                    'Cmd': None,
                    'Volumes': {},
                    'Entrypoint': None,
                    'ExposedPorts': {},
                    'OpenStdin': False,
                },
                'HostConfig': {
                    'PublishAllPorts': False,
                    'Dns': [],
                    'Links': None,
                    'CpusetCpus': '',
                    'RestartPolicy': {'MaximumRetryCount': 0, 'Name': ''},
                    'CapAdd': None,
                    'NetworkMode': 'default',
                    'PidMode': '',
                    'MemorySwap': 0,
                    'ExtraHosts': None,
                    'PortBindings': None,
                    'LxcConf': None,
                    'DnsSearch': [],
                    'Privileged': False,
                    'Binds': [],
                    'Memory': 0,
                    'VolumesFrom': None,
                    'CpuShares': 0,
                    'CapDrop': None,
                },
                'NetworkSettings': {
                    'MacAddress': '00:00:00:00:00:01',
                },
                'Image': image_id}]
        )
        docker_inspect_image = MagicMock(
            return_value={
                'Id': image_id,
                'Config': {
                    'Hostname': 'saltstack-container',
                    'WorkingDir': '/',
                    'Cmd': ['bash'],  # !!! Cmd defined on Image
                    'Volumes': {},
                    'Entrypoint': None,
                    'ExposedPorts': {},
                },
                })
        __salt__ = {'docker.list_containers': docker_list_containers,
                    'docker.inspect_container': docker_inspect_container,
                    'docker.inspect_image': docker_inspect_image,
                    'docker.list_tags': MagicMock(side_effect=[['image:latest']]),
                    'docker.state': MagicMock(side_effect=['running']),
                    }
        with patch.dict(docker_state.__dict__,
                        {'__salt__': __salt__}):
            ret = docker_state.running(
                'cont',
                image='image:latest',
                )
        self.assertEqual(ret, {'name': 'cont',
                               'comment': "Container 'cont' is already"
                               " configured as specified",
                               'changes': {},
                               'result': True,
                               })
