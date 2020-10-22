import salt.states.pkgrepo as pkgrepo
import salt.utils.platform
from tests.support.mixins import LoaderModuleMockMixin
from tests.support.mock import MagicMock, patch
from tests.support.unit import TestCase, skipIf


class PkgrepoTestCase(TestCase, LoaderModuleMockMixin):
    """
    Test cases for salt.states.pkgrepo
    """

    def setup_loader_modules(self):
        return {
            pkgrepo: {
                "__opts__": {"test": True},
                "__grains__": {"os": "", "os_family": ""},
            }
        }

    def test__normalize_repo_suse(self):
        repo = {
            "name": "repo name",
            "autorefresh": True,
            "priority": 0,
            "pkg_gpgcheck": True,
        }
        grains = {"os_family": "Suse"}
        with patch.dict(pkgrepo.__grains__, grains):
            self.assertEqual(
                pkgrepo._normalize_repo(repo),
                {"humanname": "repo name", "refresh": True, "priority": 0},
            )

    def test__normalize_key_rpm(self):
        key = {"Description": "key", "Date": "Date", "Other": "Other"}
        for os_family in ("Suse", "RedHat"):
            grains = {"os_family": os_family}
            with patch.dict(pkgrepo.__grains__, grains):
                self.assertEqual(pkgrepo._normalize_key(key), {"key": "key"})

    def test__repos_keys_migrate_drop_migrate_to_empty(self):
        src_repos = {
            "repo-1": {
                "name": "repo name 1",
                "autorefresh": True,
                "priority": 0,
                "pkg_gpgcheck": True,
            },
            "repo-2": {
                "name": "repo name 2",
                "autorefresh": True,
                "priority": 0,
                "pkg_gpgcheck": False,
            },
        }
        tgt_repos = {}

        src_keys = {
            "key1": {"Description": "key1", "Other": "Other1"},
            "key2": {"Description": "key2", "Other": "Other2"},
        }
        tgt_keys = {}

        grains = {"os_family": "Suse"}
        salt_mock = {
            "pkg.list_repos": MagicMock(side_effect=[src_repos, tgt_repos]),
            "lowpkg.list_gpg_keys": MagicMock(side_effect=[src_keys, tgt_keys]),
        }
        with patch.dict(pkgrepo.__grains__, grains), patch.dict(
            pkgrepo.__salt__, salt_mock
        ):
            self.assertEqual(
                pkgrepo._repos_keys_migrate_drop("/mnt", False, False),
                (
                    {
                        (
                            "repo-1",
                            (
                                ("humanname", "repo name 1"),
                                ("priority", 0),
                                ("refresh", True),
                            ),
                        ),
                        (
                            "repo-2",
                            (
                                ("humanname", "repo name 2"),
                                ("priority", 0),
                                ("refresh", True),
                            ),
                        ),
                    },
                    set(),
                    set(),
                    set(),
                ),
            )

    def test__repos_keys_migrate_drop_migrate_to_empty_keys(self):
        src_repos = {
            "repo-1": {
                "name": "repo name 1",
                "autorefresh": True,
                "priority": 0,
                "pkg_gpgcheck": True,
            },
            "repo-2": {
                "name": "repo name 2",
                "autorefresh": True,
                "priority": 0,
                "pkg_gpgcheck": False,
            },
        }
        tgt_repos = {}

        src_keys = {
            "key1": {"Description": "key1", "Other": "Other1"},
            "key2": {"Description": "key2", "Other": "Other2"},
        }
        tgt_keys = {}

        grains = {"os_family": "Suse"}
        salt_mock = {
            "pkg.list_repos": MagicMock(side_effect=[src_repos, tgt_repos]),
            "lowpkg.list_gpg_keys": MagicMock(side_effect=[src_keys, tgt_keys]),
        }
        with patch.dict(pkgrepo.__grains__, grains), patch.dict(
            pkgrepo.__salt__, salt_mock
        ):
            self.assertEqual(
                pkgrepo._repos_keys_migrate_drop("/mnt", True, False),
                (
                    {
                        (
                            "repo-1",
                            (
                                ("humanname", "repo name 1"),
                                ("priority", 0),
                                ("refresh", True),
                            ),
                        ),
                        (
                            "repo-2",
                            (
                                ("humanname", "repo name 2"),
                                ("priority", 0),
                                ("refresh", True),
                            ),
                        ),
                    },
                    set(),
                    {("key1", (("key", "key1"),)), ("key2", (("key", "key2"),))},
                    set(),
                ),
            )

    def test__repos_keys_migrate_drop_migrate_to_populated_no_drop(self):
        src_repos = {
            "repo-1": {
                "name": "repo name 1",
                "autorefresh": True,
                "priority": 0,
                "pkg_gpgcheck": True,
            },
            "repo-2": {
                "name": "repo name 2",
                "autorefresh": True,
                "priority": 0,
                "pkg_gpgcheck": False,
            },
        }
        tgt_repos = {
            "repo-1": {
                "name": "repo name 1",
                "autorefresh": True,
                "priority": 0,
                "pkg_gpgcheck": True,
            },
            "repo-3": {
                "name": "repo name 3",
                "autorefresh": True,
                "priority": 0,
                "pkg_gpgcheck": False,
            },
        }

        src_keys = {
            "key1": {"Description": "key1", "Other": "Other1"},
            "key2": {"Description": "key2", "Other": "Other2"},
        }
        tgt_keys = {
            "key1": {"Description": "key1", "Other": "Other1"},
            "key3": {"Description": "key3", "Other": "Other2"},
        }

        grains = {"os_family": "Suse"}
        salt_mock = {
            "pkg.list_repos": MagicMock(side_effect=[src_repos, tgt_repos]),
            "lowpkg.list_gpg_keys": MagicMock(side_effect=[src_keys, tgt_keys]),
        }
        with patch.dict(pkgrepo.__grains__, grains), patch.dict(
            pkgrepo.__salt__, salt_mock
        ):
            self.assertEqual(
                pkgrepo._repos_keys_migrate_drop("/mnt", True, False),
                (
                    {
                        (
                            "repo-2",
                            (
                                ("humanname", "repo name 2"),
                                ("priority", 0),
                                ("refresh", True),
                            ),
                        ),
                    },
                    set(),
                    {("key2", (("key", "key2"),))},
                    set(),
                ),
            )

    def test__repos_keys_migrate_drop_migrate_to_populated_drop(self):
        src_repos = {
            "repo-1": {
                "name": "repo name 1",
                "autorefresh": True,
                "priority": 0,
                "pkg_gpgcheck": True,
            },
            "repo-2": {
                "name": "repo name 2",
                "autorefresh": True,
                "priority": 0,
                "pkg_gpgcheck": False,
            },
        }
        tgt_repos = {
            "repo-1": {
                "name": "repo name 1",
                "autorefresh": True,
                "priority": 0,
                "pkg_gpgcheck": True,
            },
            "repo-3": {
                "name": "repo name 3",
                "autorefresh": True,
                "priority": 0,
                "pkg_gpgcheck": False,
            },
        }

        src_keys = {
            "key1": {"Description": "key1", "Other": "Other1"},
            "key2": {"Description": "key2", "Other": "Other2"},
        }
        tgt_keys = {
            "key1": {"Description": "key1", "Other": "Other1"},
            "key3": {"Description": "key3", "Other": "Other2"},
        }

        grains = {"os_family": "Suse"}
        salt_mock = {
            "pkg.list_repos": MagicMock(side_effect=[src_repos, tgt_repos]),
            "lowpkg.list_gpg_keys": MagicMock(side_effect=[src_keys, tgt_keys]),
        }
        with patch.dict(pkgrepo.__grains__, grains), patch.dict(
            pkgrepo.__salt__, salt_mock
        ):
            self.assertEqual(
                pkgrepo._repos_keys_migrate_drop("/mnt", True, True),
                (
                    {
                        (
                            "repo-2",
                            (
                                ("humanname", "repo name 2"),
                                ("priority", 0),
                                ("refresh", True),
                            ),
                        ),
                    },
                    {
                        (
                            "repo-3",
                            (
                                ("humanname", "repo name 3"),
                                ("priority", 0),
                                ("refresh", True),
                            ),
                        ),
                    },
                    {("key2", (("key", "key2"),))},
                    {("key3", (("key", "key3"),))},
                ),
            )

    @skipIf(salt.utils.platform.is_windows(), "Do not run on Windows")
    def test__copy_repository_to_suse(self):
        grains = {"os_family": "Suse"}
        salt_mock = {"file.copy": MagicMock()}
        with patch.dict(pkgrepo.__grains__, grains), patch.dict(
            pkgrepo.__salt__, salt_mock
        ):
            pkgrepo._copy_repository_to("/mnt")
            salt_mock["file.copy"].assert_called_with(
                src="/etc/zypp/repos.d", dst="/mnt/etc/zypp/repos.d", recurse=True
            )

    def test_migrated_non_supported_platform(self):
        grains = {"os_family": "Debian"}
        with patch.dict(pkgrepo.__grains__, grains):
            self.assertEqual(
                pkgrepo.migrated("/mnt"),
                {
                    "name": "/mnt",
                    "result": False,
                    "changes": {},
                    "comment": "Migration not supported for this platform",
                },
            )

    def test_migrated_missing_keys_api(self):
        grains = {"os_family": "Suse"}
        with patch.dict(pkgrepo.__grains__, grains):
            self.assertEqual(
                pkgrepo.migrated("/mnt"),
                {
                    "name": "/mnt",
                    "result": False,
                    "changes": {},
                    "comment": "Keys cannot be migrated for this platform",
                },
            )

    def test_migrated_wrong_method(self):
        grains = {"os_family": "Suse"}
        salt_mock = {
            "lowpkg.import_gpg_key": True,
        }
        with patch.dict(pkgrepo.__grains__, grains), patch.dict(
            pkgrepo.__salt__, salt_mock
        ):
            self.assertEqual(
                pkgrepo.migrated("/mnt", method="magic"),
                {
                    "name": "/mnt",
                    "result": False,
                    "changes": {},
                    "comment": "Migration method not supported",
                },
            )

    @patch("salt.states.pkgrepo._repos_keys_migrate_drop")
    def test_migrated_empty(self, _repos_keys_migrate_drop):
        _repos_keys_migrate_drop.return_value = (set(), set(), set(), set())

        grains = {"os_family": "Suse"}
        salt_mock = {
            "lowpkg.import_gpg_key": True,
        }
        with patch.dict(pkgrepo.__grains__, grains), patch.dict(
            pkgrepo.__salt__, salt_mock
        ):
            self.assertEqual(
                pkgrepo.migrated("/mnt"),
                {
                    "name": "/mnt",
                    "result": True,
                    "changes": {},
                    "comment": "Repositories are already migrated",
                },
            )

    @patch("salt.states.pkgrepo._repos_keys_migrate_drop")
    def test_migrated(self, _repos_keys_migrate_drop):
        _repos_keys_migrate_drop.side_effect = [
            (
                {
                    (
                        "repo-1",
                        (
                            ("humanname", "repo name 1"),
                            ("priority", 0),
                            ("refresh", True),
                        ),
                    ),
                },
                {
                    (
                        "repo-2",
                        (
                            ("humanname", "repo name 2"),
                            ("priority", 0),
                            ("refresh", True),
                        ),
                    ),
                },
                {("key1", (("key", "key1"),))},
                {("key2", (("key", "key2"),))},
            ),
            (set(), set(), set(), set()),
        ]

        grains = {"os_family": "Suse"}
        opts = {"test": False}
        salt_mock = {
            "pkg.mod_repo": MagicMock(),
            "pkg.del_repo": MagicMock(),
            "lowpkg.import_gpg_key": MagicMock(),
            "lowpkg.remove_gpg_key": MagicMock(),
        }
        with patch.dict(pkgrepo.__grains__, grains), patch.dict(
            pkgrepo.__opts__, opts
        ), patch.dict(pkgrepo.__salt__, salt_mock):
            self.assertEqual(
                pkgrepo.migrated("/mnt", True, True),
                {
                    "name": "/mnt",
                    "result": True,
                    "changes": {
                        "repos migrated": ["repo-1"],
                        "repos dropped": ["repo-2"],
                        "keys migrated": ["key1"],
                        "keys dropped": ["key2"],
                    },
                    "comment": "Repositories synchronized",
                },
            )
            salt_mock["pkg.mod_repo"].assert_called_with(
                "repo-1", humanname="repo name 1", priority=0, refresh=True, root="/mnt"
            )
            salt_mock["pkg.del_repo"].assert_called_with("repo-2", root="/mnt")
            salt_mock["lowpkg.import_gpg_key"].assert_called_with("key1", root="/mnt")
            salt_mock["lowpkg.remove_gpg_key"].assert_called_with("key2", root="/mnt")

    @patch("salt.states.pkgrepo._repos_keys_migrate_drop")
    def test_migrated_test(self, _repos_keys_migrate_drop):
        _repos_keys_migrate_drop.return_value = (
            {
                (
                    "repo-1",
                    (("humanname", "repo name 1"), ("priority", 0), ("refresh", True)),
                ),
            },
            {
                (
                    "repo-2",
                    (("humanname", "repo name 2"), ("priority", 0), ("refresh", True)),
                ),
            },
            {("key1", (("key", "key1"),))},
            {("key2", (("key", "key2"),))},
        )

        grains = {"os_family": "Suse"}
        opts = {"test": True}
        salt_mock = {
            "lowpkg.import_gpg_key": True,
        }
        with patch.dict(pkgrepo.__grains__, grains), patch.dict(
            pkgrepo.__opts__, opts
        ), patch.dict(pkgrepo.__salt__, salt_mock):
            self.assertEqual(
                pkgrepo.migrated("/mnt", True, True),
                {
                    "name": "/mnt",
                    "result": None,
                    "changes": {
                        "repos to migrate": ["repo-1"],
                        "repos to drop": ["repo-2"],
                        "keys to migrate": ["key1"],
                        "keys to drop": ["key2"],
                    },
                    "comment": "There are keys or repositories to migrate or drop",
                },
            )
