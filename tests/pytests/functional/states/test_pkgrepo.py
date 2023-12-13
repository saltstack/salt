import platform

import pytest

import salt.utils.files


@pytest.mark.parametrize(
    "options",
    [
        "",
        "  signed-by=/foo/bar  ",
        "  trusted=yes",
        "signed-by=/foo/bar arch=amd64,i386",
        "signed-by=foo/bar trusted=yes arch=amd64",
    ],
)
@pytest.mark.skipif(
    not any([x for x in ["ubuntu", "debian"] if x in platform.platform()]),
    reason="Test only for debian based platforms",
)
def test_adding_repo_file_options(states, tmp_path, options):
    """
    test adding a repo file using pkgrepo.managed
    and maintaining the user-supplied options
    """
    repo_file = str(tmp_path / "stable-binary.list")
    option = f"[{options}] " if options != "" else ""
    expected_option = f"[{options.strip()}] " if options != "" else ""
    repo_content = f"deb {option}http://www.deb-multimedia.org stable main"
    ret = states.pkgrepo.managed(name=repo_content, file=repo_file, clean_file=True)
    with salt.utils.files.fopen(repo_file, "r") as fp:
        file_content = fp.read()
        assert (
            file_content.strip()
            == f"deb {expected_option}http://www.deb-multimedia.org stable main"
        )
