"""
NAPALM Network
==============

Basic methods for interaction with the network device through the virtual proxy 'napalm'.

:codeauthor: Mircea Ulinic <ping@mirceaulinic.net> & Jerome Fleury <jf@cloudflare.com>
:maturity:   new
:depends:    napalm
:platform:   unix

Dependencies
------------

- :mod:`napalm proxy minion <salt.proxy.napalm>`

.. versionadded:: 2016.11.0
.. versionchanged:: 2017.7.0
"""

import datetime
import logging
import time

import salt.utils.files
import salt.utils.napalm
import salt.utils.templates
import salt.utils.versions

log = logging.getLogger(__name__)


try:
    import jxmlease  # pylint: disable=unused-import

    HAS_JXMLEASE = True
except ImportError:
    HAS_JXMLEASE = False

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = "net"
__proxyenabled__ = ["*"]
__virtual_aliases__ = ("napalm_net",)
# uses NAPALM-based proxy to interact with network devices

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    """
    NAPALM library must be installed for this module to work and run in a (proxy) minion.
    """
    return salt.utils.napalm.virtual(__opts__, __virtualname__, __file__)


# ----------------------------------------------------------------------------------------------------------------------
# helper functions -- will not be exported
# ----------------------------------------------------------------------------------------------------------------------


def _filter_list(input_list, search_key, search_value):
    """
    Filters a list of dictionary by a set of key-value pair.

    :param input_list:   is a list of dictionaries
    :param search_key:   is the key we are looking for
    :param search_value: is the value we are looking for the key specified in search_key
    :return:             filered list of dictionaries
    """

    output_list = list()

    for dictionary in input_list:
        if dictionary.get(search_key) == search_value:
            output_list.append(dictionary)

    return output_list


def _filter_dict(input_dict, search_key, search_value):
    """
    Filters a dictionary of dictionaries by a key-value pair.

    :param input_dict:    is a dictionary whose values are lists of dictionaries
    :param search_key:    is the key in the leaf dictionaries
    :param search_values: is the value in the leaf dictionaries
    :return:              filtered dictionary
    """

    output_dict = dict()

    for key, key_list in input_dict.items():
        key_list_filtered = _filter_list(key_list, search_key, search_value)
        if key_list_filtered:
            output_dict[key] = key_list_filtered

    return output_dict


def _safe_commit_config(loaded_result, napalm_device):
    _commit = commit(
        inherit_napalm_device=napalm_device
    )  # calls the function commit, defined below
    if not _commit.get("result", False):
        # if unable to commit
        loaded_result["comment"] += (
            _commit["comment"] if _commit.get("comment") else "Unable to commit."
        )
        loaded_result["result"] = False
        # unable to commit, something went wrong
        discarded = _safe_dicard_config(loaded_result, napalm_device)
        if not discarded["result"]:
            return loaded_result
    return _commit


def _safe_dicard_config(loaded_result, napalm_device):
    log.debug("Discarding the config")
    log.debug(loaded_result)
    _discarded = discard_config(inherit_napalm_device=napalm_device)
    if not _discarded.get("result", False):
        loaded_result["comment"] += (
            _discarded["comment"]
            if _discarded.get("comment")
            else "Unable to discard config."
        )
        loaded_result["result"] = False
        # make sure it notifies
        # that something went wrong
        _explicit_close(napalm_device)
        __context__["retcode"] = 1
        return loaded_result
    return _discarded


def _explicit_close(napalm_device):
    """
    Will explicily close the config session with the network device,
    when running in a now-always-alive proxy minion or regular minion.
    This helper must be used in configuration-related functions,
    as the session is preserved and not closed before making any changes.
    """
    if salt.utils.napalm.not_always_alive(__opts__):
        # force closing the configuration session
        # when running in a non-always-alive proxy
        # or regular minion
        try:
            napalm_device["DRIVER"].close()
        except Exception as err:  # pylint: disable=broad-except
            log.error("Unable to close the temp connection with the device:")
            log.error(err)
            log.error("Please report.")


def _config_logic(
    napalm_device,
    loaded_result,
    test=False,
    debug=False,
    replace=False,
    commit_config=True,
    loaded_config=None,
    commit_in=None,
    commit_at=None,
    revert_in=None,
    revert_at=None,
    commit_jid=None,
    **kwargs,
):
    """
    Builds the config logic for `load_config` and `load_template` functions.
    """
    # As the Salt logic is built around independent events
    # when it comes to configuration changes in the
    # candidate DB on the network devices, we need to
    # make sure we're using the same session.
    # Hence, we need to pass the same object around.
    # the napalm_device object is inherited from
    # the load_config or load_template functions
    # and forwarded to compare, discard, commit etc.
    # then the decorator will make sure that
    # if not proxy (when the connection is always alive)
    # and the `inherit_napalm_device` is set,
    # `napalm_device` will be overridden.
    # See `salt.utils.napalm.proxy_napalm_wrap` decorator.

    current_jid = kwargs.get("__pub_jid")
    if not current_jid:
        current_jid = f"{datetime.datetime.now():%Y%m%d%H%M%S%f}"

    loaded_result["already_configured"] = False

    loaded_result["loaded_config"] = ""
    if debug:
        loaded_result["loaded_config"] = loaded_config

    _compare = compare_config(inherit_napalm_device=napalm_device)
    if _compare.get("result", False):
        loaded_result["diff"] = _compare.get("out")
        loaded_result.pop("out", "")  # not needed
    else:
        loaded_result["diff"] = None
        loaded_result["result"] = False
        loaded_result["comment"] = _compare.get("comment")
        __context__["retcode"] = 1
        return loaded_result

    _loaded_res = loaded_result.get("result", False)
    if not _loaded_res or test:
        # if unable to load the config (errors / warnings)
        # or in testing mode,
        # will discard the config
        if loaded_result["comment"]:
            loaded_result["comment"] += "\n"
        if not loaded_result.get("diff", ""):
            loaded_result["already_configured"] = True
        discarded = _safe_dicard_config(loaded_result, napalm_device)
        if not discarded["result"]:
            return loaded_result
        loaded_result["comment"] += "Configuration discarded."
        # loaded_result['result'] = False not necessary
        # as the result can be true when test=True
        _explicit_close(napalm_device)
        if not loaded_result["result"]:
            __context__["retcode"] = 1
        return loaded_result

    if not test and commit_config:
        # if not in testing mode and trying to commit
        if commit_jid:
            log.info("Committing the JID: %s", str(commit_jid))
            removed = cancel_commit(commit_jid)
            log.debug("Cleaned up the commit from the schedule")
            log.debug(removed["comment"])
        if loaded_result.get("diff", ""):
            # if not testing mode
            # and also the user wants to commit (default)
            # and there are changes to commit
            if commit_in or commit_at:
                commit_time = __utils__["timeutil.get_time_at"](
                    time_in=commit_in, time_at=commit_in
                )
                # schedule job
                scheduled_job_name = f"__napalm_commit_{current_jid}"
                temp_file = salt.utils.files.mkstemp()
                with salt.utils.files.fopen(temp_file, "w") as fp_:
                    fp_.write(loaded_config)
                scheduled = __salt__["schedule.add"](
                    scheduled_job_name,
                    function="net.load_config",
                    job_kwargs={
                        "filename": temp_file,
                        "commit_jid": current_jid,
                        "replace": replace,
                    },
                    once=commit_time,
                )
                log.debug("Scheduling job")
                log.debug(scheduled)
                saved = __salt__["schedule.save"]()  # ensure the schedule is
                # persistent cross Minion restart
                discarded = _safe_dicard_config(loaded_result, napalm_device)
                # discard the changes
                if not discarded["result"]:
                    discarded["comment"] += (
                        "Scheduled the job to be executed at {schedule_ts}, "
                        "but was unable to discard the config: \n".format(
                            schedule_ts=commit_time
                        )
                    )
                    return discarded
                loaded_result["comment"] = (
                    "Changes discarded for now, and scheduled commit at:"
                    " {schedule_ts}.\nThe commit ID is: {current_jid}.\nTo discard this"
                    " commit, you can execute: \n\nsalt {min_id} net.cancel_commit"
                    " {current_jid}".format(
                        schedule_ts=commit_time,
                        min_id=__opts__["id"],
                        current_jid=current_jid,
                    )
                )
                loaded_result["commit_id"] = current_jid
                return loaded_result
            log.debug("About to commit:")
            log.debug(loaded_result["diff"])
            if revert_in or revert_at:
                revert_time = __utils__["timeutil.get_time_at"](
                    time_in=revert_in, time_at=revert_at
                )
                if __grains__["os"] == "junos":
                    if not HAS_JXMLEASE:
                        loaded_result["comment"] = (
                            "This feature requires the library jxmlease to be"
                            " installed.\nTo install, please execute: ``pip install"
                            " jxmlease``."
                        )
                        loaded_result["result"] = False
                        return loaded_result
                    timestamp_at = __utils__["timeutil.get_timestamp_at"](
                        time_in=revert_in, time_at=revert_at
                    )
                    minutes = int((timestamp_at - time.time()) / 60)
                    _comm = __salt__["napalm.junos_commit"](confirm=minutes)
                    if not _comm["out"]:
                        # If unable to commit confirm, should try to bail out
                        loaded_result["comment"] = (
                            "Unable to commit confirm: {}".format(_comm["message"])
                        )
                        loaded_result["result"] = False
                        # But before exiting, we must gracefully discard the config
                        discarded = _safe_dicard_config(loaded_result, napalm_device)
                        if not discarded["result"]:
                            return loaded_result
                else:
                    temp_file = salt.utils.files.mkstemp()
                    running_config = __salt__["net.config"](source="running")["out"][
                        "running"
                    ]
                    with salt.utils.files.fopen(temp_file, "w") as fp_:
                        fp_.write(running_config)
                    committed = _safe_commit_config(loaded_result, napalm_device)
                    if not committed["result"]:
                        # If unable to commit, dicard the config (which is
                        # already done by the _safe_commit_config function), and
                        # return with the command and other details.
                        return loaded_result
                    scheduled_job_name = f"__napalm_commit_{current_jid}"
                    scheduled = __salt__["schedule.add"](
                        scheduled_job_name,
                        function="net.load_config",
                        job_kwargs={
                            "filename": temp_file,
                            "commit_jid": current_jid,
                            "replace": True,
                        },
                        once=revert_time,
                    )
                    log.debug("Scheduling commit confirmed")
                    log.debug(scheduled)
                    saved = __salt__["schedule.save"]()
                loaded_result["comment"] = (
                    "The commit ID is: {current_jid}.\nThis commit will be reverted at:"
                    " {schedule_ts}, unless confirmed.\nTo confirm the commit and avoid"
                    " reverting, you can execute:\n\nsalt {min_id} net.confirm_commit"
                    " {current_jid}".format(
                        schedule_ts=revert_time,
                        min_id=__opts__["id"],
                        current_jid=current_jid,
                    )
                )
                loaded_result["commit_id"] = current_jid
                return loaded_result
            committed = _safe_commit_config(loaded_result, napalm_device)
            if not committed["result"]:
                return loaded_result
        else:
            # would like to commit, but there's no change
            # need to call discard_config() to release the config DB
            discarded = _safe_dicard_config(loaded_result, napalm_device)
            if not discarded["result"]:
                return loaded_result
            loaded_result["already_configured"] = True
            loaded_result["comment"] = "Already configured."
    _explicit_close(napalm_device)
    if not loaded_result["result"]:
        __context__["retcode"] = 1
    return loaded_result


# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


@salt.utils.napalm.proxy_napalm_wrap
def connected(**kwargs):  # pylint: disable=unused-argument
    """
    Specifies if the connection to the device succeeded.

    CLI Example:

    .. code-block:: bash

        salt '*' net.connected
    """

    return {"out": napalm_device.get("UP", False)}  # pylint: disable=undefined-variable


@salt.utils.napalm.proxy_napalm_wrap
def facts(**kwargs):  # pylint: disable=unused-argument
    """
    Returns characteristics of the network device.
    :return: a dictionary with the following keys:

        * uptime - Uptime of the device in seconds.
        * vendor - Manufacturer of the device.
        * model - Device model.
        * hostname - Hostname of the device
        * fqdn - Fqdn of the device
        * os_version - String with the OS version running on the device.
        * serial_number - Serial number of the device
        * interface_list - List of the interfaces of the device

    CLI Example:

    .. code-block:: bash

        salt '*' net.facts

    Example output:

    .. code-block:: python

        {
            'os_version': '13.3R6.5',
            'uptime': 10117140,
            'interface_list': [
                'lc-0/0/0',
                'pfe-0/0/0',
                'pfh-0/0/0',
                'xe-0/0/0',
                'xe-0/0/1',
                'xe-0/0/2',
                'xe-0/0/3',
                'gr-0/0/10',
                'ip-0/0/10'
            ],
            'vendor': 'Juniper',
            'serial_number': 'JN131356FBFA',
            'model': 'MX480',
            'hostname': 're0.edge05.syd01',
            'fqdn': 're0.edge05.syd01'
        }
    """

    return salt.utils.napalm.call(
        napalm_device, "get_facts", **{}  # pylint: disable=undefined-variable
    )


@salt.utils.napalm.proxy_napalm_wrap
def environment(**kwargs):  # pylint: disable=unused-argument
    """
    Returns the environment of the device.

    CLI Example:

    .. code-block:: bash

        salt '*' net.environment


    Example output:

    .. code-block:: python

        {
            'fans': {
                'Bottom Rear Fan': {
                    'status': True
                },
                'Bottom Middle Fan': {
                    'status': True
                },
                'Top Middle Fan': {
                    'status': True
                },
                'Bottom Front Fan': {
                    'status': True
                },
                'Top Front Fan': {
                    'status': True
                },
                'Top Rear Fan': {
                    'status': True
                }
            },
            'memory': {
                'available_ram': 16349,
                'used_ram': 4934
            },
            'temperature': {
               'FPC 0 Exhaust A': {
                    'is_alert': False,
                    'temperature': 35.0,
                    'is_critical': False
                }
            },
            'cpu': {
                '1': {
                    '%usage': 19.0
                },
                '0': {
                    '%usage': 35.0
                }
            }
        }
    """

    return salt.utils.napalm.call(
        napalm_device, "get_environment", **{}  # pylint: disable=undefined-variable
    )


@salt.utils.napalm.proxy_napalm_wrap
def cli(*commands, **kwargs):  # pylint: disable=unused-argument
    """
    Returns a dictionary with the raw output of all commands passed as arguments.

    commands
        List of commands to be executed on the device.

    textfsm_parse: ``False``
        Try parsing the outputs using the TextFSM templates.

        .. versionadded:: 2018.3.0

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``napalm_cli_textfsm_parse``.

    textfsm_path
        The path where the TextFSM templates can be found. This option implies
        the usage of the TextFSM index file.
        ``textfsm_path`` can be either absolute path on the server,
        either specified using the following URL mschemes: ``file://``,
        ``salt://``, ``http://``, ``https://``, ``ftp://``,
        ``s3://``, ``swift://``.

        .. versionadded:: 2018.3.0

        .. note::
            This needs to be a directory with a flat structure, having an
            index file (whose name can be specified using the ``index_file`` option)
            and a number of TextFSM templates.

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``textfsm_path``.

    textfsm_template
        The path to a certain the TextFSM template.
        This can be specified using the absolute path
        to the file, or using one of the following URL schemes:

        - ``salt://``, to fetch the template from the Salt fileserver.
        - ``http://`` or ``https://``
        - ``ftp://``
        - ``s3://``
        - ``swift://``

        .. versionadded:: 2018.3.0

    textfsm_template_dict
        A dictionary with the mapping between a command
        and the corresponding TextFSM path to use to extract the data.
        The TextFSM paths can be specified as in ``textfsm_template``.

        .. versionadded:: 2018.3.0

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``napalm_cli_textfsm_template_dict``.

    platform_grain_name: ``os``
        The name of the grain used to identify the platform name
        in the TextFSM index file. Default: ``os``.

        .. versionadded:: 2018.3.0

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``textfsm_platform_grain``.

    platform_column_name: ``Platform``
        The column name used to identify the platform,
        exactly as specified in the TextFSM index file.
        Default: ``Platform``.

        .. versionadded:: 2018.3.0

        .. note::
            This is field is case sensitive, make sure
            to assign the correct value to this option,
            exactly as defined in the index file.

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``textfsm_platform_column_name``.

    index_file: ``index``
        The name of the TextFSM index file, under the ``textfsm_path``. Default: ``index``.

        .. versionadded:: 2018.3.0

        .. note::
            This option can be also specified in the minion configuration
            file or pillar as ``textfsm_index_file``.

    saltenv: ``base``
        Salt fileserver environment from which to retrieve the file.
        Ignored if ``textfsm_path`` is not a ``salt://`` URL.

        .. versionadded:: 2018.3.0

    include_empty: ``False``
        Include empty files under the ``textfsm_path``.

        .. versionadded:: 2018.3.0

    include_pat
        Glob or regex to narrow down the files cached from the given path.
        If matching with a regex, the regex must be prefixed with ``E@``,
        otherwise the expression will be interpreted as a glob.

        .. versionadded:: 2018.3.0

    exclude_pat
        Glob or regex to exclude certain files from being cached from the given path.
        If matching with a regex, the regex must be prefixed with ``E@``,
        otherwise the expression will be interpreted as a glob.

        .. versionadded:: 2018.3.0

        .. note::
            If used with ``include_pat``, files matching this pattern will be
            excluded from the subset of files defined by ``include_pat``.

    CLI Example:

    .. code-block:: bash

        salt '*' net.cli "show version" "show chassis fan"

    CLI Example with TextFSM template:

    .. code-block:: bash

        salt '*' net.cli textfsm_parse=True textfsm_path=salt://textfsm/

    Example output:

    .. code-block:: python

        {
            'show version and haiku':  'Hostname: re0.edge01.arn01
                                          Model: mx480
                                          Junos: 13.3R6.5
                                            Help me, Obi-Wan
                                            I just saw Episode Two
                                            You're my only hope
                                         ',
            'show chassis fan' :   'Item                      Status   RPM     Measurement
                                      Top Rear Fan              OK       3840    Spinning at intermediate-speed
                                      Bottom Rear Fan           OK       3840    Spinning at intermediate-speed
                                      Top Middle Fan            OK       3900    Spinning at intermediate-speed
                                      Bottom Middle Fan         OK       3840    Spinning at intermediate-speed
                                      Top Front Fan             OK       3810    Spinning at intermediate-speed
                                      Bottom Front Fan          OK       3840    Spinning at intermediate-speed
                                     '
        }

    Example output with TextFSM parsing:

    .. code-block:: json

        {
          "comment": "",
          "result": true,
          "out": {
            "sh ver": [
              {
                "kernel": "9.1S3.5",
                "documentation": "9.1S3.5",
                "boot": "9.1S3.5",
                "crypto": "9.1S3.5",
                "chassis": "",
                "routing": "9.1S3.5",
                "base": "9.1S3.5",
                "model": "mx960"
              }
            ]
          }
        }
    """
    raw_cli_outputs = salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        "cli",
        **{"commands": list(commands)},
    )
    # thus we can display the output as is
    # in case of errors, they'll be caught in the proxy
    if not raw_cli_outputs["result"]:
        # Error -> dispaly the output as-is.
        return raw_cli_outputs
    textfsm_parse = (
        kwargs.get("textfsm_parse")
        or __opts__.get("napalm_cli_textfsm_parse")
        or __pillar__.get("napalm_cli_textfsm_parse", False)
    )
    if not textfsm_parse:
        # No TextFSM parsing required, return raw commands.
        log.debug("No TextFSM parsing requested.")
        return raw_cli_outputs
    if "textfsm.extract" not in __salt__ or "textfsm.index" not in __salt__:
        raw_cli_outputs["comment"] += "Unable to process: is TextFSM installed?"
        log.error(raw_cli_outputs["comment"])
        return raw_cli_outputs
    textfsm_template = kwargs.get("textfsm_template")
    log.debug("textfsm_template: %s", textfsm_template)
    textfsm_path = (
        kwargs.get("textfsm_path")
        or __opts__.get("textfsm_path")
        or __pillar__.get("textfsm_path")
    )
    log.debug("textfsm_path: %s", textfsm_path)
    textfsm_template_dict = (
        kwargs.get("textfsm_template_dict")
        or __opts__.get("napalm_cli_textfsm_template_dict")
        or __pillar__.get("napalm_cli_textfsm_template_dict", {})
    )
    log.debug("TextFSM command-template mapping: %s", textfsm_template_dict)
    index_file = (
        kwargs.get("index_file")
        or __opts__.get("textfsm_index_file")
        or __pillar__.get("textfsm_index_file")
    )
    log.debug("index_file: %s", index_file)
    platform_grain_name = (
        kwargs.get("platform_grain_name")
        or __opts__.get("textfsm_platform_grain")
        or __pillar__.get("textfsm_platform_grain", "os")
    )
    log.debug("platform_grain_name: %s", platform_grain_name)
    platform_column_name = (
        kwargs.get("platform_column_name")
        or __opts__.get("textfsm_platform_column_name")
        or __pillar__.get("textfsm_platform_column_name", "Platform")
    )
    log.debug("platform_column_name: %s", platform_column_name)
    saltenv = kwargs.get("saltenv", "base")
    include_empty = kwargs.get("include_empty", False)
    include_pat = kwargs.get("include_pat")
    exclude_pat = kwargs.get("exclude_pat")
    processed_cli_outputs = {
        "comment": raw_cli_outputs.get("comment", ""),
        "result": raw_cli_outputs["result"],
        "out": {},
    }
    log.debug("Starting to analyse the raw outputs")
    for command in list(commands):
        command_output = raw_cli_outputs["out"][command]
        log.debug("Output from command: %s", command)
        log.debug(command_output)
        processed_command_output = None
        if textfsm_path:
            log.debug("Using the templates under %s", textfsm_path)
            processed_cli_output = __salt__["textfsm.index"](
                command,
                platform_grain_name=platform_grain_name,
                platform_column_name=platform_column_name,
                output=command_output.strip(),
                textfsm_path=textfsm_path,
                saltenv=saltenv,
                include_empty=include_empty,
                include_pat=include_pat,
                exclude_pat=exclude_pat,
            )
            log.debug("Processed CLI output:")
            log.debug(processed_cli_output)
            if not processed_cli_output["result"]:
                log.debug("Apparently this did not work, returning the raw output")
                processed_command_output = command_output
                processed_cli_outputs[
                    "comment"
                ] += "\nUnable to process the output from {}: {}.".format(
                    command, processed_cli_output["comment"]
                )
                log.error(processed_cli_outputs["comment"])
            elif processed_cli_output["out"]:
                log.debug("All good, %s has a nice output!", command)
                processed_command_output = processed_cli_output["out"]
            else:
                comment = """\nProcessing "{}" didn't fail, but didn't return anything either. Dumping raw.""".format(
                    command
                )
                processed_cli_outputs["comment"] += comment
                log.error(comment)
                processed_command_output = command_output
        elif textfsm_template or command in textfsm_template_dict:
            if command in textfsm_template_dict:
                textfsm_template = textfsm_template_dict[command]
            log.debug("Using %s to process the command: %s", textfsm_template, command)
            processed_cli_output = __salt__["textfsm.extract"](
                textfsm_template, raw_text=command_output, saltenv=saltenv
            )
            log.debug("Processed CLI output:")
            log.debug(processed_cli_output)
            if not processed_cli_output["result"]:
                log.debug("Apparently this did not work, returning the raw output")
                processed_command_output = command_output
                processed_cli_outputs[
                    "comment"
                ] += "\nUnable to process the output from {}: {}".format(
                    command, processed_cli_output["comment"]
                )
                log.error(processed_cli_outputs["comment"])
            elif processed_cli_output["out"]:
                log.debug("All good, %s has a nice output!", command)
                processed_command_output = processed_cli_output["out"]
            else:
                log.debug(
                    "Processing %s did not fail, but did not return"
                    " anything either. Dumping raw.",
                    command,
                )
                processed_command_output = command_output
        else:
            log.error("No TextFSM template specified, or no TextFSM path defined")
            processed_command_output = command_output
            processed_cli_outputs[
                "comment"
            ] += f"\nUnable to process the output from {command}."
        processed_cli_outputs["out"][command] = processed_command_output
    processed_cli_outputs["comment"] = processed_cli_outputs["comment"].strip()
    return processed_cli_outputs


@salt.utils.napalm.proxy_napalm_wrap
def traceroute(
    destination, source=None, ttl=None, timeout=None, vrf=None, **kwargs
):  # pylint: disable=unused-argument
    """
    Calls the method traceroute from the NAPALM driver object and returns a dictionary with the result of the traceroute
    command executed on the device.

    destination
        Hostname or address of remote host

    source
        Source address to use in outgoing traceroute packets

    ttl
        IP maximum time-to-live value (or IPv6 maximum hop-limit value)

    timeout
        Number of seconds to wait for response (seconds)

    vrf
        VRF (routing instance) for traceroute attempt

        .. versionadded:: 2016.11.4

    CLI Example:

    .. code-block:: bash

        salt '*' net.traceroute 8.8.8.8
        salt '*' net.traceroute 8.8.8.8 source=127.0.0.1 ttl=5 timeout=1
    """

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        "traceroute",
        **{
            "destination": destination,
            "source": source,
            "ttl": ttl,
            "timeout": timeout,
            "vrf": vrf,
        },
    )


@salt.utils.napalm.proxy_napalm_wrap
def ping(
    destination,
    source=None,
    ttl=None,
    timeout=None,
    size=None,
    count=None,
    vrf=None,
    **kwargs,
):  # pylint: disable=unused-argument
    """
    Executes a ping on the network device and returns a dictionary as a result.

    destination
        Hostname or IP address of remote host

    source
        Source address of echo request

    ttl
        IP time-to-live value (IPv6 hop-limit value) (1..255 hops)

    timeout
        Maximum wait time after sending final packet (seconds)

    size
        Size of request packets (0..65468 bytes)

    count
        Number of ping requests to send (1..2000000000 packets)

    vrf
        VRF (routing instance) for ping attempt

        .. versionadded:: 2016.11.4

    CLI Example:

    .. code-block:: bash

        salt '*' net.ping 8.8.8.8
        salt '*' net.ping 8.8.8.8 ttl=3 size=65468
        salt '*' net.ping 8.8.8.8 source=127.0.0.1 timeout=1 count=100
    """

    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        "ping",
        **{
            "destination": destination,
            "source": source,
            "ttl": ttl,
            "timeout": timeout,
            "size": size,
            "count": count,
            "vrf": vrf,
        },
    )


@salt.utils.napalm.proxy_napalm_wrap
def arp(
    interface="", ipaddr="", macaddr="", **kwargs
):  # pylint: disable=unused-argument
    """
    NAPALM returns a list of dictionaries with details of the ARP entries.

    :param interface: interface name to filter on
    :param ipaddr: IP address to filter on
    :param macaddr: MAC address to filter on
    :return: List of the entries in the ARP table

    CLI Example:

    .. code-block:: bash

        salt '*' net.arp
        salt '*' net.arp macaddr='5c:5e:ab:da:3c:f0'

    Example output:

    .. code-block:: python

        [
            {
                'interface' : 'MgmtEth0/RSP0/CPU0/0',
                'mac'       : '5c:5e:ab:da:3c:f0',
                'ip'        : '172.17.17.1',
                'age'       : 1454496274.84
            },
            {
                'interface': 'MgmtEth0/RSP0/CPU0/0',
                'mac'       : '66:0e:94:96:e0:ff',
                'ip'        : '172.17.17.2',
                'age'       : 1435641582.49
            }
        ]
    """

    proxy_output = salt.utils.napalm.call(
        napalm_device, "get_arp_table", **{}  # pylint: disable=undefined-variable
    )

    if not proxy_output.get("result"):
        return proxy_output

    arp_table = proxy_output.get("out")

    if interface:
        arp_table = _filter_list(arp_table, "interface", interface)

    if ipaddr:
        arp_table = _filter_list(arp_table, "ip", ipaddr)

    if macaddr:
        arp_table = _filter_list(arp_table, "mac", macaddr)

    proxy_output.update({"out": arp_table})

    return proxy_output


@salt.utils.napalm.proxy_napalm_wrap
def ipaddrs(**kwargs):  # pylint: disable=unused-argument
    """
    Returns IP addresses configured on the device.

    :return:   A dictionary with the IPv4 and IPv6 addresses of the interfaces.
        Returns all configured IP addresses on all interfaces as a dictionary
        of dictionaries.  Keys of the main dictionary represent the name of the
        interface.  Values of the main dictionary represent are dictionaries
        that may consist of two keys 'ipv4' and 'ipv6' (one, both or none)
        which are themselvs dictionaries with the IP addresses as keys.

    CLI Example:

    .. code-block:: bash

        salt '*' net.ipaddrs

    Example output:

    .. code-block:: python

        {
            'FastEthernet8': {
                'ipv4': {
                    '10.66.43.169': {
                        'prefix_length': 22
                    }
                }
            },
            'Loopback555': {
                'ipv4': {
                    '192.168.1.1': {
                        'prefix_length': 24
                    }
                },
                'ipv6': {
                    '1::1': {
                        'prefix_length': 64
                    },
                    '2001:DB8:1::1': {
                        'prefix_length': 64
                    },
                    'FE80::3': {
                        'prefix_length': 'N/A'
                    }
                }
            }
        }
    """

    return salt.utils.napalm.call(
        napalm_device, "get_interfaces_ip", **{}  # pylint: disable=undefined-variable
    )


@salt.utils.napalm.proxy_napalm_wrap
def interfaces(**kwargs):  # pylint: disable=unused-argument
    """
    Returns details of the interfaces on the device.

    :return: Returns a dictionary of dictionaries. The keys for the first
        dictionary will be the interfaces in the devices.

    CLI Example:

    .. code-block:: bash

        salt '*' net.interfaces

    Example output:

    .. code-block:: python

        {
            'Management1': {
                'is_up': False,
                'is_enabled': False,
                'description': '',
                'last_flapped': -1,
                'speed': 1000,
                'mac_address': 'dead:beef:dead',
            },
            'Ethernet1':{
                'is_up': True,
                'is_enabled': True,
                'description': 'foo',
                'last_flapped': 1429978575.1554043,
                'speed': 1000,
                'mac_address': 'beef:dead:beef',
            }
        }
    """

    return salt.utils.napalm.call(
        napalm_device, "get_interfaces", **{}  # pylint: disable=undefined-variable
    )


@salt.utils.napalm.proxy_napalm_wrap
def lldp(interface="", **kwargs):  # pylint: disable=unused-argument
    """
    Returns a detailed view of the LLDP neighbors.

    :param interface: interface name to filter on

    :return:          A dictionary with the LLDL neighbors. The keys are the
        interfaces with LLDP activated on.

    CLI Example:

    .. code-block:: bash

        salt '*' net.lldp
        salt '*' net.lldp interface='TenGigE0/0/0/8'

    Example output:

    .. code-block:: python

        {
            'TenGigE0/0/0/8': [
                {
                    'parent_interface': 'Bundle-Ether8',
                    'interface_description': 'TenGigE0/0/0/8',
                    'remote_chassis_id': '8c60.4f69.e96c',
                    'remote_system_name': 'switch',
                    'remote_port': 'Eth2/2/1',
                    'remote_port_description': 'Ethernet2/2/1',
                    'remote_system_description': 'Cisco Nexus Operating System (NX-OS) Software 7.1(0)N1(1a)
                          TAC support: http://www.cisco.com/tac
                          Copyright (c) 2002-2015, Cisco Systems, Inc. All rights reserved.',
                    'remote_system_capab': 'B, R',
                    'remote_system_enable_capab': 'B'
                }
            ]
        }
    """

    proxy_output = salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        "get_lldp_neighbors_detail",
        **{},
    )

    if not proxy_output.get("result"):
        return proxy_output

    lldp_neighbors = proxy_output.get("out")

    if interface:
        lldp_neighbors = {interface: lldp_neighbors.get(interface)}

    proxy_output.update({"out": lldp_neighbors})

    return proxy_output


@salt.utils.napalm.proxy_napalm_wrap
def mac(address="", interface="", vlan=0, **kwargs):  # pylint: disable=unused-argument
    """
    Returns the MAC Address Table on the device.

    :param address:   MAC address to filter on
    :param interface: Interface name to filter on
    :param vlan:      VLAN identifier
    :return:          A list of dictionaries representing the entries in the MAC Address Table

    CLI Example:

    .. code-block:: bash

        salt '*' net.mac
        salt '*' net.mac vlan=10

    Example output:

    .. code-block:: python

        [
            {
                'mac'       : '00:1c:58:29:4a:71',
                'interface' : 'xe-3/0/2',
                'static'    : False,
                'active'    : True,
                'moves'     : 1,
                'vlan'      : 10,
                'last_move' : 1454417742.58
            },
            {
                'mac'       : '8c:60:4f:58:e1:c1',
                'interface' : 'xe-1/0/1',
                'static'    : False,
                'active'    : True,
                'moves'     : 2,
                'vlan'      : 42,
                'last_move' : 1453191948.11
            }
        ]
    """

    proxy_output = salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        "get_mac_address_table",
        **{},
    )

    if not proxy_output.get("result"):
        # if negative, leave the output unchanged
        return proxy_output

    mac_address_table = proxy_output.get("out")

    if vlan and isinstance(vlan, int):
        mac_address_table = _filter_list(mac_address_table, "vlan", vlan)

    if address:
        mac_address_table = _filter_list(mac_address_table, "mac", address)

    if interface:
        mac_address_table = _filter_list(mac_address_table, "interface", interface)

    proxy_output.update({"out": mac_address_table})

    return proxy_output


@salt.utils.napalm.proxy_napalm_wrap
def config(source=None, **kwargs):  # pylint: disable=unused-argument
    """
    .. versionadded:: 2017.7.0

    Return the whole configuration of the network device. By default, it will
    return all possible configuration sources supported by the network device.
    At most, there will be:

    - running config
    - startup config
    - candidate config

    To return only one of the configurations, you can use the ``source``
    argument.

    source
        Which configuration type you want to display, default is all of them.

        Options:

        - running
        - candidate
        - startup

    :return:
        The object returned is a dictionary with the following keys:

        - running (string): Representation of the native running configuration.
        - candidate (string): Representation of the native candidate configuration.
            If the device doesn't differentiate between running and startup
            configuration this will an empty string.
        - startup (string): Representation of the native startup configuration.
            If the device doesn't differentiate between running and startup
            configuration this will an empty string.

    CLI Example:

    .. code-block:: bash

        salt '*' net.config
        salt '*' net.config source=candidate
    """
    return salt.utils.napalm.call(
        napalm_device,  # pylint: disable=undefined-variable
        "get_config",
        **{"retrieve": source},
    )


@salt.utils.napalm.proxy_napalm_wrap
def optics(**kwargs):  # pylint: disable=unused-argument
    """
    .. versionadded:: 2017.7.0

    Fetches the power usage on the various transceivers installed
    on the network device (in dBm), and returns a view that conforms with the
    OpenConfig model openconfig-platform-transceiver.yang.

    :return:
        Returns a dictionary where the keys are as listed below:
            * intf_name (unicode)
                * physical_channels
                    * channels (list of dicts)
                        * index (int)
                        * state
                            * input_power
                                * instant (float)
                                * avg (float)
                                * min (float)
                                * max (float)
                            * output_power
                                * instant (float)
                                * avg (float)
                                * min (float)
                                * max (float)
                            * laser_bias_current
                                * instant (float)
                                * avg (float)
                                * min (float)
                                * max (float)

    CLI Example:

    .. code-block:: bash

        salt '*' net.optics
    """
    return salt.utils.napalm.call(
        napalm_device, "get_optics", **{}  # pylint: disable=undefined-variable
    )


# <---- Call NAPALM getters --------------------------------------------------------------------------------------------

# ----- Configuration specific functions ------------------------------------------------------------------------------>


@salt.utils.napalm.proxy_napalm_wrap
def load_config(
    filename=None,
    text=None,
    test=False,
    commit=True,
    debug=False,
    replace=False,
    commit_in=None,
    commit_at=None,
    revert_in=None,
    revert_at=None,
    commit_jid=None,
    inherit_napalm_device=None,
    saltenv="base",
    **kwargs,
):  # pylint: disable=unused-argument
    """
    Applies configuration changes on the device. It can be loaded from a file or from inline string.
    If you send both a filename and a string containing the configuration, the file has higher precedence.

    By default this function will commit the changes. If there are no changes, it does not commit and
    the flag ``already_configured`` will be set as ``True`` to point this out.

    To avoid committing the configuration, set the argument ``test`` to ``True`` and will discard (dry run).

    To keep the changes but not commit, set ``commit`` to ``False``.

    To replace the config, set ``replace`` to ``True``.

    filename
        Path to the file containing the desired configuration.
        This can be specified using the absolute path to the file,
        or using one of the following URL schemes:

        - ``salt://``, to fetch the template from the Salt fileserver.
        - ``http://`` or ``https://``
        - ``ftp://``
        - ``s3://``
        - ``swift://``

        .. versionchanged:: 2018.3.0

    text
        String containing the desired configuration.
        This argument is ignored when ``filename`` is specified.

    test: False
        Dry run? If set as ``True``, will apply the config, discard and return the changes. Default: ``False``
        and will commit the changes on the device.

    commit: True
        Commit? Default: ``True``.

    debug: False
        Debug mode. Will insert a new key under the output dictionary, as ``loaded_config`` containing the raw
        configuration loaded on the device.

        .. versionadded:: 2016.11.2

    replace: False
        Load and replace the configuration. Default: ``False``.

        .. versionadded:: 2016.11.2

    commit_in: ``None``
        Commit the changes in a specific number of minutes / hours. Example of
        accepted formats: ``5`` (commit in 5 minutes), ``2m`` (commit in 2
        minutes), ``1h`` (commit the changes in 1 hour)`, ``5h30m`` (commit
        the changes in 5 hours and 30 minutes).

        .. note::
            This feature works on any platforms, as it does not rely on the
            native features of the network operating system.

        .. note::
            After the command is executed and the ``diff`` is not satisfactory,
            or for any other reasons you have to discard the commit, you are
            able to do so using the
            :py:func:`net.cancel_commit <salt.modules.napalm_network.cancel_commit>`
            execution function, using the commit ID returned by this function.

        .. warning::
            Using this feature, Salt will load the exact configuration you
            expect, however the diff may change in time (i.e., if an user
            applies a manual configuration change, or a different process or
            command changes the configuration in the meanwhile).

        .. versionadded:: 2019.2.0

    commit_at: ``None``
        Commit the changes at a specific time. Example of accepted formats:
        ``1am`` (will commit the changes at the next 1AM), ``13:20`` (will
        commit at 13:20), ``1:20am``, etc.

        .. note::
            This feature works on any platforms, as it does not rely on the
            native features of the network operating system.

        .. note::
            After the command is executed and the ``diff`` is not satisfactory,
            or for any other reasons you have to discard the commit, you are
            able to do so using the
            :py:func:`net.cancel_commit <salt.modules.napalm_network.cancel_commit>`
            execution function, using the commit ID returned by this function.

        .. warning::
            Using this feature, Salt will load the exact configuration you
            expect, however the diff may change in time (i.e., if an user
            applies a manual configuration change, or a different process or
            command changes the configuration in the meanwhile).

        .. versionadded:: 2019.2.0

    revert_in: ``None``
        Commit and revert the changes in a specific number of minutes / hours.
        Example of accepted formats: ``5`` (revert in 5 minutes), ``2m`` (revert
        in 2 minutes), ``1h`` (revert the changes in 1 hour)`, ``5h30m`` (revert
        the changes in 5 hours and 30 minutes).

        .. note::
            To confirm the commit, and prevent reverting the changes, you will
            have to execute the
            :mod:`net.confirm_commit <salt.modules.napalm_network.confirm_commit>`
            function, using the commit ID returned by this function.

        .. warning::
            This works on any platform, regardless if they have or don't have
            native capabilities to confirming a commit. However, please be
            *very* cautious when using this feature: on Junos (as it is the only
            NAPALM core platform supporting this natively) it executes a commit
            confirmed as you would do from the command line.
            All the other platforms don't have this capability natively,
            therefore the revert is done via Salt. That means, your device needs
            to be reachable at the moment when Salt will attempt to revert your
            changes. Be cautious when pushing configuration changes that would
            prevent you reach the device.

            Similarly, if an user or a different process apply other
            configuration changes in the meanwhile (between the moment you
            commit and till the changes are reverted), these changes would be
            equally reverted, as Salt cannot be aware of them.

        .. versionadded:: 2019.2.0

    revert_at: ``None``
        Commit and revert the changes at a specific time. Example of accepted
        formats: ``1am`` (will commit and revert the changes at the next 1AM),
        ``13:20`` (will commit and revert at 13:20), ``1:20am``, etc.

        .. note::
            To confirm the commit, and prevent reverting the changes, you will
            have to execute the
            :mod:`net.confirm_commit <salt.modules.napalm_network.confirm_commit>`
            function, using the commit ID returned by this function.

        .. warning::
            This works on any platform, regardless if they have or don't have
            native capabilities to confirming a commit. However, please be
            *very* cautious when using this feature: on Junos (as it is the only
            NAPALM core platform supporting this natively) it executes a commit
            confirmed as you would do from the command line.
            All the other platforms don't have this capability natively,
            therefore the revert is done via Salt. That means, your device needs
            to be reachable at the moment when Salt will attempt to revert your
            changes. Be cautious when pushing configuration changes that would
            prevent you reach the device.

            Similarly, if an user or a different process apply other
            configuration changes in the meanwhile (between the moment you
            commit and till the changes are reverted), these changes would be
            equally reverted, as Salt cannot be aware of them.

        .. versionadded:: 2019.2.0

    saltenv: ``base``
        Specifies the Salt environment name.

        .. versionadded:: 2018.3.0

    :return: a dictionary having the following keys:

    * result (bool): if the config was applied successfully. It is ``False`` only in case of failure. In case \
    there are no changes to be applied and successfully performs all operations it is still ``True`` and so will be \
    the ``already_configured`` flag (example below)
    * comment (str): a message for the user
    * already_configured (bool): flag to check if there were no changes applied
    * loaded_config (str): the configuration loaded on the device. Requires ``debug`` to be set as ``True``
    * diff (str): returns the config changes applied

    CLI Example:

    .. code-block:: bash

        salt '*' net.load_config text='ntp peer 192.168.0.1'
        salt '*' net.load_config filename='/absolute/path/to/your/file'
        salt '*' net.load_config filename='/absolute/path/to/your/file' test=True
        salt '*' net.load_config filename='/absolute/path/to/your/file' commit=False

    Example output:

    .. code-block:: python

        {
            'comment': 'Configuration discarded.',
            'already_configured': False,
            'result': True,
            'diff': '[edit interfaces xe-0/0/5]+   description "Adding a description";'
        }
    """
    fun = "load_merge_candidate"
    if replace:
        fun = "load_replace_candidate"
    if salt.utils.napalm.not_always_alive(__opts__):
        # if a not-always-alive proxy
        # or regular minion
        # do not close the connection after loading the config
        # this will be handled in _config_logic
        # after running the other features:
        # compare_config, discard / commit
        # which have to be over the same session
        napalm_device["CLOSE"] = False  # pylint: disable=undefined-variable
    if filename:
        text = __salt__["cp.get_file_str"](filename, saltenv=saltenv)
        if text is False:
            # When using salt:// or https://, if the resource is not available,
            #   it will either raise an exception, or return False.
            ret = {"result": False, "out": None}
            ret["comment"] = (
                "Unable to read from {}. Please specify a valid file or text.".format(
                    filename
                )
            )
            log.error(ret["comment"])
            return ret
        if commit_jid:
            # When the commit_jid argument is passed, it probably is a scheduled
            # commit to be executed, and filename is a temporary file which
            # can be removed after reading it.
            salt.utils.files.safe_rm(filename)
    _loaded = salt.utils.napalm.call(
        napalm_device, fun, **{"config": text}  # pylint: disable=undefined-variable
    )
    return _config_logic(
        napalm_device,  # pylint: disable=undefined-variable
        _loaded,
        test=test,
        debug=debug,
        replace=replace,
        commit_config=commit,
        loaded_config=text,
        commit_at=commit_at,
        commit_in=commit_in,
        revert_in=revert_in,
        revert_at=revert_at,
        commit_jid=commit_jid,
        **kwargs,
    )


@salt.utils.napalm.proxy_napalm_wrap
def load_template(
    template_name=None,
    template_source=None,
    context=None,
    defaults=None,
    template_engine="jinja",
    saltenv="base",
    template_hash=None,
    template_hash_name=None,
    skip_verify=False,
    test=False,
    commit=True,
    debug=False,
    replace=False,
    commit_in=None,
    commit_at=None,
    revert_in=None,
    revert_at=None,
    inherit_napalm_device=None,  # pylint: disable=unused-argument
    **template_vars,
):
    """
    Renders a configuration template (default: Jinja) and loads the result on the device.

    By default this function will commit the changes. If there are no changes,
    it does not commit, discards he config and the flag ``already_configured``
    will be set as ``True`` to point this out.

    To avoid committing the configuration, set the argument ``test`` to ``True``
    and will discard (dry run).

    To preserve the changes, set ``commit`` to ``False``.
    However, this is recommended to be used only in exceptional cases
    when there are applied few consecutive states
    and/or configuration changes.
    Otherwise the user might forget that the config DB is locked
    and the candidate config buffer is not cleared/merged in the running config.

    To replace the config, set ``replace`` to ``True``.

    template_name
        Identifies path to the template source.
        The template can be either stored on the local machine, either remotely.
        The recommended location is under the ``file_roots``
        as specified in the master config file.
        For example, let's suppose the ``file_roots`` is configured as:

        .. code-block:: yaml

            file_roots:
              base:
                - /etc/salt/states

        Placing the template under ``/etc/salt/states/templates/example.jinja``,
        it can be used as ``salt://templates/example.jinja``.
        Alternatively, for local files, the user can specify the absolute path.
        If remotely, the source can be retrieved via ``http``, ``https`` or ``ftp``.

        Examples:

        - ``salt://my_template.jinja``
        - ``/absolute/path/to/my_template.jinja``
        - ``http://example.com/template.cheetah``
        - ``https:/example.com/template.mako``
        - ``ftp://example.com/template.py``

        .. versionchanged:: 2019.2.0
            This argument can now support a list of templates to be rendered.
            The resulting configuration text is loaded at once, as a single
            configuration chunk.

    template_source: None
        Inline config template to be rendered and loaded on the device.

    template_hash: None
        Hash of the template file. Format: ``{hash_type: 'md5', 'hsum': <md5sum>}``

        .. versionadded:: 2016.11.2

    context: None
        Overrides default context variables passed to the template.

        .. versionadded:: 2019.2.0

    template_hash_name: None
        When ``template_hash`` refers to a remote file,
        this specifies the filename to look for in that file.

        .. versionadded:: 2016.11.2

    saltenv: ``base``
        Specifies the template environment.
        This will influence the relative imports inside the templates.

        .. versionadded:: 2016.11.2

    template_engine: jinja
        The following templates engines are supported:

        - :mod:`cheetah<salt.renderers.cheetah>`
        - :mod:`genshi<salt.renderers.genshi>`
        - :mod:`jinja<salt.renderers.jinja>`
        - :mod:`mako<salt.renderers.mako>`
        - :mod:`py<salt.renderers.py>`
        - :mod:`wempy<salt.renderers.wempy>`

        .. versionadded:: 2016.11.2

    skip_verify: True
        If ``True``, hash verification of remote file sources
        (``http://``, ``https://``, ``ftp://``) will be skipped,
        and the ``source_hash`` argument will be ignored.

        .. versionadded:: 2016.11.2

    test: False
        Dry run? If set to ``True``, will apply the config,
        discard and return the changes.
        Default: ``False`` and will commit the changes on the device.

    commit: True
        Commit? (default: ``True``)

    debug: False
        Debug mode. Will insert a new key under the output dictionary,
        as ``loaded_config`` containing the raw result after the template was rendered.

        .. versionadded:: 2016.11.2

    replace: False
        Load and replace the configuration.

        .. versionadded:: 2016.11.2

    commit_in: ``None``
        Commit the changes in a specific number of minutes / hours. Example of
        accepted formats: ``5`` (commit in 5 minutes), ``2m`` (commit in 2
        minutes), ``1h`` (commit the changes in 1 hour)`, ``5h30m`` (commit
        the changes in 5 hours and 30 minutes).

        .. note::
            This feature works on any platforms, as it does not rely on the
            native features of the network operating system.

        .. note::
            After the command is executed and the ``diff`` is not satisfactory,
            or for any other reasons you have to discard the commit, you are
            able to do so using the
            :py:func:`net.cancel_commit <salt.modules.napalm_network.cancel_commit>`
            execution function, using the commit ID returned by this function.

        .. warning::
            Using this feature, Salt will load the exact configuration you
            expect, however the diff may change in time (i.e., if an user
            applies a manual configuration change, or a different process or
            command changes the configuration in the meanwhile).

        .. versionadded:: 2019.2.0

    commit_at: ``None``
        Commit the changes at a specific time. Example of accepted formats:
        ``1am`` (will commit the changes at the next 1AM), ``13:20`` (will
        commit at 13:20), ``1:20am``, etc.

        .. note::
            This feature works on any platforms, as it does not rely on the
            native features of the network operating system.

        .. note::
            After the command is executed and the ``diff`` is not satisfactory,
            or for any other reasons you have to discard the commit, you are
            able to do so using the
            :py:func:`net.cancel_commit <salt.modules.napalm_network.cancel_commit>`
            execution function, using the commit ID returned by this function.

        .. warning::
            Using this feature, Salt will load the exact configuration you
            expect, however the diff may change in time (i.e., if an user
            applies a manual configuration change, or a different process or
            command changes the configuration in the meanwhile).

        .. versionadded:: 2019.2.0

    revert_in: ``None``
        Commit and revert the changes in a specific number of minutes / hours.
        Example of accepted formats: ``5`` (revert in 5 minutes), ``2m`` (revert
        in 2 minutes), ``1h`` (revert the changes in 1 hour)`, ``5h30m`` (revert
        the changes in 5 hours and 30 minutes).

        .. note::
            To confirm the commit, and prevent reverting the changes, you will
            have to execute the
            :mod:`net.confirm_commit <salt.modules.napalm_network.confirm_commit>`
            function, using the commit ID returned by this function.

        .. warning::
            This works on any platform, regardless if they have or don't have
            native capabilities to confirming a commit. However, please be
            *very* cautious when using this feature: on Junos (as it is the only
            NAPALM core platform supporting this natively) it executes a commit
            confirmed as you would do from the command line.
            All the other platforms don't have this capability natively,
            therefore the revert is done via Salt. That means, your device needs
            to be reachable at the moment when Salt will attempt to revert your
            changes. Be cautious when pushing configuration changes that would
            prevent you reach the device.

            Similarly, if an user or a different process apply other
            configuration changes in the meanwhile (between the moment you
            commit and till the changes are reverted), these changes would be
            equally reverted, as Salt cannot be aware of them.

        .. versionadded:: 2019.2.0

    revert_at: ``None``
        Commit and revert the changes at a specific time. Example of accepted
        formats: ``1am`` (will commit and revert the changes at the next 1AM),
        ``13:20`` (will commit and revert at 13:20), ``1:20am``, etc.

        .. note::
            To confirm the commit, and prevent reverting the changes, you will
            have to execute the
            :mod:`net.confirm_commit <salt.modules.napalm_network.confirm_commit>`
            function, using the commit ID returned by this function.

        .. warning::
            This works on any platform, regardless if they have or don't have
            native capabilities to confirming a commit. However, please be
            *very* cautious when using this feature: on Junos (as it is the only
            NAPALM core platform supporting this natively) it executes a commit
            confirmed as you would do from the command line.
            All the other platforms don't have this capability natively,
            therefore the revert is done via Salt. That means, your device needs
            to be reachable at the moment when Salt will attempt to revert your
            changes. Be cautious when pushing configuration changes that would
            prevent you reach the device.

            Similarly, if an user or a different process apply other
            configuration changes in the meanwhile (between the moment you
            commit and till the changes are reverted), these changes would be
            equally reverted, as Salt cannot be aware of them.

        .. versionadded:: 2019.2.0

    defaults: None
        Default variables/context passed to the template.

        .. versionadded:: 2016.11.2

    template_vars
        Dictionary with the arguments/context to be used when the template is rendered.

        .. note::
            Do not explicitly specify this argument. This represents any other
            variable that will be sent to the template rendering system.
            Please see the examples below!

        .. note::
            It is more recommended to use the ``context`` argument to avoid
            conflicts between CLI arguments and template variables.

    :return: a dictionary having the following keys:

    - result (bool): if the config was applied successfully. It is ``False``
      only in case of failure. In case there are no changes to be applied and
      successfully performs all operations it is still ``True`` and so will be
      the ``already_configured`` flag (example below)
    - comment (str): a message for the user
    - already_configured (bool): flag to check if there were no changes applied
    - loaded_config (str): the configuration loaded on the device, after
      rendering the template. Requires ``debug`` to be set as ``True``
    - diff (str): returns the config changes applied

    The template can use variables from the ``grains``, ``pillar`` or ``opts``, for example:

    .. code-block:: jinja

        {% set router_model = grains.get('model') -%}
        {% set router_vendor = grains.get('vendor') -%}
        {% set os_version = grains.get('version') -%}
        {% set hostname = pillar.get('proxy', {}).get('host') -%}
        {% if router_vendor|lower == 'juniper' %}
        system {
            host-name {{hostname}};
        }
        {% elif router_vendor|lower == 'cisco' %}
        hostname {{hostname}}
        {% endif %}

    CLI Examples:

    .. code-block:: bash

        salt '*' net.load_template set_ntp_peers peers=[192.168.0.1]  # uses NAPALM default templates

        # inline template:
        salt -G 'os:junos' net.load_template template_source='system { host-name {{host_name}}; }' \
        host_name='MX480.lab'

        # inline template using grains info:
        salt -G 'os:junos' net.load_template \
        template_source='system { host-name {{grains.model}}.lab; }'
        # if the device is a MX480, the command above will set the hostname as: MX480.lab

        # inline template using pillar data:
        salt -G 'os:junos' net.load_template template_source='system { host-name {{pillar.proxy.host}}; }'

        salt '*' net.load_template https://bit.ly/2OhSgqP hostname=example  # will commit
        salt '*' net.load_template https://bit.ly/2OhSgqP hostname=example test=True  # dry run

        salt '*' net.load_template salt://templates/example.jinja debug=True  # Using the salt:// URI

        # render a mako template:
        salt '*' net.load_template salt://templates/example.mako template_engine=mako debug=True

        # render remote template
        salt -G 'os:junos' net.load_template http://bit.ly/2fReJg7 test=True debug=True peers=['192.168.0.1']
        salt -G 'os:ios' net.load_template http://bit.ly/2gKOj20 test=True debug=True peers=['192.168.0.1']

        # render multiple templates at once
        salt '*' net.load_template "['https://bit.ly/2OhSgqP', 'salt://templates/example.jinja']" context="{'hostname': 'example'}"

    Example output:

    .. code-block:: python

        {
            'comment': '',
            'already_configured': False,
            'result': True,
            'diff': '[edit system]+  host-name edge01.bjm01',
            'loaded_config': 'system { host-name edge01.bjm01; }''
        }
    """
    _rendered = ""
    _loaded = {"result": True, "comment": "", "out": None}
    loaded_config = None
    # prechecks
    if template_engine not in salt.utils.templates.TEMPLATE_REGISTRY:
        _loaded.update(
            {
                "result": False,
                "comment": (
                    "Invalid templating engine! Choose between: {tpl_eng_opts}".format(
                        tpl_eng_opts=", ".join(
                            list(salt.utils.templates.TEMPLATE_REGISTRY.keys())
                        )
                    )
                ),
            }
        )
        return _loaded  # exit

    # to check if will be rendered by salt or NAPALM
    salt_render_prefixes = ("salt://", "http://", "https://", "ftp://")
    salt_render = False
    file_exists = False
    if not isinstance(template_name, (tuple, list)):
        for salt_render_prefix in salt_render_prefixes:
            if not salt_render:
                salt_render = salt_render or template_name.startswith(
                    salt_render_prefix
                )
        file_exists = __salt__["file.file_exists"](template_name)

    if context is None:
        context = {}
    context.update(template_vars)
    # if needed to render the template send as inline arg
    if template_source:
        # render the content
        _rendered = __salt__["file.apply_template_on_contents"](
            contents=template_source,
            template=template_engine,
            context=context,
            defaults=defaults,
            saltenv=saltenv,
        )
        if not isinstance(_rendered, str):
            if "result" in _rendered:
                _loaded["result"] = _rendered["result"]
            else:
                _loaded["result"] = False
            if "comment" in _rendered:
                _loaded["comment"] = _rendered["comment"]
            else:
                _loaded["comment"] = "Error while rendering the template."
            return _loaded
    else:
        # render the file - either local, either remote
        if not isinstance(template_name, (list, tuple)):
            template_name = [template_name]
        if template_hash_name and not isinstance(template_hash_name, (list, tuple)):
            template_hash_name = [template_hash_name]
        elif not template_hash_name:
            template_hash_name = [None] * len(template_name)
        if (
            template_hash
            and isinstance(template_hash, str)
            and not (
                template_hash.startswith("salt://")
                or template_hash.startswith("file://")
            )
        ):
            # If the template hash is passed as string, and it's not a file
            # (starts with the salt:// or file:// URI), then make it a list
            # of 1 element (for the iteration below)
            template_hash = [template_hash]
        elif (
            template_hash
            and isinstance(template_hash, str)
            and (
                template_hash.startswith("salt://")
                or template_hash.startswith("file://")
            )
        ):
            # If the template hash is a file URI, then provide the same value
            # for each of the templates in the list, as probably they all
            # share the same hash file, otherwise the user should provide
            # this as a list
            template_hash = [template_hash] * len(template_name)
        elif not template_hash:
            template_hash = [None] * len(template_name)
        for tpl_index, tpl_name in enumerate(template_name):
            tpl_hash = template_hash[tpl_index]
            tpl_hash_name = template_hash_name[tpl_index]
            _rand_filename = __salt__["random.hash"](tpl_name, "md5")
            _temp_file = __salt__["file.join"]("/tmp", _rand_filename)
            _managed = __salt__["file.get_managed"](
                name=_temp_file,
                source=tpl_name,
                source_hash=tpl_hash,
                source_hash_name=tpl_hash_name,
                user=None,
                group=None,
                mode=None,
                attrs=None,
                template=template_engine,
                context=context,
                defaults=defaults,
                saltenv=saltenv,
                skip_verify=skip_verify,
            )
            if not isinstance(_managed, (list, tuple)) and isinstance(_managed, str):
                _loaded["comment"] += _managed
                _loaded["result"] = False
            elif isinstance(_managed, (list, tuple)) and not len(_managed) > 0:
                _loaded["result"] = False
                _loaded["comment"] += "Error while rendering the template."
            elif isinstance(_managed, (list, tuple)) and not len(_managed[0]) > 0:
                _loaded["result"] = False
                _loaded["comment"] += _managed[-1]  # contains the error message
            if _loaded["result"]:  # all good
                _temp_tpl_file = _managed[0]
                _temp_tpl_file_exists = __salt__["file.file_exists"](_temp_tpl_file)
                if not _temp_tpl_file_exists:
                    _loaded["result"] = False
                    _loaded["comment"] += "Error while rendering the template."
                    return _loaded
                _rendered += __salt__["file.read"](_temp_tpl_file)
                __salt__["file.remove"](_temp_tpl_file)
            else:
                return _loaded  # exit

    loaded_config = _rendered
    if _loaded["result"]:  # all good
        fun = "load_merge_candidate"
        if replace:  # replace requested
            fun = "load_replace_candidate"
        if salt.utils.napalm.not_always_alive(__opts__):
            # if a not-always-alive proxy
            # or regular minion
            # do not close the connection after loading the config
            # this will be handled in _config_logic
            # after running the other features:
            # compare_config, discard / commit
            # which have to be over the same session
            napalm_device["CLOSE"] = False  # pylint: disable=undefined-variable
        _loaded = salt.utils.napalm.call(
            napalm_device,  # pylint: disable=undefined-variable
            fun,
            **{"config": _rendered},
        )
    return _config_logic(
        napalm_device,  # pylint: disable=undefined-variable
        _loaded,
        test=test,
        debug=debug,
        replace=replace,
        commit_config=commit,
        loaded_config=loaded_config,
        commit_at=commit_at,
        commit_in=commit_in,
        revert_in=revert_in,
        revert_at=revert_at,
        **template_vars,
    )


@salt.utils.napalm.proxy_napalm_wrap
def commit(inherit_napalm_device=None, **kwargs):  # pylint: disable=unused-argument
    """
    Commits the configuration changes made on the network device.

    CLI Example:

    .. code-block:: bash

        salt '*' net.commit
    """

    return salt.utils.napalm.call(
        napalm_device, "commit_config", **{}  # pylint: disable=undefined-variable
    )


@salt.utils.napalm.proxy_napalm_wrap
def discard_config(
    inherit_napalm_device=None, **kwargs
):  # pylint: disable=unused-argument
    """
    Discards the changes applied.

    CLI Example:

    .. code-block:: bash

        salt '*' net.discard_config
    """

    return salt.utils.napalm.call(
        napalm_device, "discard_config", **{}  # pylint: disable=undefined-variable
    )


@salt.utils.napalm.proxy_napalm_wrap
def compare_config(
    inherit_napalm_device=None, **kwargs
):  # pylint: disable=unused-argument
    """
    Returns the difference between the running config and the candidate config.

    CLI Example:

    .. code-block:: bash

        salt '*' net.compare_config
    """

    return salt.utils.napalm.call(
        napalm_device, "compare_config", **{}  # pylint: disable=undefined-variable
    )


@salt.utils.napalm.proxy_napalm_wrap
def rollback(inherit_napalm_device=None, **kwargs):  # pylint: disable=unused-argument
    """
    Rollbacks the configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' net.rollback
    """

    return salt.utils.napalm.call(
        napalm_device, "rollback", **{}  # pylint: disable=undefined-variable
    )


@salt.utils.napalm.proxy_napalm_wrap
def config_changed(
    inherit_napalm_device=None, **kwargs
):  # pylint: disable=unused-argument
    """
    Will prompt if the configuration has been changed.

    :return: A tuple with a boolean that specifies if the config was changed on the device.\
    And a string that provides more details of the reason why the configuration was not changed.

    CLI Example:

    .. code-block:: bash

        salt '*' net.config_changed
    """

    is_config_changed = False
    reason = ""
    # pylint: disable=undefined-variable
    try_compare = compare_config(inherit_napalm_device=napalm_device)
    # pylint: enable=undefined-variable

    if try_compare.get("result"):
        if try_compare.get("out"):
            is_config_changed = True
        else:
            reason = "Configuration was not changed on the device."
    else:
        reason = try_compare.get("comment")

    return is_config_changed, reason


@salt.utils.napalm.proxy_napalm_wrap
def config_control(
    inherit_napalm_device=None, **kwargs
):  # pylint: disable=unused-argument
    """
    Will check if the configuration was changed.
    If differences found, will try to commit.
    In case commit unsuccessful, will try to rollback.

    :return: A tuple with a boolean that specifies if the config was changed/committed/rollbacked on the device.\
    And a string that provides more details of the reason why the configuration was not committed properly.

    CLI Example:

    .. code-block:: bash

        salt '*' net.config_control
    """

    result = True
    comment = ""

    # pylint: disable=undefined-variable
    changed, not_changed_rsn = config_changed(inherit_napalm_device=napalm_device)
    # pylint: enable=undefined-variable
    if not changed:
        return (changed, not_changed_rsn)

    # config changed, thus let's try to commit
    try_commit = commit()
    if not try_commit.get("result"):
        result = False
        comment = (
            "Unable to commit the changes: {reason}.\nWill try to rollback now!".format(
                reason=try_commit.get("comment")
            )
        )
        try_rollback = rollback()
        if not try_rollback.get("result"):
            comment += "\nCannot rollback! {reason}".format(
                reason=try_rollback.get("comment")
            )

    return result, comment


def cancel_commit(jid):
    """
    .. versionadded:: 2019.2.0

    Cancel a commit scheduled to be executed via the ``commit_in`` and
    ``commit_at`` arguments from the
    :py:func:`net.load_template <salt.modules.napalm_network.load_template>` or
    :py:func:`net.load_config <salt.modules.napalm_network.load_config>`
    execution functions. The commit ID is displayed when the commit is scheduled
    via the functions named above.

    CLI Example:

    .. code-block:: bash

        salt '*' net.cancel_commit 20180726083540640360
    """
    job_name = f"__napalm_commit_{jid}"
    removed = __salt__["schedule.delete"](job_name)
    if removed["result"]:
        saved = __salt__["schedule.save"]()
        removed["comment"] = f"Commit #{jid} cancelled."
    else:
        removed["comment"] = f"Unable to find commit #{jid}."
    return removed


def confirm_commit(jid):
    """
    .. versionadded:: 2019.2.0

    Confirm a commit scheduled to be reverted via the ``revert_in`` and
    ``revert_at``  arguments from the
    :mod:`net.load_template <salt.modules.napalm_network.load_template>` or
    :mod:`net.load_config <salt.modules.napalm_network.load_config>`
    execution functions. The commit ID is displayed when the commit confirmed
    is scheduled via the functions named above.

    CLI Example:

    .. code-block:: bash

        salt '*' net.confirm_commit 20180726083540640360
    """
    if __grains__["os"] == "junos":
        # Confirm the commit, by committing (i.e., invoking the RPC call)
        confirmed = __salt__["napalm.junos_commit"]()
        confirmed["result"] = confirmed.pop("out")
        confirmed["comment"] = confirmed.pop("message")
    else:
        confirmed = cancel_commit(jid)
    if confirmed["result"]:
        confirmed["comment"] = f"Commit #{jid} confirmed."
    return confirmed


def save_config(source=None, path=None):
    """
    .. versionadded:: 2019.2.0

    Save the configuration to a file on the local file system.

    source: ``running``
        The configuration source. Choose from: ``running``, ``candidate``,
        ``startup``. Default: ``running``.

    path
        Absolute path to file where to save the configuration.
        To push the files to the Master, use
        :mod:`cp.push <salt.modules.cp.push>` Execution function.

    CLI Example:

    .. code-block:: bash

        salt '*' net.save_config source=running
    """
    if not source:
        source = "running"
    if not path:
        path = salt.utils.files.mkstemp()
    running_config = __salt__["net.config"](source=source)
    if not running_config or not running_config["result"]:
        log.error("Unable to retrieve the config")
        return running_config
    with salt.utils.files.fopen(path, "w") as fh_:
        fh_.write(running_config["out"][source])
    return {
        "result": True,
        "out": path,
        "comment": f"{source} config saved to {path}",
    }


def replace_pattern(
    pattern,
    repl,
    count=0,
    flags=8,
    bufsize=1,
    append_if_not_found=False,
    prepend_if_not_found=False,
    not_found_content=None,
    search_only=False,
    show_changes=True,
    backslash_literal=False,
    source=None,
    path=None,
    test=False,
    replace=True,
    debug=False,
    commit=True,
):
    """
    .. versionadded:: 2019.2.0

    Replace occurrences of a pattern in the configuration source. If
    ``show_changes`` is ``True``, then a diff of what changed will be returned,
    otherwise a ``True`` will be returned when changes are made, and ``False``
    when no changes are made.
    This is a pure Python implementation that wraps Python's :py:func:`~re.sub`.

    pattern
        A regular expression, to be matched using Python's
        :py:func:`~re.search`.

    repl
        The replacement text.

    count: ``0``
        Maximum number of pattern occurrences to be replaced. If count is a
        positive integer ``n``, only ``n`` occurrences will be replaced,
        otherwise all occurrences will be replaced.

    flags (list or int): ``8``
        A list of flags defined in the ``re`` module documentation from the
        Python standard library. Each list item should be a string that will
        correlate to the human-friendly flag name. E.g., ``['IGNORECASE',
        'MULTILINE']``. Optionally, ``flags`` may be an int, with a value
        corresponding to the XOR (``|``) of all the desired flags. Defaults to
        8 (which supports 'MULTILINE').

    bufsize (int or str): ``1``
        How much of the configuration to buffer into memory at once. The
        default value ``1`` processes one line at a time. The special value
        ``file`` may be specified which will read the entire file into memory
        before processing.

    append_if_not_found: ``False``
        If set to ``True``, and pattern is not found, then the content will be
        appended to the file.

    prepend_if_not_found: ``False``
        If set to ``True`` and pattern is not found, then the content will be
        prepended to the file.

    not_found_content
        Content to use for append/prepend if not found. If None (default), uses
        ``repl``. Useful when ``repl`` uses references to group in pattern.

    search_only: ``False``
        If set to true, this no changes will be performed on the file, and this
        function will simply return ``True`` if the pattern was matched, and
        ``False`` if not.

    show_changes: ``True``
        If ``True``, return a diff of changes made. Otherwise, return ``True``
        if changes were made, and ``False`` if not.

    backslash_literal: ``False``
        Interpret backslashes as literal backslashes for the repl and not
        escape characters.  This will help when using append/prepend so that
        the backslashes are not interpreted for the repl on the second run of
        the state.

    source: ``running``
        The configuration source. Choose from: ``running``, ``candidate``, or
        ``startup``. Default: ``running``.

    path
        Save the temporary configuration to a specific path, then read from
        there.

    test: ``False``
        Dry run? If set as ``True``, will apply the config, discard and return
        the changes. Default: ``False`` and will commit the changes on the
        device.

    commit: ``True``
        Commit the configuration changes? Default: ``True``.

    debug: ``False``
        Debug mode. Will insert a new key in the output dictionary, as
        ``loaded_config`` containing the raw configuration loaded on the device.

    replace: ``True``
        Load and replace the configuration. Default: ``True``.

    If an equal sign (``=``) appears in an argument to a Salt command it is
    interpreted as a keyword argument in the format ``key=val``. That
    processing can be bypassed in order to pass an equal sign through to the
    remote shell command by manually specifying the kwarg:

    .. code-block:: bash

        salt '*' net.replace_pattern "bind-address\\s*=" "bind-address:"

    CLI Example:

    .. code-block:: bash

        salt '*' net.replace_pattern PREFIX-LIST_NAME new-prefix-list-name
        salt '*' net.replace_pattern bgp-group-name new-bgp-group-name count=1
    """
    config_saved = save_config(source=source, path=path)
    if not config_saved or not config_saved["result"]:
        return config_saved
    path = config_saved["out"]
    replace_pattern = __salt__["file.replace"](
        path,
        pattern,
        repl,
        count=count,
        flags=flags,
        bufsize=bufsize,
        append_if_not_found=append_if_not_found,
        prepend_if_not_found=prepend_if_not_found,
        not_found_content=not_found_content,
        search_only=search_only,
        show_changes=show_changes,
        backslash_literal=backslash_literal,
    )
    with salt.utils.files.fopen(path, "r") as fh_:
        updated_config = fh_.read()
    return __salt__["net.load_config"](
        text=updated_config, test=test, debug=debug, replace=replace, commit=commit
    )


def blockreplace(
    marker_start,
    marker_end,
    content="",
    append_if_not_found=False,
    prepend_if_not_found=False,
    show_changes=True,
    append_newline=False,
    source="running",
    path=None,
    test=False,
    commit=True,
    debug=False,
    replace=True,
):
    """
    .. versionadded:: 2019.2.0

    Replace content of the configuration source, delimited by the line markers.

    A block of content delimited by comments can help you manage several lines
    without worrying about old entries removal.

    marker_start
        The line content identifying a line as the start of the content block.
        Note that the whole line containing this marker will be considered,
        so whitespace or extra content before or after the marker is included
        in final output.

    marker_end
        The line content identifying a line as the end of the content block.
        Note that the whole line containing this marker will be considered,
        so whitespace or extra content before or after the marker is included
        in final output.

    content
        The content to be used between the two lines identified by
        ``marker_start`` and ``marker_stop``.

    append_if_not_found: ``False``
        If markers are not found and set to True then, the markers and content
        will be appended to the file.

    prepend_if_not_found: ``False``
        If markers are not found and set to True then, the markers and content
        will be prepended to the file.

    append_newline: ``False``
        Controls whether or not a newline is appended to the content block.
        If the value of this argument is ``True`` then a newline will be added
        to the content block. If it is ``False``, then a newline will not be
        added to the content block. If it is ``None`` then a newline will only
        be added to the content block if it does not already end in a newline.

    show_changes: ``True``
        Controls how changes are presented. If ``True``, this function will
        return the of the changes made.
        If ``False``, then it will return a boolean (``True`` if any changes
        were made, otherwise False).

    source: ``running``
        The configuration source. Choose from: ``running``, ``candidate``, or
        ``startup``. Default: ``running``.

    path: ``None``
        Save the temporary configuration to a specific path, then read from
        there. This argument is optional, can be used when you prefers a
        particular location of the temporary file.

    test: ``False``
        Dry run? If set as ``True``, will apply the config, discard and return
        the changes. Default: ``False`` and will commit the changes on the
        device.

    commit: ``True``
        Commit the configuration changes? Default: ``True``.

    debug: ``False``
        Debug mode. Will insert a new key in the output dictionary, as
        ``loaded_config`` containing the raw configuration loaded on the device.

    replace: ``True``
        Load and replace the configuration. Default: ``True``.

    CLI Example:

    .. code-block:: bash

        salt '*' net.blockreplace 'ntp' 'interface' ''
    """
    config_saved = save_config(source=source, path=path)
    if not config_saved or not config_saved["result"]:
        return config_saved
    path = config_saved["out"]
    replace_pattern = __salt__["file.blockreplace"](
        path,
        marker_start=marker_start,
        marker_end=marker_end,
        content=content,
        append_if_not_found=append_if_not_found,
        prepend_if_not_found=prepend_if_not_found,
        show_changes=show_changes,
        append_newline=append_newline,
    )
    with salt.utils.files.fopen(path, "r") as fh_:
        updated_config = fh_.read()
    return __salt__["net.load_config"](
        text=updated_config, test=test, debug=debug, replace=replace, commit=commit
    )


def patch(
    patchfile,
    options="",
    saltenv="base",
    source_hash=None,
    show_changes=True,
    source="running",
    path=None,
    test=False,
    commit=True,
    debug=False,
    replace=True,
):
    """
    .. versionadded:: 2019.2.0

    Apply a patch to the configuration source, and load the result into the
    running config of the device.

    patchfile
        A patch file to apply to the configuration source.

    options
        Options to pass to patch.

    source_hash
        If the patch file (specified via the ``patchfile`` argument)  is an
        HTTP(S) or FTP URL and the file exists in the minion's file cache, this
        option can be passed to keep the minion from re-downloading the file if
        the cached copy matches the specified hash.

    show_changes: ``True``
        Controls how changes are presented. If ``True``, this function will
        return the of the changes made.
        If ``False``, then it will return a boolean (``True`` if any changes
        were made, otherwise False).

    source: ``running``
        The configuration source. Choose from: ``running``, ``candidate``, or
        ``startup``. Default: ``running``.

    path: ``None``
        Save the temporary configuration to a specific path, then read from
        there. This argument is optional, can the user prefers a particular
        location of the temporary file.

    test: ``False``
        Dry run? If set as ``True``, will apply the config, discard and return
        the changes. Default: ``False`` and will commit the changes on the
        device.

    commit: ``True``
        Commit the configuration changes? Default: ``True``.

    debug: ``False``
        Debug mode. Will insert a new key in the output dictionary, as
        ``loaded_config`` containing the raw configuration loaded on the device.

    replace: ``True``
        Load and replace the configuration. Default: ``True``.

    CLI Example:

    .. code-block:: bash

        salt '*' net.patch https://example.com/running_config.patch
    """
    config_saved = save_config(source=source, path=path)
    if not config_saved or not config_saved["result"]:
        return config_saved
    path = config_saved["out"]
    patchfile_cache = __salt__["cp.cache_file"](patchfile)
    if patchfile_cache is False:
        return {
            "out": None,
            "result": False,
            "comment": f'The file "{patchfile}" does not exist.',
        }
    replace_pattern = __salt__["file.patch"](path, patchfile_cache, options=options)
    with salt.utils.files.fopen(path, "r") as fh_:
        updated_config = fh_.read()
    return __salt__["net.load_config"](
        text=updated_config, test=test, debug=debug, replace=replace, commit=commit
    )


# <---- Configuration specific functions -------------------------------------------------------------------------------
