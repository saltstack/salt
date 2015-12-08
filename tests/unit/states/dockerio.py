# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import
from contextlib import contextmanager

# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.mock import NO_MOCK, NO_MOCK_REASON, MagicMock


@contextmanager
def provision_state(module, fixture):
    previous_dict = getattr(module, '__salt__', {}).copy()
    try:
        module.__dict__.setdefault('__salt__', {}).update(fixture)
        yield
    finally:
        setattr(module, '__salt__', previous_dict)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class DockerStateTestCase(TestCase):
    def test_docker_run_success(self):
        from salt.states import dockerio
        salt_fixture = {'docker.retcode': MagicMock(return_value=0),
                        'docker.run_all': MagicMock(
                            return_value={'stdout': '.\n..\n',
                                          'stderr': '',
                                          'status': True,
                                          'comment': 'Success',
                                          'retcode': 0})}

        with provision_state(dockerio, salt_fixture):
            result = dockerio.run('ls /', 'ubuntu')

        self.assertEqual(result, {'name': 'ls /',
                                  'result': True,
                                  'comment': 'Success',
                                  'changes': {}})

    def test_docker_run_failure(self):
        from salt.states import dockerio
        salt_fixture = {'docker.retcode': MagicMock(return_value=0),
                        'docker.run_all': MagicMock(
                            return_value={'stdout': '',
                                          'stderr': 'Error',
                                          'status': False,
                                          'comment': 'Failure',
                                          'retcode': 1})}

        with provision_state(dockerio, salt_fixture):
            result = dockerio.run('ls /', 'ubuntu')

        self.assertEqual(result, {'name': 'ls /',
                                  'result': False,
                                  'comment': 'Failure',
                                  'changes': {}})

    def test_docker_run_onlyif(self):
        from salt.states import dockerio
        salt_fixture = {'docker.retcode': MagicMock(return_value=1),
                        'docker.run_all': None}
        with provision_state(dockerio, salt_fixture):
            result = dockerio.run('ls /', 'ubuntu',
                                  onlyif='ls -l')
        self.assertEqual(result, {'name': 'ls /',
                                  'result': True,
                                  'comment': 'onlyif execution failed',
                                  'changes': {}})

    def test_docker_run_unless(self):
        from salt.states import dockerio
        salt_fixture = {'docker.retcode': MagicMock(return_value=0),
                        'docker.run_all': None}
        with provision_state(dockerio, salt_fixture):
            result = dockerio.run('ls /', 'ubuntu',
                                  unless='ls -l')
        self.assertEqual(result, {'name': 'ls /',
                                  'result': True,
                                  'comment': 'unless execution succeeded',
                                  'changes': {}})

    def test_docker_run_docked_onlyif(self):
        from salt.states import dockerio
        salt_fixture = {'docker.retcode': MagicMock(return_value=1),
                        'docker.run_all': None}
        with provision_state(dockerio, salt_fixture):
            result = dockerio.run('ls /', 'ubuntu',
                                  docked_onlyif='ls -l')
        self.assertEqual(result, {'name': 'ls /',
                                  'result': True,
                                  'comment': 'docked_onlyif execution failed',
                                  'changes': {}})

    def test_docker_run_docked_unless(self):
        from salt.states import dockerio
        salt_fixture = {'docker.retcode': MagicMock(return_value=0),
                        'docker.run_all': None}
        with provision_state(dockerio, salt_fixture):
            result = dockerio.run('ls /', 'ubuntu',
                                  docked_unless='ls -l')
        self.assertEqual(result, {'name': 'ls /',
                                  'result': True,
                                  'comment': ('docked_unless execution'
                                              ' succeeded'),
                                  'changes': {}})


if __name__ == '__main__':
    from integration import run_tests
    run_tests(DockerStateTestCase, needs_daemon=False)
