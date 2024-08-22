import pathlib


def test_bash_completion_installed(grains):
    # This test specifically checks for a regression of #66560.
    if grains.get("os_family") == "Debian":
        completions_dir = pathlib.Path("/usr/share/bash-completion/completions")
        for exec_name in ("salt", "salt-call", "salt-cp", "salt-key"):
            # Bash-completion finds the completion when it is installed as
            # <command>, <command>.bash, or _<command>, so we test all three
            # variants before failing.
            completion_file1 = completions_dir / exec_name
            completion_file2 = completions_dir / f"{exec_name}.bash"
            completion_file3 = completions_dir / f"_{exec_name}"
            assert (
                completion_file1.exists()
                or completion_file2.exists()
                or completion_file3.exists()
            )
