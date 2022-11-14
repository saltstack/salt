"""
Module for managing Solaris logadm based log rotations.
"""

import logging
import shlex

import salt.utils.args
import salt.utils.decorators as decorators
import salt.utils.files
import salt.utils.stringutils

log = logging.getLogger(__name__)
default_conf = "/etc/logadm.conf"
option_toggles = {
    "-c": "copy",
    "-l": "localtime",
    "-N": "skip_missing",
}
option_flags = {
    "-A": "age",
    "-C": "count",
    "-a": "post_command",
    "-b": "pre_command",
    "-e": "mail_addr",
    "-E": "expire_command",
    "-g": "group",
    "-m": "mode",
    "-M": "rename_command",
    "-o": "owner",
    "-p": "period",
    "-P": "timestmp",
    "-R": "old_created_command",
    "-s": "size",
    "-S": "max_size",
    "-t": "template",
    "-T": "old_pattern",
    "-w": "entryname",
    "-z": "compress_count",
}


def __virtual__():
    """
    Only work on Solaris based systems
    """
    if "Solaris" in __grains__["os_family"]:
        return True
    return (
        False,
        "The logadm execution module cannot be loaded: only available on Solaris.",
    )


def _arg2opt(arg):
    """
    Turn a pass argument into the correct option
    """
    res = [o for o, a in option_toggles.items() if a == arg]
    res += [o for o, a in option_flags.items() if a == arg]
    return res[0] if res else None


def _parse_conf(conf_file=default_conf):
    """
    Parse a logadm configuration file.
    """
    ret = {}
    with salt.utils.files.fopen(conf_file, "r") as ifile:
        for line in ifile:
            line = salt.utils.stringutils.to_unicode(line).strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            splitline = line.split(" ", 1)
            ret[splitline[0]] = splitline[1]
    return ret


def _parse_options(entry, options, include_unset=True):
    """
    Parse a logadm options string
    """
    log_cfg = {}
    options = shlex.split(options)
    if not options:
        return None

    ## identifier is entry or log?
    if entry.startswith("/"):
        log_cfg["log_file"] = entry
    else:
        log_cfg["entryname"] = entry

    ## parse options
    # NOTE: we loop over the options because values may exist multiple times
    index = 0
    while index < len(options):
        # log file
        if index in [0, (len(options) - 1)] and options[index].startswith("/"):
            log_cfg["log_file"] = options[index]

        # check if toggle option
        elif options[index] in option_toggles:
            log_cfg[option_toggles[options[index]]] = True

        # check if flag option
        elif options[index] in option_flags and (index + 1) <= len(options):
            log_cfg[option_flags[options[index]]] = (
                int(options[index + 1])
                if options[index + 1].isdigit()
                else options[index + 1]
            )
            index += 1

        # unknown options
        else:
            if "additional_options" not in log_cfg:
                log_cfg["additional_options"] = []
            if " " in options[index]:
                log_cfg["dditional_options"] = "'{}'".format(options[index])
            else:
                log_cfg["additional_options"].append(options[index])

        index += 1

    ## turn additional_options into string
    if "additional_options" in log_cfg:
        log_cfg["additional_options"] = " ".join(log_cfg["additional_options"])

    ## ensure we have a log_file
    # NOTE: logadm assumes logname is a file if no log_file is given
    if "log_file" not in log_cfg and "entryname" in log_cfg:
        log_cfg["log_file"] = log_cfg["entryname"]
        del log_cfg["entryname"]

    ## include unset
    if include_unset:
        # toggle optioons
        for name in option_toggles.values():
            if name not in log_cfg:
                log_cfg[name] = False

        # flag options
        for name in option_flags.values():
            if name not in log_cfg:
                log_cfg[name] = None

    return log_cfg


def show_conf(conf_file=default_conf, name=None):
    """
    Show configuration

    conf_file : string
        path to logadm.conf, defaults to /etc/logadm.conf
    name : string
        optional show only a single entry

    CLI Example:

    .. code-block:: bash

        salt '*' logadm.show_conf
        salt '*' logadm.show_conf name=/var/log/syslog
    """
    cfg = _parse_conf(conf_file)

    # filter
    if name and name in cfg:
        return {name: cfg[name]}
    elif name:
        return {name: "not found in {}".format(conf_file)}
    else:
        return cfg


def list_conf(conf_file=default_conf, log_file=None, include_unset=False):
    """
    Show parsed configuration

    .. versionadded:: 2018.3.0

    conf_file : string
        path to logadm.conf, defaults to /etc/logadm.conf
    log_file : string
        optional show only one log file
    include_unset : boolean
        include unset flags in output

    CLI Example:

    .. code-block:: bash

        salt '*' logadm.list_conf
        salt '*' logadm.list_conf log=/var/log/syslog
        salt '*' logadm.list_conf include_unset=False
    """
    cfg = _parse_conf(conf_file)
    cfg_parsed = {}

    ## parse all options
    for entry in cfg:
        log_cfg = _parse_options(entry, cfg[entry], include_unset)
        cfg_parsed[
            log_cfg["log_file"] if "log_file" in log_cfg else log_cfg["entryname"]
        ] = log_cfg

    ## filter
    if log_file and log_file in cfg_parsed:
        return {log_file: cfg_parsed[log_file]}
    elif log_file:
        return {log_file: "not found in {}".format(conf_file)}
    else:
        return cfg_parsed


@decorators.memoize
def show_args():
    """
    Show which arguments map to which flags and options.

    .. versionadded:: 2018.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' logadm.show_args
    """
    mapping = {"flags": {}, "options": {}}
    for flag, arg in option_toggles.items():
        mapping["flags"][flag] = arg
    for option, arg in option_flags.items():
        mapping["options"][option] = arg

    return mapping


def rotate(name, pattern=None, conf_file=default_conf, **kwargs):
    """
    Set up pattern for logging.

    name : string
        alias for entryname
    pattern : string
        alias for log_file
    conf_file : string
        optional path to alternative configuration file
    kwargs : boolean|string|int
        optional additional flags and parameters

    .. note::
        ``name`` and ``pattern`` were kept for backwards compatibility reasons.

        ``name`` is an alias for the ``entryname`` argument, ``pattern`` is an alias
        for ``log_file``. These aliases will only be used if the ``entryname`` and
        ``log_file`` arguments are not passed.

        For a full list of arguments see ```logadm.show_args```.

    CLI Example:

    .. code-block:: bash

        salt '*' logadm.rotate myapplog pattern='/var/log/myapp/*.log' count=7
        salt '*' logadm.rotate myapplog log_file='/var/log/myapp/*.log' count=4 owner=myappd mode='0700'

    """
    ## cleanup kwargs
    kwargs = salt.utils.args.clean_kwargs(**kwargs)

    ## inject name into kwargs
    if "entryname" not in kwargs and name and not name.startswith("/"):
        kwargs["entryname"] = name

    ## inject pattern into kwargs
    if "log_file" not in kwargs:
        if pattern and pattern.startswith("/"):
            kwargs["log_file"] = pattern
        # NOTE: for backwards compatibility check if name is a path
        elif name and name.startswith("/"):
            kwargs["log_file"] = name

    ## build command
    log.debug("logadm.rotate - kwargs: %s", kwargs)
    command = "logadm -f {}".format(conf_file)
    for arg, val in kwargs.items():
        if arg in option_toggles.values() and val:
            command = "{} {}".format(
                command,
                _arg2opt(arg),
            )
        elif arg in option_flags.values():
            command = "{} {} {}".format(command, _arg2opt(arg), shlex.quote(str(val)))
        elif arg != "log_file":
            log.warning("Unknown argument %s, don't know how to map this!", arg)
    if "log_file" in kwargs:
        # NOTE: except from ```man logadm```
        #   If no log file name is provided on a logadm command line, the entry
        #   name is assumed to be the same as the log file name. For example,
        #   the following two lines achieve the same thing, keeping two copies
        #   of rotated log files:
        #
        #     % logadm -C2 -w mylog /my/really/long/log/file/name
        #     % logadm -C2 -w /my/really/long/log/file/name
        if "entryname" not in kwargs:
            command = "{} -w {}".format(command, shlex.quote(kwargs["log_file"]))
        else:
            command = "{} {}".format(command, shlex.quote(kwargs["log_file"]))

    log.debug("logadm.rotate - command: %s", command)
    result = __salt__["cmd.run_all"](command, python_shell=False)
    if result["retcode"] != 0:
        return dict(Error="Failed in adding log", Output=result["stderr"])

    return dict(Result="Success")


def remove(name, conf_file=default_conf):
    """
    Remove log pattern from logadm

    CLI Example:

    .. code-block:: bash

      salt '*' logadm.remove myapplog
    """
    command = "logadm -f {} -r {}".format(conf_file, name)
    result = __salt__["cmd.run_all"](command, python_shell=False)
    if result["retcode"] != 0:
        return dict(
            Error="Failure in removing log. Possibly already removed?",
            Output=result["stderr"],
        )
    return dict(Result="Success")
