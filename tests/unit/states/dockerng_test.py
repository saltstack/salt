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
            volumes=['/container-0'],
            client_timeout=60)
        dockerng_start.assert_called_with(
            'cont',
            binds={'/host-0': {'bind': '/container-0', 'ro': True}},
            validate_ip_addrs=False,
            validate_input=False)

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
            name='cont',
            client_timeout=60)
        dockerng_start.assert_called_with(
            'cont',
            binds={'/host-0': {'bind': '/container-0', 'ro': True}},
            validate_ip_addrs=False,
            validate_input=False)

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
            client_timeout=60)
        dockerng_start.assert_called_with(
            'cont',
            port_bindings={9797: [9090]},
            validate_ip_addrs=False,
            validate_input=False)

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
            client_timeout=60)
        dockerng_start.assert_called_with(
            'cont',
            port_bindings={9797: [9090]},
            validate_ip_addrs=False,
            validate_input=False)

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
                                  ' be strings KEY={0!r}'.format(wrong_value),
                                  'name': 'cont',
                                  'result': False})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DockerngTestCase, needs_daemon=False)
