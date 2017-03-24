# -*- coding: utf-8 -*-
'''
Unit tests for the docker state
'''

# Import Python Libs
from __future__ import absolute_import

# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    Mock,
    NO_MOCK,
    NO_MOCK_REASON,
    patch
)

# Import Salt Libs
from salt.exceptions import CommandExecutionError
import salt.modules.docker as docker_mod
import salt.states.docker_image as docker_state

docker_mod.__context__ = {'docker.docker_version': ''}
docker_mod.__salt__ = {}
docker_state.__context__ = {}
docker_state.__opts__ = {'test': False}


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DockerImageTestCase(TestCase):
    '''
    Test docker_image states
    '''
    def test_present_already_local(self):
        '''
        According following sls,

        .. code-block:: yaml

            image:latest:
              docker_image.present:
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
            ret = docker_state.present('image:latest', force=True)
            self.assertEqual(ret,
                             {'changes': {},
                              'result': True,
                              'comment': "Image 'image:latest' was pulled, "
                              "but there were no changes",
                              'name': 'image:latest',
                              })

    def test_present_and_force(self):
        '''
        According following sls,

        .. code-block:: yaml

            image:latest:
              docker_image.present:
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
            ret = docker_state.present('image:latest', force=True)
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
