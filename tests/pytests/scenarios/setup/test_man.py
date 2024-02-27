"""
Tests for existence of manpages
"""

import os
import pprint

import pytest

import salt.utils.platform
from salt.modules.virtualenv_mod import KNOWN_BINARY_NAMES

pytestmark = [
    pytest.mark.core_test,
    pytest.mark.skip_on_windows,
    pytest.mark.skip_on_aix,
    pytest.mark.skip_initial_onedir_failure,
    pytest.mark.skip_if_binaries_missing(*KNOWN_BINARY_NAMES, check_all=False),
]


def test_man_pages(virtualenv, src_dir):
    """
    Make sure that man pages are installed
    """
    # Map filenames to search strings which should be in the manpage
    manpages = {
        "salt-cp.1": ["salt-cp Documentation", "copies files from the master"],
        "salt-cloud.1": [
            "Salt Cloud Command",
            "Provision virtual machines in the cloud",
        ],
        "salt-call.1": ["salt-call Documentation", "run module functions locally"],
        "salt-api.1": [
            "salt-api Command",
            "Start interfaces used to remotely connect",
        ],
        "salt-syndic.1": ["salt-syndic Documentation", "Salt syndic daemon"],
        "salt-ssh.1": ["salt-ssh Documentation", "executed using only SSH"],
        "salt-run.1": ["salt-run Documentation", "frontend command for executing"],
        "salt-proxy.1": ["salt-proxy Documentation", "proxies these commands"],
        "salt-minion.1": ["salt-minion Documentation", "Salt minion daemon"],
        "salt-master.1": ["salt-master Documentation", "Salt master daemon"],
        "salt-key.1": [
            "salt-key Documentation",
            "management of Salt server public keys",
        ],
        "salt.1": ["allows for commands to be executed"],
        "salt.7": ["Salt Documentation"],
        "spm.1": [
            "Salt Package Manager Command",
            "command for managing Salt packages",
        ],
    }

    with virtualenv as venv:
        rootdir = str(venv.venv_dir / "installed")
        venv.run(
            venv.venv_python,
            "setup.py",
            "install",
            f"--root={rootdir}",
            cwd=src_dir,
        )

        manpage_fns = set(manpages)
        manpage_paths = {}
        for root, _, files in os.walk(rootdir):
            if not manpage_fns:
                # All manpages found, no need to keep walking
                break
            # Using list because we will be modifying the set during iteration
            for manpage_fn in list(manpage_fns):
                if manpage_fn in files:
                    manpage_path = salt.utils.path.join(root, manpage_fn)
                    manpage_paths[manpage_fn] = manpage_path
                    manpage_fns.remove(manpage_fn)

        assert (
            not manpage_fns
        ), "The following manpages were not found under {}: {}".format(
            rootdir, ", ".join(sorted(manpage_fns))
        )

        failed = {}
        for manpage in sorted(manpages):
            with salt.utils.files.fopen(manpage_paths[manpage]) as fp_:
                contents = salt.utils.stringutils.to_unicode(fp_.read())
            # Check for search string in contents
            for search_string in manpages[manpage]:
                if search_string not in contents:
                    failed.setdefault(manpage, []).append(
                        "No match for search string '{}' found in {}".format(
                            search_string, manpage_paths[manpage]
                        )
                    )
            # Check for correct install dir
            path = "/man{}/".format(manpage.rsplit(".", 1)[-1])
            if path not in manpage_paths[manpage]:
                failed.setdefault(manpage, []).append(
                    "{} not found in manpage path {}".format(
                        path, manpage_paths[manpage]
                    )
                )

        assert not failed, "One or more manpages failed:\n{}".format(
            pprint.pformat(failed)
        )
