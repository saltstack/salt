import salt.utils.files


def test_removed_installed_cycle(states, tmp_path):
    repo_file = tmp_path / "stable-binary.list"
    repo_content = "deb http://www.deb-multimedia.org stable main"
    ret = states.pkgrepo.managed(name=repo_content, file=repo_file, clean_file=True)
    with salt.utils.files.fopen(repo_file, "r") as fp:
        file_content = fp.read()
    assert file_content.strip() == repo_content
