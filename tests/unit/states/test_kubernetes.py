# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jeff Schroeder <jeffschroeder@computer.org>`
'''
# Import Python libs
from __future__ import absolute_import
from contextlib import contextmanager


# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import skipIf, TestCase
from tests.support.mock import (
    NO_MOCK,
    NO_MOCK_REASON,
    MagicMock,
    patch)

# Import Salt Libs
from salt.states import kubernetes


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(kubernetes is False, "Probably Kubernetes client lib is not installed. \
                              Skipping test_kubernetes.py")
class KubernetesTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.states.kubernetes
    '''
    def setup_loader_modules(self):
        return {kubernetes: {'__env__': 'base'}}

    @contextmanager
    def mock_func(self, func_name, return_value, test=False):
        '''
        Mock any of the kubernetes state function return values and set
        the test options.
        '''
        name = 'kubernetes.{0}'.format(func_name)
        mocked = {name: MagicMock(return_value=return_value)}
        with patch.dict(kubernetes.__salt__, mocked) as patched:
            with patch.dict(kubernetes.__opts__, {'test': test}):
                yield patched

    def make_configmap(self, name, namespace='default', data=None):
        return self.make_ret_dict(
            kind='ConfigMap',
            name=name,
            namespace=namespace,
            data=data,
        )

    def make_secret(self, name, namespace='default', data=None):
        return self.make_ret_dict(
            kind='Secret',
            name=name,
            namespace=namespace,
            data=data,
        )

    def make_ret_dict(self, kind, name, namespace=None, data=None):
        '''
        Make a minimal example configmap or secret for using in mocks
        '''

        assert kind in ('Secret', 'ConfigMap')

        if data is None:
            data = {}

        return_data = {
            'kind': kind,
            'data': data,
            'api_version': 'v1',
            'metadata': {
                'name': name,
                'namespace': namespace,
                'labels': None,
                'annotations': {
                    u'kubernetes.io/change-cause': 'salt-call state.apply',
                },
            },
        }
        return return_data

    def test_configmap_present__fail(self):
        error = kubernetes.configmap_present(
            name='testme',
            data={1: 1},
            source='salt://beyond/oblivion.jinja',
        )
        self.assertDictEqual(
            {
                'changes': {},
                'result': False,
                'name': 'testme',
                'comment': "'source' cannot be used in combination with 'data'",
            },
            error,
        )

    def test_configmap_present__create_test_true(self):
        # Create a new configmap with test=True
        with self.mock_func('show_configmap', return_value=None, test=True):
            ret = kubernetes.configmap_present(
                name='example',
                data={'example.conf': '# empty config file'},
            )
            self.assertDictEqual(
                {
                    'comment': 'The configmap is going to be created',
                    'changes': {},
                    'name': 'example',
                    'result': None,
                },
                ret,
            )

    def test_configmap_present__create(self):
        # Create a new configmap
        with self.mock_func('show_configmap', return_value=None):
            cm = self.make_configmap(
                name='test',
                namespace='default',
                data={'foo': 'bar'},
            )
            with self.mock_func('create_configmap', return_value=cm):
                actual = kubernetes.configmap_present(
                    name='test',
                    data={'foo': 'bar'},
                )
                self.assertDictEqual(
                    {
                        'comment': '',
                        'changes': {'data': {'foo': 'bar'}},
                        'name': 'test',
                        'result': True,
                    },
                    actual,
                )

    def test_configmap_present__create_no_data(self):
        # Create a new configmap with no 'data' attribute
        with self.mock_func('show_configmap', return_value=None):
            cm = self.make_configmap(
                name='test',
                namespace='default',
            )
            with self.mock_func('create_configmap', return_value=cm):
                actual = kubernetes.configmap_present(name='test')
                self.assertDictEqual(
                    {
                        'comment': '',
                        'changes': {'data': {}},
                        'name': 'test',
                        'result': True,
                    },
                    actual,
                )

    def test_configmap_present__replace_test_true(self):
        cm = self.make_configmap(
            name='settings',
            namespace='saltstack',
            data={'foobar.conf': '# Example configuration'},
        )
        with self.mock_func('show_configmap', return_value=cm, test=True):
            ret = kubernetes.configmap_present(
                name='settings',
                namespace='saltstack',
                data={'foobar.conf': '# Example configuration'},
            )
            self.assertDictEqual(
                {
                    'comment': 'The configmap is going to be replaced',
                    'changes': {},
                    'name': 'settings',
                    'result': None,
                },
                ret,
            )

    def test_configmap_present__replace(self):
        cm = self.make_configmap(name='settings', data={'action': 'make=war'})
        # Replace an existing configmap
        with self.mock_func('show_configmap', return_value=cm):
            new_cm = cm.copy()
            new_cm.update({
                'data': {'action': 'make=peace'},
            })
            with self.mock_func('replace_configmap', return_value=new_cm):
                actual = kubernetes.configmap_present(
                    name='settings',
                    data={'action': 'make=peace'},
                )
                self.assertDictEqual(
                    {
                        'comment': 'The configmap is already present. Forcing recreation',
                        'changes': {
                            'data': {
                                'action': 'make=peace',
                            },
                        },
                        'name': 'settings',
                        'result': True,
                    },
                    actual,
                )

    def test_configmap_absent__noop_test_true(self):
        # Nothing to delete with test=True
        with self.mock_func('show_configmap', return_value=None, test=True):
            actual = kubernetes.configmap_absent(name='NOT_FOUND')
            self.assertDictEqual(
                {
                    'comment': 'The configmap does not exist',
                    'changes': {},
                    'name': 'NOT_FOUND',
                    'result': None,
                },
                actual,
            )

    def test_configmap_absent__test_true(self):
        # Configmap exists with test=True
        cm = self.make_configmap(name='deleteme', namespace='default')
        with self.mock_func('show_configmap', return_value=cm, test=True):
            actual = kubernetes.configmap_absent(name='deleteme')
            self.assertDictEqual(
                {
                    'comment': 'The configmap is going to be deleted',
                    'changes': {},
                    'name': 'deleteme',
                    'result': None,
                },
                actual,
            )

    def test_configmap_absent__noop(self):
        # Nothing to delete
        with self.mock_func('show_configmap', return_value=None):
            actual = kubernetes.configmap_absent(name='NOT_FOUND')
            self.assertDictEqual(
                {
                    'comment': 'The configmap does not exist',
                    'changes': {},
                    'name': 'NOT_FOUND',
                    'result': True,
                },
                actual,
            )

    def test_configmap_absent(self):
        # Configmap exists, delete it!
        cm = self.make_configmap(name='deleteme', namespace='default')
        with self.mock_func('show_configmap', return_value=cm):
            # The return from this module isn't used in the state
            with self.mock_func('delete_configmap', return_value={}):
                actual = kubernetes.configmap_absent(name='deleteme')
                self.assertDictEqual(
                    {
                        'comment': 'ConfigMap deleted',
                        'changes': {
                            'kubernetes.configmap': {
                                'new': 'absent',
                                'old': 'present',
                            },
                        },
                        'name': 'deleteme',
                        'result': True,
                    },
                    actual,
                )

    def test_secret_present__fail(self):
        actual = kubernetes.secret_present(
            name='sekret',
            data={'password': 'monk3y'},
            source='salt://nope.jinja',
        )
        self.assertDictEqual(
            {
                'changes': {},
                'result': False,
                'name': 'sekret',
                'comment': "'source' cannot be used in combination with 'data'",
            },
            actual,
        )

    def test_secret_present__exists_test_true(self):
        secret = self.make_secret(name='sekret')
        new_secret = secret.copy()
        new_secret.update({
            'data': {'password': 'uncle'},
        })
        # Secret exists already and needs replacing with test=True
        with self.mock_func('show_secret', return_value=secret):
            with self.mock_func('replace_secret', return_value=new_secret, test=True):
                actual = kubernetes.secret_present(
                    name='sekret',
                    data={'password': 'uncle'},
                )
                self.assertDictEqual(
                    {
                        'changes': {},
                        'result': None,
                        'name': 'sekret',
                        'comment': 'The secret is going to be replaced',
                    },
                    actual,
                )

    def test_secret_present__exists(self):
        # Secret exists and gets replaced
        secret = self.make_secret(name='sekret', data={'password': 'booyah'})
        with self.mock_func('show_secret', return_value=secret):
            with self.mock_func('replace_secret', return_value=secret):
                actual = kubernetes.secret_present(
                    name='sekret',
                    data={'password': 'booyah'},
                )
                self.assertDictEqual(
                    {
                        'changes': {'data': ['password']},
                        'result': True,
                        'name': 'sekret',
                        'comment': "The secret is already present. Forcing recreation",
                    },
                    actual,
                )

    def test_secret_present__create(self):
        # Secret exists and gets replaced
        secret = self.make_secret(name='sekret', data={'password': 'booyah'})
        with self.mock_func('show_secret', return_value=None):
            with self.mock_func('create_secret', return_value=secret):
                actual = kubernetes.secret_present(
                    name='sekret',
                    data={'password': 'booyah'},
                )
                self.assertDictEqual(
                    {
                        'changes': {'data': ['password']},
                        'result': True,
                        'name': 'sekret',
                        'comment': '',
                    },
                    actual,
                )

    def test_secret_present__create_no_data(self):
        # Secret exists and gets replaced
        secret = self.make_secret(name='sekret')
        with self.mock_func('show_secret', return_value=None):
            with self.mock_func('create_secret', return_value=secret):
                actual = kubernetes.secret_present(name='sekret')
                self.assertDictEqual(
                    {
                        'changes': {'data': []},
                        'result': True,
                        'name': 'sekret',
                        'comment': '',
                    },
                    actual,
                )

    def test_secret_present__create_test_true(self):
        # Secret exists and gets replaced with test=True
        secret = self.make_secret(name='sekret')
        with self.mock_func('show_secret', return_value=None):
            with self.mock_func('create_secret', return_value=secret, test=True):
                actual = kubernetes.secret_present(name='sekret')
                self.assertDictEqual(
                    {
                        'changes': {},
                        'result': None,
                        'name': 'sekret',
                        'comment': 'The secret is going to be created',
                    },
                    actual,
                )
