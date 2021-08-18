import pytest
import salt.modules.kubeadm as kubeadm
from salt.exceptions import CommandExecutionError
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class KubeAdmTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.kubeadm
    """

    def setup_loader_modules(self):
        return {kubeadm: {"__salt__": {}, "__utils__": {}}}

    def test_version(self):
        """
        Test kuebadm.version without parameters
        """
        version = '{"clientVersion":{"major":"1"}}'
        salt_mock = {
            "cmd.run_stdout": MagicMock(return_value=version),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.version() == {"clientVersion": {"major": "1"}}
            salt_mock["cmd.run_stdout"].assert_called_with(
                ["kubeadm", "version", "--output", "json"]
            )

    def test_version_params(self):
        """
        Test kuebadm.version with parameters
        """
        version = '{"clientVersion":{"major":"1"}}'
        salt_mock = {
            "cmd.run_stdout": MagicMock(return_value=version),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.version(kubeconfig="/kube.cfg", rootfs="/mnt") == {
                "clientVersion": {"major": "1"}
            }
            salt_mock["cmd.run_stdout"].assert_called_with(
                [
                    "kubeadm",
                    "version",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                    "--output",
                    "json",
                ]
            )

    def test_token_create(self):
        """
        Test kuebadm.token_create without parameters
        """
        result = {"retcode": 0, "stdout": "token"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.token_create() == "token"
            salt_mock["cmd.run_all"].assert_called_with(["kubeadm", "token", "create"])

    def test_token_create_params(self):
        """
        Test kuebadm.token_create with parameters
        """
        result = {"retcode": 0, "stdout": "token"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.token_create(
                    token="token",
                    config="/kubeadm.cfg",
                    description="a description",
                    groups=["g:1", "g:2"],
                    ttl="1h1m1s",
                    usages=["u1", "u2"],
                    kubeconfig="/kube.cfg",
                    rootfs="/mnt",
                )
                == "token"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "token",
                    "create",
                    "token",
                    "--config",
                    "/kubeadm.cfg",
                    "--description",
                    "a description",
                    "--groups",
                    '["g:1", "g:2"]',
                    "--ttl",
                    "1h1m1s",
                    "--usages",
                    '["u1", "u2"]',
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_token_create_error(self):
        """
        Test kuebadm.token_create error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.token_create()

    def test_token_delete(self):
        """
        Test kuebadm.token_delete without parameters
        """
        result = {"retcode": 0, "stdout": "deleted"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.token_delete("token")
            salt_mock["cmd.run_all"].assert_called_with(
                ["kubeadm", "token", "delete", "token"]
            )

    def test_token_delete_params(self):
        """
        Test kuebadm.token_delete with parameters
        """
        result = {"retcode": 0, "stdout": "deleted"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.token_delete("token", kubeconfig="/kube.cfg", rootfs="/mnt")
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "token",
                    "delete",
                    "token",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_token_delete_error(self):
        """
        Test kuebadm.token_delete error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.token_delete("token")

    def test_token_generate(self):
        """
        Test kuebadm.token_generate without parameters
        """
        result = {"retcode": 0, "stdout": "token"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.token_generate() == "token"
            salt_mock["cmd.run_all"].assert_called_with(
                ["kubeadm", "token", "generate"]
            )

    def test_token_generate_params(self):
        """
        Test kuebadm.token_generate with parameters
        """
        result = {"retcode": 0, "stdout": "token"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.token_generate(kubeconfig="/kube.cfg", rootfs="/mnt") == "token"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "token",
                    "generate",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_token_generate_error(self):
        """
        Test kuebadm.token_generate error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.token_generate()

    def test_token_empty(self):
        """
        Test kuebadm.token_list when no outout
        """
        result = {"retcode": 0, "stdout": ""}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.token_list() == []
            salt_mock["cmd.run_all"].assert_called_with(["kubeadm", "token", "list"])

    def test_token_list(self):
        """
        Test kuebadm.token_list without parameters
        """
        output = "H1  H2  H31 H32  H4\n1   2   3.1 3.2  4"
        result = {"retcode": 0, "stdout": output}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.token_list() == [
                {"h1": "1", "h2": "2", "h31 h32": "3.1 3.2", "h4": "4"}
            ]
            salt_mock["cmd.run_all"].assert_called_with(["kubeadm", "token", "list"])

    def test_token_list_multiple_lines(self):
        """
        Test kuebadm.token_list with multiple tokens
        """
        output = "H1  H2  H31 H32  H4\n1   2   3.1 3.2  4\na   b   c d      e"
        result = {"retcode": 0, "stdout": output}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.token_list() == [
                {"h1": "1", "h2": "2", "h31 h32": "3.1 3.2", "h4": "4"},
                {"h1": "a", "h2": "b", "h31 h32": "c d", "h4": "e"},
            ]

    def test_token_list_broken_lines(self):
        """
        Test kuebadm.token_list with multiple tokens, one broken
        """
        output = "H1  H2  H31 H32  H4\n1   2   3.1 3.2  4\na   b   c  d     e"
        result = {"retcode": 0, "stdout": output}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.token_list() == [
                {"h1": "1", "h2": "2", "h31 h32": "3.1 3.2", "h4": "4"}
            ]

    def test_token_list_params(self):
        """
        Test kuebadm.token_list with parameters
        """
        output = "H1  H2  H31 H32  H4\n1   2   3.1 3.2  4"
        result = {"retcode": 0, "stdout": output}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            result = kubeadm.token_list(kubeconfig="/kube.cfg", rootfs="/mnt")
            assert result == [{"h1": "1", "h2": "2", "h31 h32": "3.1 3.2", "h4": "4"}]
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "token",
                    "list",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_token_list_error(self):
        """
        Test kuebadm.token_generate error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.token_list()

    def test_alpha_certs_renew(self):
        """
        Test kuebadm.alpha_certs_renew without parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.alpha_certs_renew() == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(
                ["kubeadm", "alpha", "certs", "renew"]
            )

    def test_alpha_certs_renew_params(self):
        """
        Test kuebadm.alpha_certs_renew with parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.alpha_certs_renew(rootfs="/mnt") == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(
                ["kubeadm", "alpha", "certs", "renew", "--rootfs", "/mnt"]
            )

    def test_alpha_certs_renew_error(self):
        """
        Test kuebadm.alpha_certs_renew error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.alpha_certs_renew()

    def test_alpha_kubeconfig_user(self):
        """
        Test kuebadm.alpha_kubeconfig_user without parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.alpha_kubeconfig_user("user") == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(
                ["kubeadm", "alpha", "kubeconfig", "user", "--client-name", "user"]
            )

    def test_alpha_kubeconfig_user_params(self):
        """
        Test kuebadm.alpha_kubeconfig_user with parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.alpha_kubeconfig_user(
                    "user",
                    apiserver_advertise_address="127.0.0.1",
                    apiserver_bind_port="1234",
                    cert_dir="/pki",
                    org="org",
                    token="token",
                    rootfs="/mnt",
                )
                == "stdout"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "alpha",
                    "kubeconfig",
                    "user",
                    "--client-name",
                    "user",
                    "--apiserver-advertise-address",
                    "127.0.0.1",
                    "--apiserver-bind-port",
                    "1234",
                    "--cert-dir",
                    "/pki",
                    "--org",
                    "org",
                    "--token",
                    "token",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_alpha_kubeconfig_user_error(self):
        """
        Test kuebadm.alpha_kubeconfig_user error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.alpha_kubeconfig_user("user")

    def test_alpha_kubelet_config_download(self):
        """
        Test kuebadm.alpha_kubelet_config_download without parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.alpha_kubelet_config_download() == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(
                ["kubeadm", "alpha", "kubelet", "config", "download"]
            )

    def test_alpha_kubelet_config_download_params(self):
        """
        Test kuebadm.alpha_kubelet_config_download with parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.alpha_kubelet_config_download(
                    kubeconfig="/kube.cfg", kubelet_version="version", rootfs="/mnt"
                )
                == "stdout"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "alpha",
                    "kubelet",
                    "config",
                    "download",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--kubelet-version",
                    "version",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_alpha_kubelet_config_download_error(self):
        """
        Test kuebadm.alpha_kubelet_config_download error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.alpha_kubelet_config_download()

    def test_alpha_kubelet_config_enable_dynamic(self):
        """
        Test kuebadm.alpha_kubelet_config_enable_dynamic without parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            result = kubeadm.alpha_kubelet_config_enable_dynamic("node-1")
            assert result == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "alpha",
                    "kubelet",
                    "config",
                    "enable-dynamic",
                    "--node-name",
                    "node-1",
                ]
            )

    def test_alpha_kubelet_config_enable_dynamic_params(self):
        """
        Test kuebadm.alpha_kubelet_config_enable_dynamic with parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.alpha_kubelet_config_enable_dynamic(
                    "node-1",
                    kubeconfig="/kube.cfg",
                    kubelet_version="version",
                    rootfs="/mnt",
                )
                == "stdout"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "alpha",
                    "kubelet",
                    "config",
                    "enable-dynamic",
                    "--node-name",
                    "node-1",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--kubelet-version",
                    "version",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_alpha_kubelet_config_enable_dynamic_error(self):
        """
        Test kuebadm.alpha_kubelet_config_enable_dynamic error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.alpha_kubelet_config_enable_dynamic("node-1")

    def test_alpha_selfhosting_pivot(self):
        """
        Test kuebadm.alpha_selfhosting_pivot without parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.alpha_selfhosting_pivot() == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(
                ["kubeadm", "alpha", "selfhosting", "pivot", "--force"]
            )

    def test_alpha_selfhosting_pivot_params(self):
        """
        Test kuebadm.alpha_selfhosting_pivot with parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.alpha_selfhosting_pivot(
                    cert_dir="/pki",
                    config="/kubeadm.cfg",
                    kubeconfig="/kube.cfg",
                    store_certs_in_secrets=True,
                    rootfs="/mnt",
                )
                == "stdout"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "alpha",
                    "selfhosting",
                    "pivot",
                    "--force",
                    "--store-certs-in-secrets",
                    "--cert-dir",
                    "/pki",
                    "--config",
                    "/kubeadm.cfg",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_alpha_selfhosting_pivot_error(self):
        """
        Test kuebadm.alpha_selfhosting_pivot error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.alpha_selfhosting_pivot()

    def test_config_images_list(self):
        """
        Test kuebadm.config_images_list without parameters
        """
        result = {"retcode": 0, "stdout": "image1\nimage2\n"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.config_images_list() == ["image1", "image2"]
            salt_mock["cmd.run_all"].assert_called_with(
                ["kubeadm", "config", "images", "list"]
            )

    def test_config_images_list_params(self):
        """
        Test kuebadm.config_images_list with parameters
        """
        result = {"retcode": 0, "stdout": "image1\nimage2\n"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.config_images_list(
                    config="/kubeadm.cfg",
                    feature_gates="k=v",
                    kubernetes_version="version",
                    kubeconfig="/kube.cfg",
                    rootfs="/mnt",
                )
                == ["image1", "image2"]
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "config",
                    "images",
                    "list",
                    "--config",
                    "/kubeadm.cfg",
                    "--feature-gates",
                    "k=v",
                    "--kubernetes-version",
                    "version",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_config_images_list_error(self):
        """
        Test kuebadm.config_images_list error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.config_images_list()

    def test_config_images_pull(self):
        """
        Test kuebadm.config_images_pull without parameters
        """
        result = {
            "retcode": 0,
            "stdout": "[config/images] Pulled image1\n[config/images] Pulled image2\n",
        }
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.config_images_pull() == ["image1", "image2"]
            salt_mock["cmd.run_all"].assert_called_with(
                ["kubeadm", "config", "images", "pull"]
            )

    def test_config_images_pull_params(self):
        """
        Test kuebadm.config_images_pull with parameters
        """
        result = {
            "retcode": 0,
            "stdout": "[config/images] Pulled image1\n[config/images] Pulled image2\n",
        }
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.config_images_pull(
                    config="/kubeadm.cfg",
                    cri_socket="socket",
                    feature_gates="k=v",
                    kubernetes_version="version",
                    kubeconfig="/kube.cfg",
                    rootfs="/mnt",
                )
                == ["image1", "image2"]
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "config",
                    "images",
                    "pull",
                    "--config",
                    "/kubeadm.cfg",
                    "--cri-socket",
                    "socket",
                    "--feature-gates",
                    "k=v",
                    "--kubernetes-version",
                    "version",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_config_images_pull_error(self):
        """
        Test kuebadm.config_images_pull error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.config_images_pull()

    def test_config_migrate(self):
        """
        Test kuebadm.config_migrate without parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.config_migrate("/oldconfig.cfg") == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(
                ["kubeadm", "config", "migrate", "--old-config", "/oldconfig.cfg"]
            )

    def test_config_migrate_params(self):
        """
        Test kuebadm.config_migrate with parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.config_migrate(
                    "/oldconfig.cfg",
                    new_config="/newconfig.cfg",
                    kubeconfig="/kube.cfg",
                    rootfs="/mnt",
                )
                == "stdout"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "config",
                    "migrate",
                    "--old-config",
                    "/oldconfig.cfg",
                    "--new-config",
                    "/newconfig.cfg",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_config_migrate_error(self):
        """
        Test kuebadm.config_migrate error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.config_migrate("/oldconfig.cfg")

    def test_config_print_init_defaults(self):
        """
        Test kuebadm.config_print_init_defaults without parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.config_print_init_defaults() == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(
                ["kubeadm", "config", "print", "init-defaults"]
            )

    def test_config_print_init_defaults_params(self):
        """
        Test kuebadm.config_print_init_defaults with parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.config_print_init_defaults(
                    component_configs="component", kubeconfig="/kube.cfg", rootfs="/mnt"
                )
                == "stdout"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "config",
                    "print",
                    "init-defaults",
                    "--component-configs",
                    "component",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_config_print_init_defaults_error(self):
        """
        Test kuebadm.config_print_init_defaults error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.config_print_init_defaults()

    def test_config_print_join_defaults(self):
        """
        Test kuebadm.config_print_join_defaults without parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.config_print_join_defaults() == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(
                ["kubeadm", "config", "print", "join-defaults"]
            )

    def test_config_print_join_defaults_params(self):
        """
        Test kuebadm.config_print_join_defaults with parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.config_print_join_defaults(
                    component_configs="component", kubeconfig="/kube.cfg", rootfs="/mnt"
                )
                == "stdout"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "config",
                    "print",
                    "join-defaults",
                    "--component-configs",
                    "component",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_config_print_join_defaults_error(self):
        """
        Test kuebadm.config_print_join_defaults error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.config_print_join_defaults()

    def test_config_upload_from_file(self):
        """
        Test kuebadm.config_upload_from_file without parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.config_upload_from_file("/config.cfg") == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(
                ["kubeadm", "config", "upload", "from-file", "--config", "/config.cfg"]
            )

    def test_config_upload_from_file_params(self):
        """
        Test kuebadm.config_upload_from_file with parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.config_upload_from_file(
                    "/config.cfg", kubeconfig="/kube.cfg", rootfs="/mnt"
                )
                == "stdout"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "config",
                    "upload",
                    "from-file",
                    "--config",
                    "/config.cfg",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_config_upload_from_file_error(self):
        """
        Test kuebadm.config_upload_from_file error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.config_upload_from_file("/config.cfg")

    def test_config_upload_from_flags(self):
        """
        Test kuebadm.config_upload_from_flags without parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.config_upload_from_flags() == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(
                ["kubeadm", "config", "upload", "from-flags"]
            )

    def test_config_upload_from_flags_params(self):
        """
        Test kuebadm.config_upload_from_flags with parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.config_upload_from_flags(
                    apiserver_advertise_address="127.0.0.1",
                    apiserver_bind_port="1234",
                    apiserver_cert_extra_sans="sans",
                    cert_dir="/pki",
                    cri_socket="socket",
                    feature_gates="k=v",
                    kubernetes_version="version",
                    node_name="node-1",
                    pod_network_cidr="10.1.0.0/12",
                    service_cidr="10.2.0.0/12",
                    service_dns_domain="example.org",
                    kubeconfig="/kube.cfg",
                    rootfs="/mnt",
                )
                == "stdout"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "config",
                    "upload",
                    "from-flags",
                    "--apiserver-advertise-address",
                    "127.0.0.1",
                    "--apiserver-bind-port",
                    "1234",
                    "--apiserver-cert-extra-sans",
                    "sans",
                    "--cert-dir",
                    "/pki",
                    "--cri-socket",
                    "socket",
                    "--feature-gates",
                    "k=v",
                    "--kubernetes-version",
                    "version",
                    "--node-name",
                    "node-1",
                    "--pod-network-cidr",
                    "10.1.0.0/12",
                    "--service-cidr",
                    "10.2.0.0/12",
                    "--service-dns-domain",
                    "example.org",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_config_upload_from_flags_error(self):
        """
        Test kuebadm.config_upload_from_flags error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.config_upload_from_flags()

    def test_config_view(self):
        """
        Test kuebadm.config_view without parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.config_view() == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(["kubeadm", "config", "view"])

    def test_config_view_params(self):
        """
        Test kuebadm.config_view with parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.config_view(kubeconfig="/kube.cfg", rootfs="/mnt") == "stdout"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "config",
                    "view",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_config_view_error(self):
        """
        Test kuebadm.config_view error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.config_view()

    def test_init(self):
        """
        Test kuebadm.init without parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.init() == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(["kubeadm", "init"])

    def test_init_params(self):
        """
        Test kuebadm.init with parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.init(
                    apiserver_advertise_address="127.0.0.1",
                    apiserver_bind_port="1234",
                    apiserver_cert_extra_sans="sans",
                    cert_dir="/pki",
                    certificate_key="secret",
                    config="/config.cfg",
                    cri_socket="socket",
                    experimental_upload_certs=True,
                    feature_gates="k=v",
                    ignore_preflight_errors="all",
                    image_repository="example.org",
                    kubernetes_version="version",
                    node_name="node-1",
                    pod_network_cidr="10.1.0.0/12",
                    service_cidr="10.2.0.0/12",
                    service_dns_domain="example.org",
                    skip_certificate_key_print=True,
                    skip_phases="all",
                    skip_token_print=True,
                    token="token",
                    token_ttl="1h1m1s",
                    rootfs="/mnt",
                )
                == "stdout"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "init",
                    "--experimental-upload-certs",
                    "--skip-certificate-key-print",
                    "--skip-token-print",
                    "--apiserver-advertise-address",
                    "127.0.0.1",
                    "--apiserver-bind-port",
                    "1234",
                    "--apiserver-cert-extra-sans",
                    "sans",
                    "--cert-dir",
                    "/pki",
                    "--certificate-key",
                    "secret",
                    "--config",
                    "/config.cfg",
                    "--cri-socket",
                    "socket",
                    "--feature-gates",
                    "k=v",
                    "--ignore-preflight-errors",
                    "all",
                    "--image-repository",
                    "example.org",
                    "--kubernetes-version",
                    "version",
                    "--node-name",
                    "node-1",
                    "--pod-network-cidr",
                    "10.1.0.0/12",
                    "--service-cidr",
                    "10.2.0.0/12",
                    "--service-dns-domain",
                    "example.org",
                    "--skip-phases",
                    "all",
                    "--token",
                    "token",
                    "--token-ttl",
                    "1h1m1s",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_init_error(self):
        """
        Test kuebadm.init error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.init()

    def test_join(self):
        """
        Test kuebadm.join without parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.join() == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(["kubeadm", "join"])

    def test_join_params(self):
        """
        Test kuebadm.join with parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.join(
                    api_server_endpoint="10.160.65.165:6443",
                    apiserver_advertise_address="127.0.0.1",
                    apiserver_bind_port="1234",
                    certificate_key="secret",
                    config="/config.cfg",
                    cri_socket="socket",
                    discovery_file="/discovery.cfg",
                    discovery_token="token",
                    discovery_token_ca_cert_hash="type:value",
                    discovery_token_unsafe_skip_ca_verification=True,
                    experimental_control_plane=True,
                    ignore_preflight_errors="all",
                    node_name="node-1",
                    skip_phases="all",
                    tls_bootstrap_token="token",
                    token="token",
                    rootfs="/mnt",
                )
                == "stdout"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "join",
                    "10.160.65.165:6443",
                    "--discovery-token-unsafe-skip-ca-verification",
                    "--experimental-control-plane",
                    "--apiserver-advertise-address",
                    "127.0.0.1",
                    "--apiserver-bind-port",
                    "1234",
                    "--certificate-key",
                    "secret",
                    "--config",
                    "/config.cfg",
                    "--cri-socket",
                    "socket",
                    "--discovery-file",
                    "/discovery.cfg",
                    "--discovery-token",
                    "token",
                    "--discovery-token-ca-cert-hash",
                    "type:value",
                    "--ignore-preflight-errors",
                    "all",
                    "--node-name",
                    "node-1",
                    "--skip-phases",
                    "all",
                    "--tls-bootstrap-token",
                    "token",
                    "--token",
                    "token",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_join_error(self):
        """
        Test kuebadm.join error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.join()

    def test_reset(self):
        """
        Test kuebadm.reset without parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert kubeadm.reset() == "stdout"
            salt_mock["cmd.run_all"].assert_called_with(["kubeadm", "reset", "--force"])

    def test_reset_params(self):
        """
        Test kuebadm.reset with parameters
        """
        result = {"retcode": 0, "stdout": "stdout"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            assert (
                kubeadm.reset(
                    cert_dir="/pki",
                    cri_socket="socket",
                    ignore_preflight_errors="all",
                    kubeconfig="/kube.cfg",
                    rootfs="/mnt",
                )
                == "stdout"
            )
            salt_mock["cmd.run_all"].assert_called_with(
                [
                    "kubeadm",
                    "reset",
                    "--force",
                    "--cert-dir",
                    "/pki",
                    "--cri-socket",
                    "socket",
                    "--ignore-preflight-errors",
                    "all",
                    "--kubeconfig",
                    "/kube.cfg",
                    "--rootfs",
                    "/mnt",
                ]
            )

    def test_reset_error(self):
        """
        Test kuebadm.reset error
        """
        result = {"retcode": 1, "stderr": "error"}
        salt_mock = {
            "cmd.run_all": MagicMock(return_value=result),
        }
        with patch.dict(kubeadm.__salt__, salt_mock):
            with pytest.raises(CommandExecutionError):
                assert kubeadm.reset()
