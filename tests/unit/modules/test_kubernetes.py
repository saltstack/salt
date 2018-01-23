# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Jochen Breuer <jbreuer@suse.de>`
'''

# Import Python Libs
from __future__ import absolute_import

from contextlib import contextmanager

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.unit import TestCase, skipIf
from tests.support.mock import (
    Mock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

try:
    from salt.modules import kubernetes
except ImportError:
    kubernetes = False
if not kubernetes.HAS_LIBS:
    kubernetes = False


@contextmanager
def mock_kubernetes_library():
    """
    After fixing the bug in 1c821c0e77de58892c77d8e55386fac25e518c31,
    it caused kubernetes._cleanup() to get called for virtually every
    test, which blows up. This prevents that specific blow-up once
    """
    with patch('salt.modules.kubernetes.kubernetes') as mock_kubernetes_lib:
        mock_kubernetes_lib.client.configuration.ssl_ca_cert = ''
        mock_kubernetes_lib.client.configuration.cert_file = ''
        mock_kubernetes_lib.client.configuration.key_file = ''
        yield mock_kubernetes_lib


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(kubernetes is False, "Probably Kubernetes client lib is not installed. \
                              Skipping test_kubernetes.py")
class KubernetesTestCase(TestCase, LoaderModuleMockMixin):
    '''
    Test cases for salt.modules.kubernetes
    '''

    def setup_loader_modules(self):
        return {
            kubernetes: {
                '__salt__': {},
            }
        }

    def test_nodes(self):
        '''
        Test node listing.
        :return:
        '''
        with mock_kubernetes_library() as mock_kubernetes_lib:
            with patch.dict(kubernetes.__salt__, {'config.option': Mock(return_value="")}):
                mock_kubernetes_lib.client.CoreV1Api.return_value = Mock(
                    **{"list_node.return_value.to_dict.return_value":
                        {'items': [{'metadata': {'name': 'mock_node_name'}}]}}
                )
                self.assertEqual(kubernetes.nodes(), ['mock_node_name'])
                self.assertTrue(kubernetes.kubernetes.client.CoreV1Api().list_node().to_dict.called)

    def test_deployments(self):
        '''
        Tests deployment listing.
        :return:
        '''
        with mock_kubernetes_library() as mock_kubernetes_lib:
            with patch.dict(kubernetes.__salt__, {'config.option': Mock(return_value="")}):
                mock_kubernetes_lib.client.ExtensionsV1beta1Api.return_value = Mock(
                    **{"list_namespaced_deployment.return_value.to_dict.return_value":
                        {'items': [{'metadata': {'name': 'mock_deployment_name'}}]}}
                )
                self.assertEqual(kubernetes.deployments(), ['mock_deployment_name'])
                self.assertTrue(
                    kubernetes.kubernetes.client.ExtensionsV1beta1Api().list_namespaced_deployment().to_dict.called)

    def test_services(self):
        '''
        Tests services listing.
        :return:
        '''
        with mock_kubernetes_library() as mock_kubernetes_lib:
            with patch.dict(kubernetes.__salt__, {'config.option': Mock(return_value="")}):
                mock_kubernetes_lib.client.CoreV1Api.return_value = Mock(
                    **{"list_namespaced_service.return_value.to_dict.return_value":
                        {'items': [{'metadata': {'name': 'mock_service_name'}}]}}
                )
                self.assertEqual(kubernetes.services(), ['mock_service_name'])
                self.assertTrue(kubernetes.kubernetes.client.CoreV1Api().list_namespaced_service().to_dict.called)

    def test_pods(self):
        '''
        Tests pods listing.
        :return:
        '''
        with mock_kubernetes_library() as mock_kubernetes_lib:
            with patch.dict(kubernetes.__salt__, {'config.option': Mock(return_value="")}):
                mock_kubernetes_lib.client.CoreV1Api.return_value = Mock(
                    **{"list_namespaced_pod.return_value.to_dict.return_value":
                        {'items': [{'metadata': {'name': 'mock_pod_name'}}]}}
                )
                self.assertEqual(kubernetes.pods(), ['mock_pod_name'])
                self.assertTrue(kubernetes.kubernetes.client.CoreV1Api().
                                list_namespaced_pod().to_dict.called)

    def test_delete_deployments(self):
        '''
        Tests deployment deletion
        :return:
        '''
        with mock_kubernetes_library() as mock_kubernetes_lib:
            with patch('salt.modules.kubernetes.show_deployment', Mock(return_value=None)):
                with patch.dict(kubernetes.__salt__, {'config.option': Mock(return_value="")}):
                    mock_kubernetes_lib.client.V1DeleteOptions = Mock(return_value="")
                    mock_kubernetes_lib.client.ExtensionsV1beta1Api.return_value = Mock(
                        **{"delete_namespaced_deployment.return_value.to_dict.return_value": {'code': ''}}
                    )
                    self.assertEqual(kubernetes.delete_deployment("test"), {'code': 200})
                    self.assertTrue(
                        kubernetes.kubernetes.client.ExtensionsV1beta1Api().
                        delete_namespaced_deployment().to_dict.called)

    def test_create_deployments(self):
        '''
        Tests deployment creation.
        :return:
        '''
        with mock_kubernetes_library() as mock_kubernetes_lib:
            with patch.dict(kubernetes.__salt__, {'config.option': Mock(return_value="")}):
                mock_kubernetes_lib.client.ExtensionsV1beta1Api.return_value = Mock(
                    **{"create_namespaced_deployment.return_value.to_dict.return_value": {}}
                )
                self.assertEqual(kubernetes.create_deployment("test", "default", {}, {},
                                                              None, None, None), {})
                self.assertTrue(
                    kubernetes.kubernetes.client.ExtensionsV1beta1Api().
                    create_namespaced_deployment().to_dict.called)

    def test_setup_client_key_file(self):
        '''
        Test that the `kubernetes.client-key-file` configuration isn't overwritten
        :return:
        '''
        def settings(name, value=None):
            data = {
                'kubernetes.client-key-file': '/home/testuser/.minikube/client.key',
            }
            return data.get(name, value)

        with patch.dict(kubernetes.__salt__, {'config.option': Mock(side_effect=settings)}):
            config = kubernetes._setup_conn()
            self.assertEqual(
                settings('kubernetes.client-key-file'),
                config['key_file'],
            )

    def test_node_labels(self):
        '''
        Test kubernetes.node_labels
        :return:
        '''
        with patch('salt.modules.kubernetes.node') as mock_node:
            mock_node.return_value = {
                'metadata': {
                    'labels': {
                        'kubernetes.io/hostname': 'minikube',
                        'kubernetes.io/os': 'linux',
                    }
                }
            }
            self.assertEqual(
                kubernetes.node_labels('minikube'),
                {'kubernetes.io/hostname': 'minikube', 'kubernetes.io/os': 'linux'},
            )

    def test_adding_change_cause_annotation(self):
        '''
        Tests adding a `kubernetes.io/change-cause` annotation just like
        kubectl [apply|create|replace] --record does
        :return:
        '''
        with patch('salt.modules.kubernetes.sys.argv', ['/usr/bin/salt-call', 'state.apply']) as mock_sys:
            func = getattr(kubernetes, '__dict_to_object_meta')
            data = func(name='test-pod', namespace='test', metadata={})

            self.assertEqual(data.name, 'test-pod')
            self.assertEqual(data.namespace, 'test')
            self.assertEqual(
                data.annotations,
                {'kubernetes.io/change-cause': '/usr/bin/salt-call state.apply'}
            )

            # Ensure any specified annotations aren't overwritten
            test_metadata = {'annotations': {'kubernetes.io/change-cause': 'NOPE'}}
            data = func(name='test-pod', namespace='test', metadata=test_metadata)

            self.assertEqual(
                data.annotations,
                {'kubernetes.io/change-cause': 'NOPE'}
            )

    def test_enforce_only_strings_dict(self):
        func = getattr(kubernetes, '__enforce_only_strings_dict')
        data = {
            'unicode': 1,
            2: 2,
        }
        self.assertEqual(
            {'unicode': '1', '2': '2'},
            func(data),
        )
