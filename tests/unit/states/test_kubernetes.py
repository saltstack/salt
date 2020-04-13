# -*- coding: utf-8 -*-
"""
    :codeauthor: :email:`Jeff Schroeder <jeffschroeder@computer.org>`
"""
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

import base64
from contextlib import contextmanager

# Import Salt Libs
import salt.utils.stringutils
from salt.ext import six
from salt.states import kubernetes

# Import Salt Testing Libs
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf


@skipIf(
    kubernetes is False,
    "Probably Kubernetes client lib is not installed. \
                              Skipping test_kubernetes.py",
)
class KubernetesTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.kubernetes
    """

    def setup_loader_modules(self):
        return {kubernetes: {"__env__": "base"}}

    @contextmanager
    def mock_func(self, func_name, return_value, test=False):
        """
        Mock any of the kubernetes state function return values and set
        the test options.
        """
        name = "kubernetes.{0}".format(func_name)
        mocked = {name: MagicMock(return_value=return_value)}
        with patch.dict(kubernetes.__salt__, mocked) as patched:
            with patch.dict(kubernetes.__opts__, {"test": test}):
                yield patched

    def make_configmap(self, name, namespace="default", data=None):
        return self.make_ret_dict(
            kind="ConfigMap", name=name, namespace=namespace, data=data,
        )

    def make_secret(self, name, namespace="default", data=None):
        secret_data = self.make_ret_dict(
            kind="Secret", name=name, namespace=namespace, data=data,
        )
        # Base64 all of the values just like kubectl does
        for key, value in six.iteritems(secret_data["data"]):
            secret_data["data"][key] = base64.b64encode(
                salt.utils.stringutils.to_bytes(value)
            )

        return secret_data

    def make_node_labels(self, name="minikube"):
        return {
            "kubernetes.io/hostname": name,
            "beta.kubernetes.io/os": "linux",
            "beta.kubernetes.io/arch": "amd64",
            "failure-domain.beta.kubernetes.io/region": "us-west-1",
        }

    def make_node(self, name="minikube"):
        node_data = self.make_ret_dict(kind="Node", name="minikube")
        node_data.update(
            {
                "api_version": "v1",
                "kind": "Node",
                "metadata": {
                    "annotations": {"node.alpha.kubernetes.io/ttl": "0"},
                    "labels": self.make_node_labels(name=name),
                    "name": name,
                    "namespace": None,
                    "self_link": "/api/v1/nodes/{name}".format(name=name),
                    "uid": "7811b8ae-c1a1-11e7-a55a-0800279fb61e",
                },
                "spec": {"external_id": name},
                "status": {},
            }
        )
        return node_data

    def make_namespace(self, name="default"):
        namespace_data = self.make_ret_dict(kind="Namespace", name=name)
        del namespace_data["data"]
        namespace_data.update(
            {
                "status": {"phase": "Active"},
                "spec": {"finalizers": ["kubernetes"]},
                "metadata": {
                    "name": name,
                    "namespace": None,
                    "labels": None,
                    "self_link": "/api/v1/namespaces/{namespace}".format(
                        namespace=name,
                    ),
                    "annotations": None,
                    "uid": "752fceeb-c1a1-11e7-a55a-0800279fb61e",
                },
            }
        )
        return namespace_data

    def make_ret_dict(self, kind, name, namespace=None, data=None):
        """
        Make a minimal example configmap or secret for using in mocks
        """

        assert kind in ("Secret", "ConfigMap", "Namespace", "Node")

        if data is None:
            data = {}

        self_link = "/api/v1/namespaces/{namespace}/{kind}s/{name}".format(
            namespace=namespace, kind=kind.lower(), name=name,
        )

        return_data = {
            "kind": kind,
            "data": data,
            "api_version": "v1",
            "metadata": {
                "name": name,
                "labels": None,
                "namespace": namespace,
                "self_link": self_link,
                "annotations": {"kubernetes.io/change-cause": "salt-call state.apply"},
            },
        }
        return return_data

    def test_configmap_present__fail(self):
        error = kubernetes.configmap_present(
            name="testme", data={1: 1}, source="salt://beyond/oblivion.jinja",
        )
        self.assertDictEqual(
            {
                "changes": {},
                "result": False,
                "name": "testme",
                "comment": "'source' cannot be used in combination with 'data'",
            },
            error,
        )

    def test_configmap_present__create_test_true(self):
        # Create a new configmap with test=True
        with self.mock_func("show_configmap", return_value=None, test=True):
            ret = kubernetes.configmap_present(
                name="example", data={"example.conf": "# empty config file"},
            )
            self.assertDictEqual(
                {
                    "comment": "The configmap is going to be created",
                    "changes": {},
                    "name": "example",
                    "result": None,
                },
                ret,
            )

    def test_configmap_present__create(self):
        # Create a new configmap
        with self.mock_func("show_configmap", return_value=None):
            cm = self.make_configmap(
                name="test", namespace="default", data={"foo": "bar"},
            )
            with self.mock_func("create_configmap", return_value=cm):
                actual = kubernetes.configmap_present(name="test", data={"foo": "bar"},)
                self.assertDictEqual(
                    {
                        "comment": "",
                        "changes": {"data": {"foo": "bar"}},
                        "name": "test",
                        "result": True,
                    },
                    actual,
                )

    def test_configmap_present__create_no_data(self):
        # Create a new configmap with no 'data' attribute
        with self.mock_func("show_configmap", return_value=None):
            cm = self.make_configmap(name="test", namespace="default",)
            with self.mock_func("create_configmap", return_value=cm):
                actual = kubernetes.configmap_present(name="test")
                self.assertDictEqual(
                    {
                        "comment": "",
                        "changes": {"data": {}},
                        "name": "test",
                        "result": True,
                    },
                    actual,
                )

    def test_configmap_present__replace_test_true(self):
        cm = self.make_configmap(
            name="settings",
            namespace="saltstack",
            data={"foobar.conf": "# Example configuration"},
        )
        with self.mock_func("show_configmap", return_value=cm, test=True):
            ret = kubernetes.configmap_present(
                name="settings",
                namespace="saltstack",
                data={"foobar.conf": "# Example configuration"},
            )
            self.assertDictEqual(
                {
                    "comment": "The configmap is going to be replaced",
                    "changes": {},
                    "name": "settings",
                    "result": None,
                },
                ret,
            )

    def test_configmap_present__replace(self):
        cm = self.make_configmap(name="settings", data={"action": "make=war"})
        # Replace an existing configmap
        with self.mock_func("show_configmap", return_value=cm):
            new_cm = cm.copy()
            new_cm.update({"data": {"action": "make=peace"}})
            with self.mock_func("replace_configmap", return_value=new_cm):
                actual = kubernetes.configmap_present(
                    name="settings", data={"action": "make=peace"},
                )
                self.assertDictEqual(
                    {
                        "comment": "The configmap is already present. Forcing recreation",
                        "changes": {"data": {"action": "make=peace"}},
                        "name": "settings",
                        "result": True,
                    },
                    actual,
                )

    def test_configmap_absent__noop_test_true(self):
        # Nothing to delete with test=True
        with self.mock_func("show_configmap", return_value=None, test=True):
            actual = kubernetes.configmap_absent(name="NOT_FOUND")
            self.assertDictEqual(
                {
                    "comment": "The configmap does not exist",
                    "changes": {},
                    "name": "NOT_FOUND",
                    "result": None,
                },
                actual,
            )

    def test_configmap_absent__test_true(self):
        # Configmap exists with test=True
        cm = self.make_configmap(name="deleteme", namespace="default")
        with self.mock_func("show_configmap", return_value=cm, test=True):
            actual = kubernetes.configmap_absent(name="deleteme")
            self.assertDictEqual(
                {
                    "comment": "The configmap is going to be deleted",
                    "changes": {},
                    "name": "deleteme",
                    "result": None,
                },
                actual,
            )

    def test_configmap_absent__noop(self):
        # Nothing to delete
        with self.mock_func("show_configmap", return_value=None):
            actual = kubernetes.configmap_absent(name="NOT_FOUND")
            self.assertDictEqual(
                {
                    "comment": "The configmap does not exist",
                    "changes": {},
                    "name": "NOT_FOUND",
                    "result": True,
                },
                actual,
            )

    def test_configmap_absent(self):
        # Configmap exists, delete it!
        cm = self.make_configmap(name="deleteme", namespace="default")
        with self.mock_func("show_configmap", return_value=cm):
            # The return from this module isn't used in the state
            with self.mock_func("delete_configmap", return_value={}):
                actual = kubernetes.configmap_absent(name="deleteme")
                self.assertDictEqual(
                    {
                        "comment": "ConfigMap deleted",
                        "changes": {
                            "kubernetes.configmap": {
                                "new": "absent",
                                "old": "present",
                            },
                        },
                        "name": "deleteme",
                        "result": True,
                    },
                    actual,
                )

    def test_secret_present__fail(self):
        actual = kubernetes.secret_present(
            name="sekret", data={"password": "monk3y"}, source="salt://nope.jinja",
        )
        self.assertDictEqual(
            {
                "changes": {},
                "result": False,
                "name": "sekret",
                "comment": "'source' cannot be used in combination with 'data'",
            },
            actual,
        )

    def test_secret_present__exists_test_true(self):
        secret = self.make_secret(name="sekret")
        new_secret = secret.copy()
        new_secret.update({"data": {"password": "uncle"}})
        # Secret exists already and needs replacing with test=True
        with self.mock_func("show_secret", return_value=secret):
            with self.mock_func("replace_secret", return_value=new_secret, test=True):
                actual = kubernetes.secret_present(
                    name="sekret", data={"password": "uncle"},
                )
                self.assertDictEqual(
                    {
                        "changes": {},
                        "result": None,
                        "name": "sekret",
                        "comment": "The secret is going to be replaced",
                    },
                    actual,
                )

    def test_secret_present__exists(self):
        # Secret exists and gets replaced
        secret = self.make_secret(name="sekret", data={"password": "booyah"})
        with self.mock_func("show_secret", return_value=secret):
            with self.mock_func("replace_secret", return_value=secret):
                actual = kubernetes.secret_present(
                    name="sekret", data={"password": "booyah"},
                )
                self.assertDictEqual(
                    {
                        "changes": {"data": ["password"]},
                        "result": True,
                        "name": "sekret",
                        "comment": "The secret is already present. Forcing recreation",
                    },
                    actual,
                )

    def test_secret_present__create(self):
        # Secret exists and gets replaced
        secret = self.make_secret(name="sekret", data={"password": "booyah"})
        with self.mock_func("show_secret", return_value=None):
            with self.mock_func("create_secret", return_value=secret):
                actual = kubernetes.secret_present(
                    name="sekret", data={"password": "booyah"},
                )
                self.assertDictEqual(
                    {
                        "changes": {"data": ["password"]},
                        "result": True,
                        "name": "sekret",
                        "comment": "",
                    },
                    actual,
                )

    def test_secret_present__create_no_data(self):
        # Secret exists and gets replaced
        secret = self.make_secret(name="sekret")
        with self.mock_func("show_secret", return_value=None):
            with self.mock_func("create_secret", return_value=secret):
                actual = kubernetes.secret_present(name="sekret")
                self.assertDictEqual(
                    {
                        "changes": {"data": []},
                        "result": True,
                        "name": "sekret",
                        "comment": "",
                    },
                    actual,
                )

    def test_secret_present__create_test_true(self):
        # Secret exists and gets replaced with test=True
        secret = self.make_secret(name="sekret")
        with self.mock_func("show_secret", return_value=None):
            with self.mock_func("create_secret", return_value=secret, test=True):
                actual = kubernetes.secret_present(name="sekret")
                self.assertDictEqual(
                    {
                        "changes": {},
                        "result": None,
                        "name": "sekret",
                        "comment": "The secret is going to be created",
                    },
                    actual,
                )

    def test_secret_absent__noop_test_true(self):
        with self.mock_func("show_secret", return_value=None, test=True):
            actual = kubernetes.secret_absent(name="sekret")
            self.assertDictEqual(
                {
                    "changes": {},
                    "result": None,
                    "name": "sekret",
                    "comment": "The secret does not exist",
                },
                actual,
            )

    def test_secret_absent__noop(self):
        with self.mock_func("show_secret", return_value=None):
            actual = kubernetes.secret_absent(name="passwords")
            self.assertDictEqual(
                {
                    "changes": {},
                    "result": True,
                    "name": "passwords",
                    "comment": "The secret does not exist",
                },
                actual,
            )

    def test_secret_absent__delete_test_true(self):
        secret = self.make_secret(name="credentials", data={"redis": "letmein"})
        with self.mock_func("show_secret", return_value=secret):
            with self.mock_func("delete_secret", return_value=secret, test=True):
                actual = kubernetes.secret_absent(name="credentials")
                self.assertDictEqual(
                    {
                        "changes": {},
                        "result": None,
                        "name": "credentials",
                        "comment": "The secret is going to be deleted",
                    },
                    actual,
                )

    def test_secret_absent__delete(self):
        secret = self.make_secret(name="foobar", data={"redis": "letmein"})
        deleted = {
            "status": None,
            "kind": "Secret",
            "code": None,
            "reason": None,
            "details": None,
            "message": None,
            "api_version": "v1",
            "metadata": {
                "self_link": "/api/v1/namespaces/default/secrets/foobar",
                "resource_version": "30292",
            },
        }
        with self.mock_func("show_secret", return_value=secret):
            with self.mock_func("delete_secret", return_value=deleted):
                actual = kubernetes.secret_absent(name="foobar")
                self.assertDictEqual(
                    {
                        "changes": {
                            "kubernetes.secret": {"new": "absent", "old": "present"},
                        },
                        "result": True,
                        "name": "foobar",
                        "comment": "Secret deleted",
                    },
                    actual,
                )

    def test_node_label_present__add_test_true(self):
        labels = self.make_node_labels()
        with self.mock_func("node_labels", return_value=labels, test=True):
            actual = kubernetes.node_label_present(
                name="com.zoo-animal", node="minikube", value="monkey",
            )
            self.assertDictEqual(
                {
                    "changes": {},
                    "result": None,
                    "name": "com.zoo-animal",
                    "comment": "The label is going to be set",
                },
                actual,
            )

    def test_node_label_present__add(self):
        node_data = self.make_node()
        # Remove some of the defaults to make it simpler
        node_data["metadata"]["labels"] = {
            "beta.kubernetes.io/os": "linux",
        }
        labels = node_data["metadata"]["labels"]

        with self.mock_func("node_labels", return_value=labels):
            with self.mock_func("node_add_label", return_value=node_data):
                actual = kubernetes.node_label_present(
                    name="failure-domain.beta.kubernetes.io/zone",
                    node="minikube",
                    value="us-central1-a",
                )
                self.assertDictEqual(
                    {
                        "comment": "",
                        "changes": {
                            "minikube.failure-domain.beta.kubernetes.io/zone": {
                                "new": {
                                    "failure-domain.beta.kubernetes.io/zone": "us-central1-a",
                                    "beta.kubernetes.io/os": "linux",
                                },
                                "old": {"beta.kubernetes.io/os": "linux"},
                            },
                        },
                        "name": "failure-domain.beta.kubernetes.io/zone",
                        "result": True,
                    },
                    actual,
                )

    def test_node_label_present__already_set(self):
        node_data = self.make_node()
        labels = node_data["metadata"]["labels"]
        with self.mock_func("node_labels", return_value=labels):
            with self.mock_func("node_add_label", return_value=node_data):
                actual = kubernetes.node_label_present(
                    name="failure-domain.beta.kubernetes.io/region",
                    node="minikube",
                    value="us-west-1",
                )
                self.assertDictEqual(
                    {
                        "changes": {},
                        "result": True,
                        "name": "failure-domain.beta.kubernetes.io/region",
                        "comment": "The label is already set and has the specified value",
                    },
                    actual,
                )

    def test_node_label_present__update_test_true(self):
        node_data = self.make_node()
        labels = node_data["metadata"]["labels"]
        with self.mock_func("node_labels", return_value=labels):
            with self.mock_func("node_add_label", return_value=node_data, test=True):
                actual = kubernetes.node_label_present(
                    name="failure-domain.beta.kubernetes.io/region",
                    node="minikube",
                    value="us-east-1",
                )
                self.assertDictEqual(
                    {
                        "changes": {},
                        "result": None,
                        "name": "failure-domain.beta.kubernetes.io/region",
                        "comment": "The label is going to be updated",
                    },
                    actual,
                )

    def test_node_label_present__update(self):
        node_data = self.make_node()
        # Remove some of the defaults to make it simpler
        node_data["metadata"]["labels"] = {
            "failure-domain.beta.kubernetes.io/region": "us-west-1",
        }
        labels = node_data["metadata"]["labels"]
        with self.mock_func("node_labels", return_value=labels):
            with self.mock_func("node_add_label", return_value=node_data):
                actual = kubernetes.node_label_present(
                    name="failure-domain.beta.kubernetes.io/region",
                    node="minikube",
                    value="us-east-1",
                )
                self.assertDictEqual(
                    {
                        "changes": {
                            "minikube.failure-domain.beta.kubernetes.io/region": {
                                "new": {
                                    "failure-domain.beta.kubernetes.io/region": "us-east-1"
                                },
                                "old": {
                                    "failure-domain.beta.kubernetes.io/region": "us-west-1"
                                },
                            }
                        },
                        "result": True,
                        "name": "failure-domain.beta.kubernetes.io/region",
                        "comment": "The label is already set, changing the value",
                    },
                    actual,
                )

    def test_node_label_absent__noop_test_true(self):
        labels = self.make_node_labels()
        with self.mock_func("node_labels", return_value=labels, test=True):
            actual = kubernetes.node_label_absent(
                name="non-existent-label", node="minikube",
            )
            self.assertDictEqual(
                {
                    "changes": {},
                    "result": None,
                    "name": "non-existent-label",
                    "comment": "The label does not exist",
                },
                actual,
            )

    def test_node_label_absent__noop(self):
        labels = self.make_node_labels()
        with self.mock_func("node_labels", return_value=labels):
            actual = kubernetes.node_label_absent(
                name="non-existent-label", node="minikube",
            )
            self.assertDictEqual(
                {
                    "changes": {},
                    "result": True,
                    "name": "non-existent-label",
                    "comment": "The label does not exist",
                },
                actual,
            )

    def test_node_label_absent__delete_test_true(self):
        labels = self.make_node_labels()
        with self.mock_func("node_labels", return_value=labels, test=True):
            actual = kubernetes.node_label_absent(
                name="failure-domain.beta.kubernetes.io/region", node="minikube",
            )
            self.assertDictEqual(
                {
                    "changes": {},
                    "result": None,
                    "name": "failure-domain.beta.kubernetes.io/region",
                    "comment": "The label is going to be deleted",
                },
                actual,
            )

    def test_node_label_absent__delete(self):
        node_data = self.make_node()
        labels = node_data["metadata"]["labels"].copy()

        node_data["metadata"]["labels"].pop("failure-domain.beta.kubernetes.io/region")

        with self.mock_func("node_labels", return_value=labels):
            with self.mock_func("node_remove_label", return_value=node_data):
                actual = kubernetes.node_label_absent(
                    name="failure-domain.beta.kubernetes.io/region", node="minikube",
                )
                self.assertDictEqual(
                    {
                        "result": True,
                        "changes": {
                            "kubernetes.node_label": {
                                "new": "absent",
                                "old": "present",
                            }
                        },
                        "comment": "Label removed from node",
                        "name": "failure-domain.beta.kubernetes.io/region",
                    },
                    actual,
                )

    def test_namespace_present__create_test_true(self):
        with self.mock_func("show_namespace", return_value=None, test=True):
            actual = kubernetes.namespace_present(name="saltstack")
            self.assertDictEqual(
                {
                    "changes": {},
                    "result": None,
                    "name": "saltstack",
                    "comment": "The namespace is going to be created",
                },
                actual,
            )

    def test_namespace_present__create(self):
        namespace_data = self.make_namespace(name="saltstack")
        with self.mock_func("show_namespace", return_value=None):
            with self.mock_func("create_namespace", return_value=namespace_data):
                actual = kubernetes.namespace_present(name="saltstack")
                self.assertDictEqual(
                    {
                        "changes": {"namespace": {"new": namespace_data, "old": {}}},
                        "result": True,
                        "name": "saltstack",
                        "comment": "",
                    },
                    actual,
                )

    def test_namespace_present__noop_test_true(self):
        namespace_data = self.make_namespace(name="saltstack")
        with self.mock_func("show_namespace", return_value=namespace_data, test=True):
            actual = kubernetes.namespace_present(name="saltstack")
            self.assertDictEqual(
                {
                    "changes": {},
                    "result": None,
                    "name": "saltstack",
                    "comment": "The namespace already exists",
                },
                actual,
            )

    def test_namespace_present__noop(self):
        namespace_data = self.make_namespace(name="saltstack")
        with self.mock_func("show_namespace", return_value=namespace_data):
            actual = kubernetes.namespace_present(name="saltstack")
            self.assertDictEqual(
                {
                    "changes": {},
                    "result": True,
                    "name": "saltstack",
                    "comment": "The namespace already exists",
                },
                actual,
            )

    def test_namespace_absent__noop_test_true(self):
        with self.mock_func("show_namespace", return_value=None, test=True):
            actual = kubernetes.namespace_absent(name="salt")
            self.assertDictEqual(
                {
                    "changes": {},
                    "result": None,
                    "name": "salt",
                    "comment": "The namespace does not exist",
                },
                actual,
            )

    def test_namespace_absent__noop(self):
        with self.mock_func("show_namespace", return_value=None):
            actual = kubernetes.namespace_absent(name="salt")
            self.assertDictEqual(
                {
                    "changes": {},
                    "result": True,
                    "name": "salt",
                    "comment": "The namespace does not exist",
                },
                actual,
            )

    def test_namespace_absent__delete_test_true(self):
        namespace_data = self.make_namespace(name="salt")
        with self.mock_func("show_namespace", return_value=namespace_data, test=True):
            actual = kubernetes.namespace_absent(name="salt")
            self.assertDictEqual(
                {
                    "changes": {},
                    "result": None,
                    "name": "salt",
                    "comment": "The namespace is going to be deleted",
                },
                actual,
            )

    def test_namespace_absent__delete_code_200(self):
        namespace_data = self.make_namespace(name="salt")
        deleted = namespace_data.copy()
        deleted["code"] = 200
        deleted.update({"code": 200, "message": None})
        with self.mock_func("show_namespace", return_value=namespace_data):
            with self.mock_func("delete_namespace", return_value=deleted):
                actual = kubernetes.namespace_absent(name="salt")
                self.assertDictEqual(
                    {
                        "changes": {
                            "kubernetes.namespace": {"new": "absent", "old": "present"}
                        },
                        "result": True,
                        "name": "salt",
                        "comment": "Terminating",
                    },
                    actual,
                )

    def test_namespace_absent__delete_status_terminating(self):
        namespace_data = self.make_namespace(name="salt")
        deleted = namespace_data.copy()
        deleted.update(
            {
                "code": None,
                "status": "Terminating namespace",
                "message": "Terminating this shizzzle yo",
            }
        )
        with self.mock_func("show_namespace", return_value=namespace_data):
            with self.mock_func("delete_namespace", return_value=deleted):
                actual = kubernetes.namespace_absent(name="salt")
                self.assertDictEqual(
                    {
                        "changes": {
                            "kubernetes.namespace": {"new": "absent", "old": "present"}
                        },
                        "result": True,
                        "name": "salt",
                        "comment": "Terminating this shizzzle yo",
                    },
                    actual,
                )

    def test_namespace_absent__delete_status_phase_terminating(self):
        # This is what kubernetes 1.8.0 looks like when deleting namespaces
        namespace_data = self.make_namespace(name="salt")
        deleted = namespace_data.copy()
        deleted.update(
            {"code": None, "message": None, "status": {"phase": "Terminating"}}
        )
        with self.mock_func("show_namespace", return_value=namespace_data):
            with self.mock_func("delete_namespace", return_value=deleted):
                actual = kubernetes.namespace_absent(name="salt")
                self.assertDictEqual(
                    {
                        "changes": {
                            "kubernetes.namespace": {"new": "absent", "old": "present"}
                        },
                        "result": True,
                        "name": "salt",
                        "comment": "Terminating",
                    },
                    actual,
                )

    def test_namespace_absent__delete_error(self):
        namespace_data = self.make_namespace(name="salt")
        deleted = namespace_data.copy()
        deleted.update({"code": 418, "message": "I' a teapot!", "status": None})
        with self.mock_func("show_namespace", return_value=namespace_data):
            with self.mock_func("delete_namespace", return_value=deleted):
                actual = kubernetes.namespace_absent(name="salt")
                self.assertDictEqual(
                    {
                        "changes": {},
                        "result": False,
                        "name": "salt",
                        "comment": "Something went wrong, response: {0}".format(
                            deleted,
                        ),
                    },
                    actual,
                )
