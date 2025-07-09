"""
Manages configuration files via augeas

This module requires the ``augeas`` Python module.

.. _Augeas: http://augeas.net/

.. warning::

    Minimal installations of Debian and Ubuntu have been seen to have packaging
    bugs with python-augeas, causing the augeas module to fail to import. If
    the minion has the augeas module installed, but the functions in this
    execution module fail to run due to being unavailable, first restart the
    salt-minion service. If the problem persists past that, the following
    command can be run from the master to determine what is causing the import
    to fail:

    .. code-block:: bash

        salt minion-id cmd.run 'python -c "from augeas import Augeas"'

    For affected Debian/Ubuntu hosts, installing ``libpython2.7`` has been
    known to resolve the issue.
"""

import logging
import os
import re

import salt.utils.args
import salt.utils.data
import salt.utils.stringutils
from salt.exceptions import SaltInvocationError

# Make sure augeas python interface is installed
HAS_AUGEAS = False
try:
    from augeas import Augeas as _Augeas  # pylint: disable=no-name-in-module

    HAS_AUGEAS = True
except ImportError:
    pass


log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "augeas"

METHOD_MAP = {
    "set": "set",
    "setm": "setm",
    "mv": "move",
    "move": "move",
    "ins": "insert",
    "insert": "insert",
    "rm": "remove",
    "remove": "remove",
}


def __virtual__():
    """
    Only run this module if the augeas python module is installed
    """
    if HAS_AUGEAS:
        return __virtualname__
    return (False, "Cannot load augeas_cfg module: augeas python module not installed")


def _recurmatch(path, aug):
    """
    Recursive generator providing the infrastructure for
    augtools print behavior.

    This function is based on test_augeas.py from
    Harald Hoyer <harald@redhat.com>  in the python-augeas
    repository
    """
    if path:
        clean_path = path.rstrip("/*")
        yield (clean_path, aug.get(path))

        for i in aug.match(clean_path + "/*"):
            i = i.replace("!", "\\!")  # escape some dirs
            yield from _recurmatch(i, aug)


def _lstrip_word(word, prefix):
    """
    Return a copy of the string after the specified prefix was removed
    from the beginning of the string
    """

    if str(word).startswith(prefix):
        return str(word)[len(prefix) :]
    return word


def _check_load_paths(load_path):
    """
    Checks the validity of the load_path, returns a sanitized version
    with invalid paths removed.
    """
    if load_path is None or not isinstance(load_path, str):
        return None

    _paths = []

    for _path in load_path.split(":"):
        if os.path.isabs(_path) and os.path.isdir(_path):
            _paths.append(_path)
        else:
            log.info("Invalid augeas_cfg load_path entry: %s removed", _path)

    if not _paths:
        return None

    return ":".join(_paths)


def execute(context=None, lens=None, commands=(), load_path=None):
    """
    Execute Augeas commands

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.execute /files/etc/redis/redis.conf \\
        commands='["set bind 0.0.0.0", "set maxmemory 1G"]'

    context
        The Augeas context

    lens
        The Augeas lens to use

    commands
        The Augeas commands to execute

    .. versionadded:: 2016.3.0

    load_path
        A colon-spearated list of directories that modules should be searched
        in. This is in addition to the standard load path and the directories
        in AUGEAS_LENS_LIB.
    """
    ret = {"retval": False}

    arg_map = {
        "set": (1, 2),
        "setm": (2, 3),
        "move": (2,),
        "insert": (3,),
        "remove": (1,),
    }

    def make_path(path):
        """
        Return correct path
        """
        if not context:
            return path

        if path.lstrip("/"):
            if path.startswith(context):
                return path

            path = path.lstrip("/")
            return os.path.join(context, path)
        else:
            return context

    load_path = _check_load_paths(load_path)

    flags = _Augeas.NO_MODL_AUTOLOAD if lens and context else _Augeas.NONE
    aug = _Augeas(flags=flags, loadpath=load_path)

    if lens and context:
        aug.add_transform(lens, re.sub("^/files", "", context))
        aug.load()

    for command in commands:
        try:
            # first part up to space is always the
            # command name (i.e.: set, move)
            cmd, arg = command.split(" ", 1)

            if cmd not in METHOD_MAP:
                ret["error"] = f"Command {cmd} is not supported (yet)"
                return ret

            method = METHOD_MAP[cmd]
            nargs = arg_map[method]

            parts = salt.utils.args.shlex_split(arg)

            if len(parts) not in nargs:
                err = f"{method} takes {nargs} args: {parts}"
                raise ValueError(err)
            if method == "set":
                path = make_path(parts[0])
                value = parts[1] if len(parts) == 2 else None
                args = {"path": path, "value": value}
            elif method == "setm":
                base = make_path(parts[0])
                sub = parts[1]
                value = parts[2] if len(parts) == 3 else None
                args = {"base": base, "sub": sub, "value": value}
            elif method == "move":
                path = make_path(parts[0])
                dst = parts[1]
                args = {"src": path, "dst": dst}
            elif method == "insert":
                label, where, path = parts
                if where not in ("before", "after"):
                    raise ValueError(f'Expected "before" or "after", not {where}')
                path = make_path(path)
                args = {"path": path, "label": label, "before": where == "before"}
            elif method == "remove":
                path = make_path(parts[0])
                args = {"path": path}
        except ValueError as err:
            log.error(err)
            # if command.split fails arg will not be set
            if "arg" not in locals():
                arg = command
            ret["error"] = (
                f"Invalid formatted command, see debug log for details: {arg}"
            )
            return ret

        args = salt.utils.data.decode(args, to_str=True)
        log.debug("%s: %s", method, args)

        func = getattr(aug, method)
        func(**args)

    try:
        aug.save()
        ret["retval"] = True
    except OSError as err:
        ret["error"] = str(err)

        if lens and not lens.endswith(".lns"):
            ret["error"] += (
                '\nLenses are normally configured as "name.lns". '
                'Did you mean "{}.lns"?'.format(lens)
            )

    aug.close()
    return ret


def get(path, value="", load_path=None):
    """
    Get a value for a specific augeas path

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.get /files/etc/hosts/1/ ipaddr

    path
        The path to get the value of

    value
        The optional value to get

    .. versionadded:: 2016.3.0

    load_path
        A colon-spearated list of directories that modules should be searched
        in. This is in addition to the standard load path and the directories
        in AUGEAS_LENS_LIB.
    """
    load_path = _check_load_paths(load_path)

    aug = _Augeas(loadpath=load_path)
    ret = {}

    path = path.rstrip("/")
    if value:
        path += "/{}".format(value.strip("/"))

    try:
        _match = aug.match(path)
    except RuntimeError as err:
        return {"error": str(err)}

    if _match:
        ret[path] = aug.get(path)
    else:
        ret[path] = ""  # node does not exist

    return ret


def setvalue(*args):
    """
    Set a value for a specific augeas path

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.setvalue /files/etc/hosts/1/canonical localhost

    This will set the first entry in /etc/hosts to localhost

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.setvalue /files/etc/hosts/01/ipaddr 192.168.1.1 \\
                                 /files/etc/hosts/01/canonical test

    Adds a new host to /etc/hosts the ip address 192.168.1.1 and hostname test

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.setvalue prefix=/files/etc/sudoers/ \\
                 "spec[user = '%wheel']/user" "%wheel" \\
                 "spec[user = '%wheel']/host_group/host" 'ALL' \\
                 "spec[user = '%wheel']/host_group/command[1]" 'ALL' \\
                 "spec[user = '%wheel']/host_group/command[1]/tag" 'PASSWD' \\
                 "spec[user = '%wheel']/host_group/command[2]" '/usr/bin/apt-get' \\
                 "spec[user = '%wheel']/host_group/command[2]/tag" NOPASSWD

    Ensures that the following line is present in /etc/sudoers::

        %wheel ALL = PASSWD : ALL , NOPASSWD : /usr/bin/apt-get , /usr/bin/aptitude
    """
    load_path = None
    load_paths = [x for x in args if str(x).startswith("load_path=")]
    if load_paths:
        if len(load_paths) > 1:
            raise SaltInvocationError("Only one 'load_path=' value is permitted")
        else:
            load_path = load_paths[0].split("=", 1)[1]
    load_path = _check_load_paths(load_path)

    aug = _Augeas(loadpath=load_path)
    ret = {"retval": False}

    tuples = [
        x
        for x in args
        if not str(x).startswith("prefix=") and not str(x).startswith("load_path=")
    ]
    prefix = [x for x in args if str(x).startswith("prefix=")]
    if prefix:
        if len(prefix) > 1:
            raise SaltInvocationError("Only one 'prefix=' value is permitted")
        else:
            prefix = prefix[0].split("=", 1)[1]

    if len(tuples) % 2 != 0:
        raise SaltInvocationError("Uneven number of path/value arguments")

    tuple_iter = iter(tuples)
    for path, value in zip(tuple_iter, tuple_iter):
        target_path = path
        if prefix:
            target_path = os.path.join(prefix.rstrip("/"), path.lstrip("/"))
        try:
            aug.set(target_path, str(value))
        except ValueError as err:
            ret["error"] = f"Multiple values: {err}"

    try:
        aug.save()
        ret["retval"] = True
    except OSError as err:
        ret["error"] = str(err)
    return ret


def match(path, value="", load_path=None):
    """
    Get matches for path expression

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.match /files/etc/services/service-name ssh

    path
        The path to match

    value
        The value to match on

    .. versionadded:: 2016.3.0

    load_path
        A colon-spearated list of directories that modules should be searched
        in. This is in addition to the standard load path and the directories
        in AUGEAS_LENS_LIB.
    """
    load_path = _check_load_paths(load_path)

    aug = _Augeas(loadpath=load_path)
    ret = {}

    try:
        matches = aug.match(path)
    except RuntimeError:
        return ret

    for _match in matches:
        if value and aug.get(_match) == value:
            ret[_match] = value
        elif not value:
            ret[_match] = aug.get(_match)
    return ret


def remove(path, load_path=None):
    """
    Get matches for path expression

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.remove \\
        /files/etc/sysctl.conf/net.ipv4.conf.all.log_martians

    path
        The path to remove

    .. versionadded:: 2016.3.0

    load_path
        A colon-spearated list of directories that modules should be searched
        in. This is in addition to the standard load path and the directories
        in AUGEAS_LENS_LIB.
    """
    load_path = _check_load_paths(load_path)

    aug = _Augeas(loadpath=load_path)
    ret = {"retval": False}
    try:
        count = aug.remove(path)
        aug.save()
        if count == -1:
            ret["error"] = "Invalid node"
        else:
            ret["retval"] = True
    except (RuntimeError, OSError) as err:
        ret["error"] = str(err)

    ret["count"] = count

    return ret


def ls(path, load_path=None):  # pylint: disable=C0103
    """
    List the direct children of a node

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.ls /files/etc/passwd

    path
        The path to list

    .. versionadded:: 2016.3.0

    load_path
        A colon-spearated list of directories that modules should be searched
        in. This is in addition to the standard load path and the directories
        in AUGEAS_LENS_LIB.
    """

    def _match(path):
        """Internal match function"""
        try:
            matches = aug.match(salt.utils.stringutils.to_str(path))
        except RuntimeError:
            return {}

        ret = {}
        for _ma in matches:
            ret[_ma] = aug.get(_ma)
        return ret

    load_path = _check_load_paths(load_path)

    aug = _Augeas(loadpath=load_path)

    path = path.rstrip("/") + "/"
    match_path = path + "*"

    matches = _match(match_path)
    ret = {}

    for key, value in matches.items():
        name = _lstrip_word(key, path)
        if _match(key + "/*"):
            ret[name + "/"] = value  # has sub nodes, e.g. directory
        else:
            ret[name] = value
    return ret


def tree(path, load_path=None):
    """
    Returns recursively the complete tree of a node

    CLI Example:

    .. code-block:: bash

        salt '*' augeas.tree /files/etc/

    path
        The base of the recursive listing

    .. versionadded:: 2016.3.0

    load_path
        A colon-spearated list of directories that modules should be searched
        in. This is in addition to the standard load path and the directories
        in AUGEAS_LENS_LIB.
    """
    load_path = _check_load_paths(load_path)

    aug = _Augeas(loadpath=load_path)

    path = path.rstrip("/") + "/"
    match_path = path
    return dict([i for i in _recurmatch(match_path, aug)])
