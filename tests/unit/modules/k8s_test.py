# Import pytohn libs
from __future__ import absolute_import
# Import Salt Testing libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
ensure_in_syspath('../../')
# from unittest import TestCase

# Import Salt execution module to test
# from salt.modules import k8s
# FIXME
import salt.modules.k8s as k8s
import json
import hashlib
import base64
import time
from subprocess import Popen, PIPE

TestCase.maxDiff = None


class TestK8SNamespace(TestCase):

    def test_get_namespaces(self):
        res = k8s.get_namespaces(apiserver_url="http://127.0.0.1:8080")
        a = len(res.get("items"))
        proc = Popen(["kubectl", "get", "namespaces", "-o", "json"], stdout=PIPE)
        kubectl_out = json.loads(proc.communicate()[0])
        b = len(kubectl_out.get("items"))
        self.assertEqual(a, b)

    def test_get_one_namespace(self):
        res = k8s.get_namespaces("default", apiserver_url="http://127.0.0.1:8080")
        a = res.get("metadata", {}).get("name", "a")
        proc = Popen(["kubectl", "get", "namespaces", "default", "-o", "json"], stdout=PIPE)
        kubectl_out = json.loads(proc.communicate()[0])
        b = kubectl_out.get("metadata", {}).get("name", "b")
        self.assertEqual(a, b)

    def test_create_namespace(self):
        hash = hashlib.sha1()
        hash.update(str(time.time()))
        nsname = hash.hexdigest()[:16]
        res = k8s.create_namespace(nsname, apiserver_url="http://127.0.0.1:8080")
        proc = Popen(["kubectl", "get", "namespaces", nsname, "-o", "json"], stdout=PIPE)
        kubectl_out = json.loads(proc.communicate()[0])
        # if creation is failed, kubernetes return non json error message
        self.assertTrue(isinstance(kubectl_out, dict))


class TestK8SSecrets(TestCase):

    def setUp(self):
        hash = hashlib.sha1()
        hash.update(str(time.time()))
        self.name = hash.hexdigest()[:16]
        data = {"testsecret": base64.encodestring("teststring")}
        self.request = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": self.name,
                "namespace": "default",
            },
            "data": data,
        }

    def test_get_secrets(self):
        res = k8s.get_secrets("default", apiserver_url="http://127.0.0.1:8080")
        a = len(res.get("items", []))
        proc = Popen(["kubectl", "--namespace=default", "get", "secrets", "-o", "json"], stdout=PIPE)
        kubectl_out = json.loads(proc.communicate()[0])
        b = len(kubectl_out.get("items", []))
        self.assertEqual(a, b)

    def test_get_one_secret(self):
        name = self.name
        filename = "/tmp/{0}.json".format(name)
        with open(filename, 'w') as f:
            json.dump(self.request, f)

        create = Popen(["kubectl", "--namespace=default", "create", "-f", filename], stdout=PIPE)
        # wee need to give kubernetes time save data in etcd
        time.sleep(0.1)
        res = k8s.get_secrets("default", name, apiserver_url="http://127.0.0.1:8080")
        a = res.get("metadata", {}).get("name", "a")
        proc = Popen(["kubectl", "--namespace=default", "get", "secrets", name, "-o", "json"], stdout=PIPE)
        kubectl_out = json.loads(proc.communicate()[0])
        b = kubectl_out.get("metadata", {}).get("name", "b")
        self.assertEqual(a, b)

    def test_get_decoded_secret(self):
        name = self.name
        filename = "/tmp/{0}.json".format(name)
        with open(filename, 'w') as f:
            json.dump(self.request, f)

        create = Popen(["kubectl", "--namespace=default", "create", "-f", filename], stdout=PIPE)
        # wee need to give etcd to populate data on all nodes
        time.sleep(0.1)
        res = k8s.get_secrets("default", name, apiserver_url="http://127.0.0.1:8080", decode=True)
        a = res.get("data", {}).get("testsecret", )
        self.assertEqual(a, "teststring")

    def test_create_secret(self):
        name = self.name
        names = []
        expected_data = {}
        for i in range(2):
            names.append("/tmp/{0}-{1}".format(name, i))
            with open("/tmp/{0}-{1}".format(name, i), 'w') as f:
                expected_data["{0}-{1}".format(name, i)] = base64.b64encode("{0}{1}".format(name, i))
                f.write("{0}{1}".format(name, i))
        res = k8s.create_secret("default", name, names, apiserver_url="http://127.0.0.1:8080")
        proc = Popen(["kubectl", "--namespace=default", "get", "secrets", name, "-o", "json"], stdout=PIPE)
        kubectl_out = json.loads(proc.communicate()[0])
        # if creation is failed, kubernetes return non json error message
        b = kubectl_out.get("data", {})
        self.assertTrue(isinstance(kubectl_out, dict))
        self.assertEqual(expected_data, b)

    def test_update_secret(self):
        name = self.name
        filename = "/tmp/{0}.json".format(name)
        with open(filename, 'w') as f:
            json.dump(self.request, f)

        create = Popen(["kubectl", "--namespace=default", "create", "-f", filename], stdout=PIPE)
        # wee need to give kubernetes time save data in etcd
        time.sleep(0.1)
        expected_data = {}
        names = []
        for i in range(3):
            names.append("/tmp/{0}-{1}-updated".format(name, i))
            with open("/tmp/{0}-{1}-updated".format(name, i), 'w') as f:
                expected_data["{0}-{1}-updated".format(name, i)] = base64.b64encode("{0}{1}-updated".format(name, i))
                f.write("{0}{1}-updated".format(name, i))

        res = k8s.update_secret("default", name, names, apiserver_url="http://127.0.0.1:8080")
        # if creation is failed, kubernetes return non json error message
        proc = Popen(["kubectl", "--namespace=default", "get", "secrets", name, "-o", "json"], stdout=PIPE)
        kubectl_out = json.loads(proc.communicate()[0])
        # if creation is failed, kubernetes return non json error message
        b = kubectl_out.get("data", {})
        self.assertTrue(isinstance(kubectl_out, dict))
        self.assertEqual(expected_data, b)

    def test_delete_secret(self):
        name = self.name
        filename = "/tmp/{0}.json".format(name)
        with open(filename, 'w') as f:
            json.dump(self.request, f)

        create = Popen(["kubectl", "--namespace=default", "create", "-f", filename], stdout=PIPE)
        # wee need to give kubernetes time save data in etcd
        time.sleep(0.1)
        res = k8s.delete_secret("default", name, apiserver_url="http://127.0.0.1:8080")
        time.sleep(0.1)
        proc = Popen(["kubectl", "--namespace=default", "get", "secrets", name, "-o", "json"], stdout=PIPE, stderr=PIPE)
        kubectl_out, err = proc.communicate()
        # stdout is empty, stderr is showing something like "not found"
        self.assertEqual('', kubectl_out)
        self.assertEqual('Error from server: secrets "{0}" not found\n'.format(name), err)

if __name__ == '__main__':
    from integration import run_tests
    run_tests(TestK8SNamespace,
              TestK8SSecrets,
              needs_daemon=False)
