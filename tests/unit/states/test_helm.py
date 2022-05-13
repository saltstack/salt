import salt.states.helm as helm
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase


class HelmTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.modules.helm
    """

    def setup_loader_modules(self):
        return {helm: {}}

    def test_repo_managed_import_failed_repo_manage(self):
        ret = {
            "name": "state_id",
            "changes": {},
            "result": False,
            "comment": "'helm.repo_manage' modules not available on this minion.",
        }
        self.assertEqual(helm.repo_managed("state_id"), ret)

    def test_repo_managed_import_failed_repo_update(self):
        mock_helm_modules = {"helm.repo_manage": MagicMock(return_value=True)}
        with patch.dict(helm.__salt__, mock_helm_modules):
            ret = {
                "name": "state_id",
                "changes": {},
                "result": False,
                "comment": "'helm.repo_update' modules not available on this minion.",
            }
            self.assertEqual(helm.repo_managed("state_id"), ret)

    def test_repo_managed_is_testing(self):
        mock_helm_modules = {
            "helm.repo_manage": MagicMock(return_value=True),
            "helm.repo_update": MagicMock(return_value=True),
        }
        with patch.dict(helm.__salt__, mock_helm_modules):
            mock__opts__ = {"test": MagicMock(return_value=True)}
            with patch.dict(helm.__opts__, mock__opts__):
                ret = {
                    "name": "state_id",
                    "result": None,
                    "comment": "Helm repo would have been managed.",
                    "changes": {},
                }
                self.assertEqual(helm.repo_managed("state_id"), ret)

    def test_repo_managed_success(self):
        result_changes = {"added": True, "removed": True, "failed": False}
        mock_helm_modules = {
            "helm.repo_manage": MagicMock(return_value=result_changes),
            "helm.repo_update": MagicMock(return_value=True),
        }
        with patch.dict(helm.__salt__, mock_helm_modules):
            ret = {
                "name": "state_id",
                "result": True,
                "comment": "Repositories were added or removed.",
                "changes": result_changes,
            }
            self.assertEqual(helm.repo_managed("state_id"), ret)

    def test_repo_managed_success_with_update(self):
        result_changes = {"added": True, "removed": True, "failed": False}
        mock_helm_modules = {
            "helm.repo_manage": MagicMock(return_value=result_changes),
            "helm.repo_update": MagicMock(return_value=True),
        }
        result_wanted = result_changes
        result_wanted.update({"repo_update": True})
        with patch.dict(helm.__salt__, mock_helm_modules):
            ret = {
                "name": "state_id",
                "result": True,
                "comment": "Repositories were added or removed.",
                "changes": result_wanted,
            }
            self.assertEqual(helm.repo_managed("state_id"), ret)

    def test_repo_managed_failed(self):
        result_changes = {"added": True, "removed": True, "failed": True}
        mock_helm_modules = {
            "helm.repo_manage": MagicMock(return_value=result_changes),
            "helm.repo_update": MagicMock(return_value=True),
        }
        with patch.dict(helm.__salt__, mock_helm_modules):
            ret = {
                "name": "state_id",
                "result": False,
                "comment": "Failed to add or remove some repositories.",
                "changes": result_changes,
            }
            self.assertEqual(helm.repo_managed("state_id"), ret)

    def test_repo_updated_import_failed(self):
        ret = {
            "name": "state_id",
            "changes": {},
            "result": False,
            "comment": "'helm.repo_update' modules not available on this minion.",
        }
        self.assertEqual(helm.repo_updated("state_id"), ret)

    def test_repo_updated_is_testing(self):
        mock_helm_modules = {"helm.repo_update": MagicMock(return_value=True)}
        with patch.dict(helm.__salt__, mock_helm_modules):
            mock__opts__ = {"test": MagicMock(return_value=True)}
            with patch.dict(helm.__opts__, mock__opts__):
                ret = {
                    "name": "state_id",
                    "result": None,
                    "comment": "Helm repo would have been updated.",
                    "changes": {},
                }
                self.assertEqual(helm.repo_updated("state_id"), ret)

    def test_repo_updated_success(self):
        mock_helm_modules = {"helm.repo_update": MagicMock(return_value=True)}
        with patch.dict(helm.__salt__, mock_helm_modules):
            ret = {
                "name": "state_id",
                "result": True,
                "comment": "Helm repo is updated.",
                "changes": {},
            }
            self.assertEqual(helm.repo_updated("state_id"), ret)

    def test_repo_updated_failed(self):
        mock_helm_modules = {"helm.repo_update": MagicMock(return_value=False)}
        with patch.dict(helm.__salt__, mock_helm_modules):
            ret = {
                "name": "state_id",
                "result": False,
                "comment": "Failed to sync some repositories.",
                "changes": False,
            }
            self.assertEqual(helm.repo_updated("state_id"), ret)

    def test_release_present_import_failed_helm_status(self):
        ret = {
            "name": "state_id",
            "changes": {},
            "result": False,
            "comment": "'helm.status' modules not available on this minion.",
        }
        self.assertEqual(helm.release_present("state_id", "mychart"), ret)

    def test_release_present_import_failed_helm_install(self):
        mock_helm_modules = {"helm.status": MagicMock(return_value=True)}
        with patch.dict(helm.__salt__, mock_helm_modules):
            ret = {
                "name": "state_id",
                "changes": {},
                "result": False,
                "comment": "'helm.install' modules not available on this minion.",
            }
            self.assertEqual(helm.release_present("state_id", "mychart"), ret)

    def test_release_present_import_failed_helm_upgrade(self):
        mock_helm_modules = {
            "helm.status": MagicMock(return_value=True),
            "helm.install": MagicMock(return_value=True),
        }
        with patch.dict(helm.__salt__, mock_helm_modules):
            ret = {
                "name": "state_id",
                "changes": {},
                "result": False,
                "comment": "'helm.upgrade' modules not available on this minion.",
            }
            self.assertEqual(helm.release_present("state_id", "mychart"), ret)

    def test_release_present_is_testing(self):
        mock_helm_modules = {
            "helm.status": MagicMock(return_value=True),
            "helm.install": MagicMock(return_value=True),
            "helm.upgrade": MagicMock(return_value=True),
        }
        with patch.dict(helm.__salt__, mock_helm_modules):
            mock__opts__ = {"test": MagicMock(return_value=True)}
            with patch.dict(helm.__opts__, mock__opts__):
                ret = {
                    "name": "state_id",
                    "result": None,
                    "comment": "Helm release would have been installed or updated.",
                    "changes": {},
                }
                self.assertEqual(helm.release_present("state_id", "mychart"), ret)

    def test_release_absent_import_failed_helm_uninstall(self):
        ret = {
            "name": "state_id",
            "changes": {},
            "result": False,
            "comment": "'helm.uninstall' modules not available on this minion.",
        }
        self.assertEqual(helm.release_absent("state_id"), ret)

    def test_release_absent_import_failed_helm_status(self):
        mock_helm_modules = {"helm.uninstall": MagicMock(return_value=True)}
        with patch.dict(helm.__salt__, mock_helm_modules):
            ret = {
                "name": "state_id",
                "changes": {},
                "result": False,
                "comment": "'helm.status' modules not available on this minion.",
            }
            self.assertEqual(helm.release_absent("state_id"), ret)

    def test_release_absent_is_testing(self):
        mock_helm_modules = {
            "helm.status": MagicMock(return_value=True),
            "helm.uninstall": MagicMock(return_value=True),
        }
        with patch.dict(helm.__salt__, mock_helm_modules):
            mock__opts__ = {"test": MagicMock(return_value=True)}
            with patch.dict(helm.__opts__, mock__opts__):
                ret = {
                    "name": "state_id",
                    "result": None,
                    "comment": "Helm release would have been uninstalled.",
                    "changes": {},
                }
                self.assertEqual(helm.release_absent("state_id"), ret)

    def test_release_absent_success(self):
        mock_helm_modules = {
            "helm.status": MagicMock(return_value={}),
            "helm.uninstall": MagicMock(return_value=True),
        }
        with patch.dict(helm.__salt__, mock_helm_modules):
            ret = {
                "name": "state_id",
                "result": True,
                "comment": "Helm release state_id is absent.",
                "changes": {"absent": "state_id"},
            }
            self.assertEqual(helm.release_absent("state_id"), ret)

    def test_release_absent_error(self):
        mock_helm_modules = {
            "helm.status": MagicMock(return_value={}),
            "helm.uninstall": MagicMock(return_value="error"),
        }
        with patch.dict(helm.__salt__, mock_helm_modules):
            ret = {
                "name": "state_id",
                "result": False,
                "comment": "error",
                "changes": {},
            }
            self.assertEqual(helm.release_absent("state_id"), ret)
