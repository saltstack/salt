import logging

import pytest
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_if_binaries_missing(*KNOWN_BINARY_NAMES, check_all=False),
]


@pytest.mark.destructive_test
@pytest.mark.skip_if_not_root
def test_issue_1959_virtualenv_runas(tmp_path, state_tree, states):
    # Since we'll be creating the virtualenv under a different account, the `tmp_path` path
    # needs to be world writable
    tmp_path.chmod(0o0777)
    with pytest.helpers.create_account(create_group=True) as account:

        state_tree_dirname = account.username
        state_tree_path = state_tree / state_tree_dirname
        with pytest.helpers.temp_file(
            "requirements.txt", contents="pep8==1.3.3\n", directory=state_tree_path
        ):
            venv_dir = tmp_path / "venv"
            ret = states.virtualenv.managed(
                name=str(venv_dir),
                user=account.username,
                requirements="salt://{}/requirements.txt".format(state_tree_dirname),
            )
            assert ret.result is True

            # Lets check proper ownership
            statinfo = venv_dir.stat()
            assert statinfo.st_uid == account.info.uid


@pytest.mark.parametrize("requirement", ["pep8==1.3.3", "zope.interface==5.0.0"])
def test_issue_2594_non_invalidated_cache(tmp_path, state_tree, modules, requirement):
    state_tree_dirname = "issue-2594"
    state_tree_path = state_tree / state_tree_dirname
    with pytest.helpers.temp_file(
        "requirements.txt", contents=requirement, directory=state_tree_path
    ):
        venv_dir = tmp_path / "venv"

        # Our state template
        template = [
            "{}:".format(venv_dir),
            "  virtualenv.managed:",
            "    - system_site_packages: False",
            "    - clear: false",
            "    - requirements: salt://{}/requirements.txt".format(state_tree_dirname),
        ]

        # Let's run our state!!!
        ret = modules.state.template_str("\n".join(template))
        assert not ret.failed
        for entry in ret:
            assert entry.result is True
            assert "Created new virtualenv" in entry.comment
            assert "packages" in entry.changes
            assert "new" in entry.changes["packages"]
            assert requirement in entry.changes["packages"]["new"]

        # Let's make sure, it really got installed
        ret = modules.pip.freeze(bin_env=str(venv_dir))
        assert requirement in ret
