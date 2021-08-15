"""
Wrap the saltcheck module to copy files to ssh minion before running tests
"""

import logging
import os
import shutil
import tarfile
import tempfile
from contextlib import closing

import salt.utils.files
import salt.utils.json
import salt.utils.url

log = logging.getLogger(__name__)


def update_master_cache(states, saltenv="base"):
    """
    Replace standard saltcheck version with similar logic but replacing cp.cache_dir with
        generating files, tar'ing them up, copying tarball to remote host, extracting tar
        to state cache directory, and cleanup of files
    """
    cache = __opts__["cachedir"]
    state_cache = os.path.join(cache, "files", saltenv)

    # Setup for copying states to gendir
    gendir = tempfile.mkdtemp()
    trans_tar = salt.utils.files.mkstemp()
    if "cp.fileclient_{}".format(id(__opts__)) not in __context__:
        __context__[
            "cp.fileclient_{}".format(id(__opts__))
        ] = salt.fileclient.get_file_client(__opts__)

    # generate cp.list_states output and save to gendir
    cp_output = salt.utils.json.dumps(__salt__["cp.list_states"]())
    cp_output_file = os.path.join(gendir, "cp_output.txt")
    with salt.utils.files.fopen(cp_output_file, "w") as fp:
        fp.write(cp_output)

    # cp state directories to gendir
    already_processed = []
    sls_list = salt.utils.args.split_input(states)
    for state_name in sls_list:
        # generate low data for each state and save to gendir
        state_low_file = os.path.join(gendir, state_name + ".low")
        state_low_output = salt.utils.json.dumps(
            __salt__["state.show_low_sls"](state_name)
        )
        with salt.utils.files.fopen(state_low_file, "w") as fp:
            fp.write(state_low_output)

        state_name = state_name.replace(".", os.sep)
        if state_name in already_processed:
            log.debug("Already cached state for %s", state_name)
        else:
            file_copy_file = os.path.join(gendir, state_name + ".copy")
            log.debug("copying %s to %s", state_name, gendir)
            qualified_name = salt.utils.url.create(state_name, saltenv)
            # Duplicate cp.get_dir to gendir
            copy_result = __context__["cp.fileclient_{}".format(id(__opts__))].get_dir(
                qualified_name, gendir, saltenv
            )
            if copy_result:
                copy_result = [dir.replace(gendir, state_cache) for dir in copy_result]
                copy_result_output = salt.utils.json.dumps(copy_result)
                with salt.utils.files.fopen(file_copy_file, "w") as fp:
                    fp.write(copy_result_output)
                already_processed.append(state_name)
            else:
                # If files were not copied, assume state.file.sls was given and just copy state
                state_name = os.path.dirname(state_name)
                file_copy_file = os.path.join(gendir, state_name + ".copy")
                if state_name in already_processed:
                    log.debug("Already cached state for %s", state_name)
                else:
                    qualified_name = salt.utils.url.create(state_name, saltenv)
                    copy_result = __context__[
                        "cp.fileclient_{}".format(id(__opts__))
                    ].get_dir(qualified_name, gendir, saltenv)
                    if copy_result:
                        copy_result = [
                            dir.replace(gendir, state_cache) for dir in copy_result
                        ]
                        copy_result_output = salt.utils.json.dumps(copy_result)
                        with salt.utils.files.fopen(file_copy_file, "w") as fp:
                            fp.write(copy_result_output)
                        already_processed.append(state_name)

    # turn gendir into tarball and remove gendir
    try:
        # cwd may not exist if it was removed but salt was run from it
        cwd = os.getcwd()
    except OSError:
        cwd = None
    os.chdir(gendir)
    with closing(tarfile.open(trans_tar, "w:gz")) as tfp:
        for root, dirs, files in salt.utils.path.os_walk(gendir):
            for name in files:
                full = os.path.join(root, name)
                tfp.add(full[len(gendir) :].lstrip(os.sep))
    if cwd:
        os.chdir(cwd)
    shutil.rmtree(gendir)

    # Copy tarfile to ssh host
    single = salt.client.ssh.Single(__opts__, "", **__salt__.kwargs)
    thin_dir = __opts__["thin_dir"]
    ret = single.shell.send(trans_tar, thin_dir)

    # Clean up local tar
    try:
        os.remove(trans_tar)
    except OSError:
        pass

    tar_path = os.path.join(thin_dir, os.path.basename(trans_tar))
    # Extract remote tarball to cache directory and remove tar file
    # TODO this could be better handled by a single state/connection due to ssh overhead
    ret = __salt__["file.mkdir"](state_cache)
    ret = __salt__["archive.tar"]("xf", tar_path, dest=state_cache)
    ret = __salt__["file.remove"](tar_path)

    return ret


def run_state_tests(states, saltenv="base", check_all=False):
    """
    Define common functions to activite this wrapping module and tar copy.
    After file copies are finished, run the usual local saltcheck function
    """
    ret = update_master_cache(states, saltenv)
    ret = __salt__["saltcheck.run_state_tests_ssh"](
        states, saltenv=saltenv, check_all=check_all
    )
    return ret


def run_highstate_tests(saltenv="base"):
    """
    Lookup top files for minion, pass results to wrapped run_state_tests for copy and run
    """
    top_states = __salt__["state.show_top"]().get(saltenv)
    state_string = ",".join(top_states)
    ret = run_state_tests(state_string, saltenv)
    return ret
