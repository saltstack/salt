import pathlib
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


@pytest.fixture
def key_path():
    key_file = pathlib.Path("/usr", "share", "keyrings", "salt-archive-keyring.gpg")
    assert not key_file.is_file()
    yield key_file
    key_file.unlink()


@pytest.mark.skipif(
    not any([x for x in ["ubuntu", "debian"] if x in platform.platform()]),
    reason="Test only for debian based platforms",
)
def test_adding_repo_file_signedby(grains, states, tmp_path, key_path):
    """
    Test adding a repo file using pkgrepo.managed
    and setting signedby
    """
    repo_file = str(tmp_path / "stable-binary.list")
    fullname = grains["osfullname"].lower()
    arch = grains["osarch"]
    lsb_release = grains["lsb_distrib_release"]
    key_file = "https://repo.saltproject.io/py3/{}/{}/{}/latest/salt-archive-keyring.gpg".format(
        fullname, lsb_release, arch
    )
    repo_content = "deb [arch={arch} signed-by=/usr/share/keyrings/salt-archive-keyring.gpg] https://repo.saltproject.io/py3/{}/{}/{arch}/latest {} main".format(
        fullname, lsb_release, grains["oscodename"], arch=arch
    )
    ret = states.pkgrepo.managed(
        name=repo_content,
        file=repo_file,
        clean_file=True,
        signedby=str(key_path),
        key_url=key_file,
        aptkey=False,
    )
    with salt.utils.files.fopen(repo_file, "r") as fp:
        file_content = fp.read()
        assert file_content.strip() == repo_content
    assert key_path.is_file()


@pytest.mark.skipif(
    not any([x for x in ["ubuntu", "debian"] if x in platform.platform()]),
    reason="Test only for debian based platforms",
)
def test_adding_repo_file_signedby_keyserver(grains, states, tmp_path, key_path):
    """
    Test adding a repo file using pkgrepo.managed
    and setting signedby with a keyserver
    """
    repo_file = str(tmp_path / "stable-binary.list")
    fullname = grains["osfullname"].lower()
    arch = grains["osarch"]
    lsb_release = grains["lsb_distrib_release"]
    key_file = "https://repo.saltproject.io/py3/{}/{}/{}/latest/salt-archive-keyring.gpg".format(
        fullname, lsb_release, arch
    )
    repo_content = "deb [arch={arch} signed-by=/usr/share/keyrings/salt-archive-keyring.gpg] https://repo.saltproject.io/py3/{}/{}/{arch}/latest {} main".format(
        fullname, lsb_release, grains["oscodename"], arch=arch
    )

    ret = states.pkgrepo.managed(
        name=repo_content,
        file=repo_file,
        clean_file=True,
        signedby=str(key_path),
        keyserver="keyserver.ubuntu.com",
        keyid="0E08A149DE57BFBE",
        aptkey=False,
    )
    with salt.utils.files.fopen(repo_file, "r") as fp:
        file_content = fp.read()
        assert file_content.strip() == repo_content
    assert key_path.is_file()
