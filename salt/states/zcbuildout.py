"""
Management of zc.buildout
=========================

This module is inspired from minitage's buildout maker
(https://github.com/minitage/minitage/blob/master/src/minitage/core/makers/buildout.py)

.. versionadded:: 2016.3.0

.. note::

    This state module is beta; the API is subject to change and no promise
    as to performance or functionality is yet present

Available Functions
-------------------

- built

  .. code-block:: yaml

      installed1
        buildout.installed:
          - name: /path/to/buildout

      installed2
        buildout.installed:
          - name: /path/to/buildout
          - parts:
            - a
            - b
          - python: /path/to/pythonpath/bin/python
          - unless: /bin/test_something_installed
          - onlyif: /bin/test_else_installed

"""

import logging
import sys

# Define the module's virtual name
__virtualname__ = "buildout"
log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if zc.buildout libs available
    """
    if "buildout.buildout" in __salt__:
        return __virtualname__
    return (False, "buildout module could not be loaded")


INVALID_RESPONSE = "Unexpected response from docker"
VALID_RESPONSE = ""
NOTSET = object()
MAPPING_CACHE = {}
FN_CACHE = {}


def __salt(fn):
    if fn not in FN_CACHE:
        FN_CACHE[fn] = __salt__[fn]
    return FN_CACHE[fn]


def _ret_status(
    exec_status=None, name="", comment="", result=None, quiet=False, changes=None
):
    if not changes:
        changes = {}
    if exec_status is None:
        exec_status = {}
    if exec_status:
        if result is None:
            result = exec_status["status"]
        scomment = exec_status.get("comment", None)
        if scomment:
            comment += "\n" + scomment
        out = exec_status.get("out", "")
        if not quiet:
            if out:
                if isinstance(out, str):
                    comment += "\n" + out
            outlog = exec_status.get("outlog", None)
            if outlog:
                if isinstance(outlog, str):
                    comment += "\n" + outlog
    return {
        "changes": changes,
        "result": result,
        "name": name,
        "comment": comment,
    }


def _valid(exec_status=None, name="", comment="", changes=None):
    return _ret_status(
        exec_status=exec_status,
        comment=comment,
        name=name,
        changes=changes,
        result=True,
    )


def _invalid(exec_status=None, name="", comment="", changes=None):
    return _ret_status(
        exec_status=exec_status,
        comment=comment,
        name=name,
        changes=changes,
        result=False,
    )


def installed(
    name,
    config="buildout.cfg",
    quiet=False,
    parts=None,
    user=None,
    env=(),
    buildout_ver=None,
    test_release=False,
    distribute=None,
    new_st=None,
    offline=False,
    newest=False,
    python=sys.executable,
    debug=False,
    verbose=False,
    unless=None,
    onlyif=None,
    use_vt=False,
    loglevel="debug",
    **kwargs
):
    """
    Install buildout in a specific directory

    It is a thin wrapper to modules.buildout.buildout

    name
        directory to execute in

    quiet

        do not output console & logs

    config
        buildout config to use (default: buildout.cfg)

    parts
        specific buildout parts to run

    user
        user used to run buildout as

        .. versionadded:: 2014.1.4

    env
        environment variables to set when running

    buildout_ver
        force a specific buildout version (1 | 2)

    test_release
        buildout accept test release

    new_st
        Forcing use of setuptools >= 0.7

    distribute
        use distribute over setuptools if possible

    offline
        does buildout run offline

    python
        python to use

    debug
        run buildout with -D debug flag

    onlyif
        Only execute cmd if statement on the host return 0

    unless
        Do not execute cmd if statement on the host return 0

    newest
        run buildout in newest mode

    verbose
        run buildout in verbose mode (-vvvvv)

    use_vt
        Use the new salt VT to stream output [experimental]

    loglevel
        loglevel for buildout commands
    """
    ret = {}

    if "group" in kwargs:
        log.warning("Passing 'group' is deprecated, just remove it")
    output_loglevel = kwargs.get("output_loglevel", None)
    if output_loglevel and not loglevel:
        log.warning(
            "Passing 'output_loglevel' is deprecated, please use loglevel instead"
        )
    try:
        test_release = int(test_release)
    except ValueError:
        test_release = None

    func = __salt("buildout.buildout")
    kwargs = dict(
        directory=name,
        config=config,
        parts=parts,
        runas=user,
        env=env,
        buildout_ver=buildout_ver,
        test_release=test_release,
        distribute=distribute,
        new_st=new_st,
        offline=offline,
        newest=newest,
        python=python,
        debug=debug,
        verbose=verbose,
        onlyif=onlyif,
        unless=unless,
        use_vt=use_vt,
        loglevel=loglevel,
    )
    ret.update(_ret_status(func(**kwargs), name, quiet=quiet))
    return ret
