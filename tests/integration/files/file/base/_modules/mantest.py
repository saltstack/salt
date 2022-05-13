"""
Helpers for testing man pages
"""

import logging
import os
import sys

import salt.utils.files
import salt.utils.path
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError
from tests.support.runtests import RUNTIME_VARS

log = logging.getLogger(__name__)


def install(rootdir):
    if not os.path.exists(rootdir):
        os.makedirs(rootdir)
    return __salt__["cmd.run_all"](
        [
            sys.executable,
            os.path.join(RUNTIME_VARS.CODE_DIR, "setup.py"),
            "install",
            "--root={}".format(rootdir),
        ],
        redirect_stderr=True,
    )


def search(manpages, rootdir):
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

    if manpage_fns:
        raise CommandExecutionError(
            "The following manpages were not found under {}: {}".format(
                rootdir, ", ".join(sorted(manpage_fns))
            )
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
                "{} not found in manpage path {}".format(path, manpage_paths[manpage])
            )

    if failed:
        raise CommandExecutionError("One or more manpages failed", info=failed)

    return True
