import platform

import pytest

import salt.utils.files


@pytest.mark.skipif(
    not any([x for x in ["ubuntu", "debian"] if x in platform.platform()]),
    reason="Test only for debian based platforms",
)
def test_adding_repo_file(states, tmp_path):
    """
    test adding a repo file using pkgrepo.managed
    """
    repo_file = str(tmp_path / "stable-binary.list")
    repo_content = "deb http://www.deb-multimedia.org stable main"
    ret = states.pkgrepo.managed(name=repo_content, file=repo_file, clean_file=True)
    with salt.utils.files.fopen(repo_file, "r") as fp:
        file_content = fp.read()
    assert file_content.strip() == repo_content


@pytest.mark.skipif(
    not any([x for x in ["ubuntu", "debian"] if x in platform.platform()]),
    reason="Test only for debian based platforms",
)
def test_adding_repo_file_arch(states, tmp_path):
    """
    test adding a repo file using pkgrepo.managed
    and setting architecture
    """
    repo_file = str(tmp_path / "stable-binary.list")
    repo_content = "deb [arch=amd64  ] http://www.deb-multimedia.org stable main"
    ret = states.pkgrepo.managed(name=repo_content, file=repo_file, clean_file=True)
    with salt.utils.files.fopen(repo_file, "r") as fp:
        file_content = fp.read()
        assert (
            file_content.strip()
            == "deb [arch=amd64] http://www.deb-multimedia.org stable main"
        )
