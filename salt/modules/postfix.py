"""
Support for Postfix

This module is currently little more than a config file viewer and editor. It
is able to read the master.cf file (which is one style) and files in the style
of main.cf (which is a different style, that is used in multiple postfix
configuration files).

The design of this module is such that when files are edited, a minimum of
changes are made to them. Each file should look as if it has been edited by
hand; order, comments and whitespace are all preserved.
"""

import logging
import re

import salt.utils.files
import salt.utils.path
import salt.utils.stringutils

SWWS = re.compile(r"^\s")

log = logging.getLogger(__name__)

MAIN_CF = "/etc/postfix/main.cf"
MASTER_CF = "/etc/postfix/master.cf"


def __virtual__():
    """
    Only load the module if Postfix is installed
    """
    if salt.utils.path.which("postfix"):
        return True
    return (False, "postfix execution module not loaded: postfix not installed.")


def _parse_master(path=MASTER_CF):
    """
    Parse the master.cf file. This file is essentially a whitespace-delimited
    columnar file. The columns are: service, type, private (yes), unpriv (yes),
    chroot (yes), wakeup (never), maxproc (100), command + args.

    This function parses out the columns, leaving empty lines and comments
    intact. Where the value doesn't detract from the default, a dash (-) will
    be used.

    Returns a dict of the active config lines, and a list of the entire file,
    in order. These compliment each other.
    """
    with salt.utils.files.fopen(path, "r") as fh_:
        full_conf = salt.utils.stringutils.to_unicode(fh_.read())

    # Condense the file based on line continuations, but keep order, comments
    # and whitespace
    conf_list = []
    conf_dict = {}
    for line in full_conf.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            conf_list.append(line)
            continue
        comps = line.strip().split()
        conf_line = {
            "service": comps[0],
            "conn_type": comps[1],
            "private": comps[2],
            "unpriv": comps[3],
            "chroot": comps[4],
            "wakeup": comps[5],
            "maxproc": comps[6],
            "command": " ".join(comps[7:]),
        }
        dict_key = "{} {}".format(comps[0], comps[1])
        conf_list.append(conf_line)
        conf_dict[dict_key] = conf_line

    return conf_dict, conf_list


def show_master(path=MASTER_CF):
    """
    Return a dict of active config values. This does not include comments,
    spacing or order.

    The data returned from this function should not be used for direct
    modification of the main.cf file; other functions are available for that.

    CLI Examples:

    .. code-block:: bash

        salt <minion> postfix.show_master
        salt <minion> postfix.show_master path=/path/to/master.cf
    """
    conf_dict, conf_list = _parse_master(path)  # pylint: disable=W0612
    return conf_dict


def set_master(
    service,
    conn_type,
    private="y",
    unpriv="y",
    chroot="y",
    wakeup="n",
    maxproc="100",
    command="",
    write_conf=True,
    path=MASTER_CF,
):
    """
    Set a single config value in the master.cf file. If the value does not
    already exist, it will be appended to the end.

    Because of shell parsing issues, '-' cannot be set as a value, as is normal
    in the master.cf file; either 'y', 'n' or a number should be used when
    calling this function from the command line. If the value used matches the
    default, it will internally be converted to a '-'. Calling this function
    from the Python API is not affected by this limitation

    The settings and their default values, in order, are: service (required),
    conn_type (required), private (y), unpriv (y), chroot (y), wakeup (n),
    maxproc (100), command (required).

    By default, this function will write out the changes to the master.cf file,
    and then returns the full contents of the file. By setting the
    ``write_conf`` option to ``False``, it will skip writing the file.

    CLI Example:

    .. code-block:: bash

        salt <minion> postfix.set_master smtp inet n y n n 100 smtpd
    """
    conf_dict, conf_list = _parse_master(path)

    new_conf = []
    dict_key = "{} {}".format(service, conn_type)
    new_line = _format_master(
        service,
        conn_type,
        private,
        unpriv,
        chroot,
        wakeup,
        maxproc,
        command,
    )
    for line in conf_list:
        if isinstance(line, dict):
            if line["service"] == service and line["conn_type"] == conn_type:
                # This is the one line that we're changing
                new_conf.append(new_line)
            else:
                # No changes to this line, but it still needs to be
                # formatted properly
                new_conf.append(_format_master(**line))
        else:
            # This line is a comment or is empty
            new_conf.append(line)

    if dict_key not in conf_dict:
        # This config value does not exist, so append it to the end
        new_conf.append(new_line)

    if write_conf:
        _write_conf(new_conf, path)
    return "\n".join(new_conf)


def _format_master(
    service, conn_type, private, unpriv, chroot, wakeup, maxproc, command
):
    """
    Format the given values into the style of line normally used in the
    master.cf file.
    """
    # ==========================================================================
    # service type  private unpriv  chroot  wakeup  maxproc command + args
    #              (yes)   (yes)   (yes)   (never) (100)
    # ==========================================================================
    # smtp      inet  n       -       n       -       -       smtpd
    if private == "y":
        private = "-"

    if unpriv == "y":
        unpriv = "-"

    if chroot == "y":
        chroot = "-"

    if wakeup == "n":
        wakeup = "-"

    maxproc = str(maxproc)
    if maxproc == "100":
        maxproc = "-"

    conf_line = "{:9s} {:5s} {:7s} {:7s} {:7s} {:7s} {:7s} {}".format(
        service,
        conn_type,
        private,
        unpriv,
        chroot,
        wakeup,
        maxproc,
        command,
    )
    # print(conf_line)
    return conf_line


def _parse_main(path=MAIN_CF):
    """
    Parse files in the style of main.cf. This is not just a "name = value" file;
    there are other rules:

    * Comments start with #
    * Any whitespace at the beginning of a line denotes that that line is a
        continuation from the previous line.
    * The whitespace rule applies to comments.
    * Keys defined in the file may be referred to as variables further down in
        the file.
    """
    with salt.utils.files.fopen(path, "r") as fh_:
        full_conf = salt.utils.stringutils.to_unicode(fh_.read())

    # Condense the file based on line continuations, but keep order, comments
    # and whitespace
    conf_list = []
    for line in full_conf.splitlines():
        if not line.strip():
            conf_list.append(line)
            continue
        if re.match(SWWS, line):
            if not conf_list:
                # This should only happen at the top of the file
                conf_list.append(line)
                continue
            if not isinstance(conf_list[-1], str):
                conf_list[-1] = ""
            # This line is a continuation of the previous line
            conf_list[-1] = "\n".join([conf_list[-1], line])
        else:
            conf_list.append(line)

    # Extract just the actual key/value pairs
    pairs = {}
    for line in conf_list:
        if not line.strip():
            continue
        if line.startswith("#"):
            continue
        comps = line.split("=")
        pairs[comps[0].strip()] = "=".join(comps[1:]).strip()

    # Return both sets of data, they compliment each other elsewhere
    return pairs, conf_list


def show_main(path=MAIN_CF):
    """
    Return a dict of active config values. This does not include comments,
    spacing or order. Bear in mind that order is functionally important in the
    main.cf file, since keys can be referred to as variables. This means that
    the data returned from this function should not be used for direct
    modification of the main.cf file; other functions are available for that.

    CLI Examples:

    .. code-block:: bash

        salt <minion> postfix.show_main
        salt <minion> postfix.show_main path=/path/to/main.cf
    """
    pairs, conf_list = _parse_main(path)  # pylint: disable=W0612
    return pairs


def set_main(key, value, path=MAIN_CF):
    """
    Set a single config value in the main.cf file. If the value does not already
    exist, it will be appended to the end.

    CLI Example:

    .. code-block:: bash

        salt <minion> postfix.set_main mailq_path /usr/bin/mailq
    """
    pairs, conf_list = _parse_main(path)

    new_conf = []
    key_line_match = re.compile("^{}([\\s=]|$)".format(re.escape(key)))
    if key in pairs:
        for line in conf_list:
            if re.match(key_line_match, line):
                new_conf.append("{} = {}".format(key, value))
            else:
                new_conf.append(line)
    else:
        conf_list.append("{} = {}".format(key, value))
        new_conf = conf_list

    _write_conf(new_conf, path)
    return new_conf


def _write_conf(conf, path=MAIN_CF):
    """
    Write out configuration file.
    """
    with salt.utils.files.fopen(path, "w") as fh_:
        for line in conf:
            line = salt.utils.stringutils.to_str(line)
            if isinstance(line, dict):
                fh_.write(" ".join(line))
            else:
                fh_.write(line)
            fh_.write("\n")


def show_queue():
    """
    Show contents of the mail queue

    CLI Example:

    .. code-block:: bash

        salt '*' postfix.show_queue

    """
    cmd = "mailq"
    out = __salt__["cmd.run"](cmd).splitlines()
    queue = []

    queue_pattern = re.compile(
        r"(?P<queue_id>^[A-Z0-9]+)\s+(?P<size>\d+)\s(?P<timestamp>\w{3}\s\w{3}\s\d{1,2}\s\d{2}\:\d{2}\:\d{2})\s+(?P<sender>.+)"
    )
    recipient_pattern = re.compile(r"^\s+(?P<recipient>.+)")
    queue_id, size, timestamp, sender, recipient = None, None, None, None, None
    for line in out:
        if re.match("^[-|postqueue:|Mail]", line):
            # discard in-queue wrapper
            continue
        if re.match(queue_pattern, line):
            m = re.match(queue_pattern, line)
            queue_id = m.group("queue_id")
            size = m.group("size")
            timestamp = m.group("timestamp")
            sender = m.group("sender")
        elif re.match(recipient_pattern, line):  # recipient/s
            m = re.match(recipient_pattern, line)
            recipient = m.group("recipient")
        elif not line:  # end of record
            if all((queue_id, size, timestamp, sender, recipient)):
                queue.append(
                    {
                        "queue_id": queue_id,
                        "size": size,
                        "timestamp": timestamp,
                        "sender": sender,
                        "recipient": recipient,
                    }
                )
    return queue


def delete(queue_id):
    """
    Delete message(s) from the mail queue

    CLI Example:

    .. code-block:: bash

        salt '*' postfix.delete 5C33CA0DEA

        salt '*' postfix.delete ALL

    """

    ret = {"message": "", "result": True}

    if not queue_id:
        log.error("Require argument queue_id")

    if not queue_id == "ALL":
        queue = show_queue()
        _message = None
        for item in queue:
            if item["queue_id"] == queue_id:
                _message = item

        if not _message:
            ret["message"] = "No message in queue with ID {}".format(queue_id)
            ret["result"] = False
            return ret

    cmd = "postsuper -d {}".format(queue_id)
    result = __salt__["cmd.run_all"](cmd)

    if result["retcode"] == 0:
        if queue_id == "ALL":
            ret["message"] = "Successfully removed all messages"
        else:
            ret["message"] = "Successfully removed message with queue id {}".format(
                queue_id
            )
    else:
        if queue_id == "ALL":
            ret["message"] = "Unable to removed all messages"
        else:
            ret["message"] = "Unable to remove message with queue id {}: {}".format(
                queue_id, result["stderr"]
            )
    return ret


def hold(queue_id):
    """
    Put message(s) on hold from the mail queue

    CLI Example:

    .. code-block:: bash

        salt '*' postfix.hold 5C33CA0DEA

        salt '*' postfix.hold ALL

    """

    ret = {"message": "", "result": True}

    if not queue_id:
        log.error("Require argument queue_id")

    if not queue_id == "ALL":
        queue = show_queue()
        _message = None
        for item in queue:
            if item["queue_id"] == queue_id:
                _message = item

        if not _message:
            ret["message"] = "No message in queue with ID {}".format(queue_id)
            ret["result"] = False
            return ret

    cmd = "postsuper -h {}".format(queue_id)
    result = __salt__["cmd.run_all"](cmd)

    if result["retcode"] == 0:
        if queue_id == "ALL":
            ret["message"] = "Successfully placed all messages on hold"
        else:
            ret[
                "message"
            ] = "Successfully placed message on hold with queue id {}".format(queue_id)
    else:
        if queue_id == "ALL":
            ret["message"] = "Unable to place all messages on hold"
        else:
            ret[
                "message"
            ] = "Unable to place message on hold with queue id {}: {}".format(
                queue_id, result["stderr"]
            )
    return ret


def unhold(queue_id):
    """
    Set held message(s) in the mail queue to unheld

    CLI Example:

    .. code-block:: bash

        salt '*' postfix.unhold 5C33CA0DEA

        salt '*' postfix.unhold ALL

    """

    ret = {"message": "", "result": True}

    if not queue_id:
        log.error("Require argument queue_id")

    if not queue_id == "ALL":
        queue = show_queue()
        _message = None
        for item in queue:
            if item["queue_id"] == queue_id:
                _message = item

        if not _message:
            ret["message"] = "No message in queue with ID {}".format(queue_id)
            ret["result"] = False
            return ret

    cmd = "postsuper -H {}".format(queue_id)
    result = __salt__["cmd.run_all"](cmd)

    if result["retcode"] == 0:
        if queue_id == "ALL":
            ret["message"] = "Successfully set all message as unheld"
        else:
            ret[
                "message"
            ] = "Successfully set message as unheld with queue id {}".format(queue_id)
    else:
        if queue_id == "ALL":
            ret["message"] = "Unable to set all message as unheld."
        else:
            ret[
                "message"
            ] = "Unable to set message as unheld with queue id {}: {}".format(
                queue_id, result["stderr"]
            )
    return ret


def requeue(queue_id):
    """
    Requeue message(s) in the mail queue

    CLI Example:

    .. code-block:: bash

        salt '*' postfix.requeue 5C33CA0DEA

        salt '*' postfix.requeue ALL

    """

    ret = {"message": "", "result": True}

    if not queue_id:
        log.error("Required argument queue_id")

    if not queue_id == "ALL":
        queue = show_queue()
        _message = None
        for item in queue:
            if item["queue_id"] == queue_id:
                _message = item

        if not _message:
            ret["message"] = "No message in queue with ID {}".format(queue_id)
            ret["result"] = False
            return ret

    cmd = "postsuper -r {}".format(queue_id)
    result = __salt__["cmd.run_all"](cmd)

    if result["retcode"] == 0:
        if queue_id == "ALL":
            ret["message"] = "Successfully requeued all messages"
        else:
            ret["message"] = "Successfully requeued message with queue id {}".format(
                queue_id
            )
    else:
        if queue_id == "ALL":
            ret["message"] = "Unable to requeue all messages"
        else:
            ret["message"] = "Unable to requeue message with queue id {}: {}".format(
                queue_id, result["stderr"]
            )
    return ret
