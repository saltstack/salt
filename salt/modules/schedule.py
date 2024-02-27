"""
Module for managing the Salt schedule on a minion

Requires that python-dateutil is installed on the minion.

.. versionadded:: 2014.7.0

"""

import copy as pycopy
import datetime
import logging
import os

import yaml

import salt.utils.event
import salt.utils.files
import salt.utils.odict
import salt.utils.yaml

try:
    import dateutil.parser as dateutil_parser

    _WHEN_SUPPORTED = True
    _RANGE_SUPPORTED = True
except ImportError:
    _WHEN_SUPPORTED = False
    _RANGE_SUPPORTED = False

__proxyenabled__ = ["*"]

log = logging.getLogger(__name__)

__func_alias__ = {"list_": "list", "reload_": "reload"}

SCHEDULE_CONF = [
    "name",
    "maxrunning",
    "function",
    "splay",
    "range",
    "when",
    "once",
    "once_fmt",
    "returner",
    "jid_include",
    "args",
    "kwargs",
    "_seconds",
    "seconds",
    "minutes",
    "hours",
    "days",
    "enabled",
    "return_job",
    "metadata",
    "cron",
    "until",
    "after",
    "return_config",
    "return_kwargs",
    "run_on_start",
    "skip_during_range",
    "run_after_skip_range",
]


def _get_schedule_config_file():
    """
    Return the minion schedule configuration file
    """
    config_dir = __opts__.get("conf_dir", None)
    if config_dir is None and "conf_file" in __opts__:
        config_dir = os.path.dirname(__opts__["conf_file"])
    if config_dir is None:
        config_dir = salt.syspaths.CONFIG_DIR

    minion_d_dir = os.path.join(
        config_dir,
        os.path.dirname(
            __opts__.get(
                "default_include",
                salt.config.DEFAULT_MINION_OPTS["default_include"],
            )
        ),
    )

    if not os.path.isdir(config_dir):
        os.makedirs(config_dir)

    if not os.path.isdir(minion_d_dir):
        os.makedirs(minion_d_dir)

    return os.path.join(minion_d_dir, "_schedule.conf")


def list_(
    show_all=False, show_disabled=True, where=None, return_yaml=True, offline=False
):
    """
    List the jobs currently scheduled on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.list

        # Show all jobs including hidden internal jobs
        salt '*' schedule.list show_all=True

        # Hide disabled jobs from list of jobs
        salt '*' schedule.list show_disabled=False

    """

    def _get_saved():
        schedule = {}
        schedule_config = _get_schedule_config_file()
        if os.path.exists(schedule_config):
            with salt.utils.files.fopen(schedule_config) as fp_:
                schedule_yaml = fp_.read()
                if schedule_yaml:
                    schedule_contents = yaml.safe_load(schedule_yaml)
                    schedule = schedule_contents.get("schedule", {})
        return schedule

    schedule = {}
    if offline:
        schedule = _get_saved()
        saved_schedule = pycopy.deepcopy(schedule)
    else:
        try:
            with salt.utils.event.get_event("minion", opts=__opts__) as event_bus:
                res = __salt__["event.fire"](
                    {"func": "list", "where": where}, "manage_schedule"
                )
                if res:
                    event_ret = event_bus.get_event(
                        tag="/salt/minion/minion_schedule_list_complete", wait=30
                    )
                    if event_ret and event_ret["complete"]:
                        schedule = event_ret["schedule"]
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret = {}
            ret["comment"] = "Event module not available. Schedule list failed."
            ret["result"] = True
            log.debug("Event module not available. Schedule list failed.")
            return ret

        saved_schedule = _get_saved()

    _hidden = ["enabled", "skip_function", "skip_during_range"]
    for job in list(schedule.keys()):  # iterate over a copy since we will mutate it
        if job in _hidden:
            continue

        # Default jobs added by salt begin with __
        # by default hide them unless show_all is True.
        if job.startswith("__") and not show_all:
            del schedule[job]
            continue

        # if enabled is not included in the job,
        # assume job is enabled.
        if "enabled" not in schedule[job]:
            schedule[job]["enabled"] = True

        for item in pycopy.copy(schedule[job]):
            if item not in SCHEDULE_CONF:
                del schedule[job][item]
                continue
            if schedule[job][item] is None:
                del schedule[job][item]
                continue
            if schedule[job][item] == "true":
                schedule[job][item] = True
            if schedule[job][item] == "false":
                schedule[job][item] = False

        # if the job is disabled and show_disabled is False, skip job
        if not show_disabled and not schedule[job]["enabled"]:
            del schedule[job]
            continue

        if "_seconds" in schedule[job]:
            # remove _seconds from the listing
            del schedule[job]["_seconds"]

    if return_yaml:
        # Indicate whether the scheduled job is saved
        # to the minion configuration.
        for item in schedule:
            if isinstance(schedule[item], dict):
                if item in saved_schedule:
                    schedule[item]["saved"] = True
                else:
                    schedule[item]["saved"] = False
        tmp = {"schedule": schedule}
        return salt.utils.yaml.safe_dump(tmp, default_flow_style=False)
    else:
        return schedule


def is_enabled(name=None):
    """
    List a Job only if its enabled

    If job is not specified, indicate
    if the scheduler is enabled or disabled.

    .. versionadded:: 2015.5.3

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.is_enabled name=job_name
        salt '*' schedule.is_enabled
    """

    current_schedule = __salt__["schedule.list"](show_all=False, return_yaml=False)
    if not name:
        return current_schedule.get("enabled", True)
    else:
        if name in current_schedule:
            return current_schedule[name]
        else:
            return {}


def purge(**kwargs):
    """
    Purge all the jobs currently scheduled on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.purge

        # Purge jobs on Salt minion
        salt '*' schedule.purge

    """

    ret = {"comment": [], "changes": {}, "result": True}

    current_schedule = list_(
        show_all=True, return_yaml=False, offline=kwargs.get("offline")
    )
    for name in pycopy.deepcopy(current_schedule):
        if name == "enabled":
            continue
        if name.startswith("__"):
            continue

        if "test" in kwargs and kwargs["test"]:
            ret["result"] = True
            ret["comment"].append(f"Job: {name} would be deleted from schedule.")
        else:
            if kwargs.get("offline"):
                del current_schedule[name]

                ret["comment"].append(f"Deleted job: {name} from schedule.")
                ret["changes"][name] = "removed"

            else:
                persist = kwargs.get("persist", True)
                try:
                    with salt.utils.event.get_event(
                        "minion", opts=__opts__
                    ) as event_bus:
                        res = __salt__["event.fire"](
                            {"name": name, "func": "delete", "persist": persist},
                            "manage_schedule",
                        )
                        if res:
                            event_ret = event_bus.get_event(
                                tag="/salt/minion/minion_schedule_delete_complete",
                                wait=30,
                            )
                            if event_ret and event_ret["complete"]:
                                _schedule_ret = event_ret["schedule"]
                                if name not in _schedule_ret:
                                    ret["result"] = True
                                    ret["changes"][name] = "removed"
                                    ret["comment"].append(
                                        f"Deleted job: {name} from schedule."
                                    )
                                else:
                                    ret["comment"].append(
                                        "Failed to delete job {} from schedule.".format(
                                            name
                                        )
                                    )
                                    ret["result"] = True

                except KeyError:
                    # Effectively a no-op, since we can't really return without an event system
                    ret["comment"] = "Event module not available. Schedule add failed."
                    ret["result"] = True

    # wait until the end to write file in offline mode
    if kwargs.get("offline"):
        schedule_conf = _get_schedule_config_file()

        try:
            with salt.utils.files.fopen(schedule_conf, "wb+") as fp_:
                fp_.write(
                    salt.utils.stringutils.to_bytes(
                        salt.utils.yaml.safe_dump({"schedule": current_schedule})
                    )
                )
        except OSError:
            log.error(
                "Failed to persist the updated schedule",
                exc_info_on_loglevel=logging.DEBUG,
            )

    return ret


def delete(name, **kwargs):
    """
    Delete a job from the minion's schedule

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.delete job1

        # Delete job on Salt minion when the Salt minion is not running
        salt '*' schedule.delete job1

    """

    ret = {
        "comment": f"Failed to delete job {name} from schedule.",
        "result": False,
        "changes": {},
    }

    if not name:
        ret["comment"] = "Job name is required."

    if "test" in kwargs and kwargs["test"]:
        ret["comment"] = f"Job: {name} would be deleted from schedule."
        ret["result"] = True
    else:
        if kwargs.get("offline"):
            current_schedule = list_(
                show_all=True,
                where="opts",
                return_yaml=False,
                offline=kwargs.get("offline"),
            )

            del current_schedule[name]

            schedule_conf = _get_schedule_config_file()

            try:
                with salt.utils.files.fopen(schedule_conf, "wb+") as fp_:
                    fp_.write(
                        salt.utils.stringutils.to_bytes(
                            salt.utils.yaml.safe_dump({"schedule": current_schedule})
                        )
                    )
            except OSError:
                log.error(
                    "Failed to persist the updated schedule",
                    exc_info_on_loglevel=logging.DEBUG,
                )

            ret["result"] = True
            ret["comment"] = f"Deleted Job {name} from schedule."
            ret["changes"][name] = "removed"
        else:
            persist = kwargs.get("persist", True)

            if name in list_(
                show_all=True,
                where="opts",
                return_yaml=False,
                offline=kwargs.get("offline"),
            ):
                event_data = {"name": name, "func": "delete", "persist": persist}
            elif name in list_(
                show_all=True,
                where="pillar",
                return_yaml=False,
                offline=kwargs.get("offline"),
            ):
                event_data = {
                    "name": name,
                    "where": "pillar",
                    "func": "delete",
                    "persist": False,
                }
            else:
                ret["comment"] = f"Job {name} does not exist."
                return ret

            try:
                with salt.utils.event.get_event("minion", opts=__opts__) as event_bus:
                    res = __salt__["event.fire"](event_data, "manage_schedule")
                    if res:
                        event_ret = event_bus.get_event(
                            tag="/salt/minion/minion_schedule_delete_complete",
                            wait=30,
                        )
                        if event_ret and event_ret["complete"]:
                            schedule = event_ret["schedule"]
                            if name not in schedule:
                                ret["result"] = True
                                ret["comment"] = "Deleted Job {} from schedule.".format(
                                    name
                                )
                                ret["changes"][name] = "removed"
                            else:
                                ret["comment"] = (
                                    "Failed to delete job {} from schedule.".format(
                                        name
                                    )
                                )
                            return ret
            except KeyError:
                # Effectively a no-op, since we can't really return without an event system
                ret["comment"] = "Event module not available. Schedule add failed."
    return ret


def build_schedule_item(name, **kwargs):
    """
    Build a schedule job

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.build_schedule_item job1 function='test.ping' seconds=3600
    """

    ret = {"comment": [], "result": True}

    if not name:
        ret["comment"] = "Job name is required."
        ret["result"] = False
        return ret

    schedule = {}
    schedule[name] = salt.utils.odict.OrderedDict()
    schedule[name]["function"] = kwargs["function"]

    time_conflict = False
    for item in ["seconds", "minutes", "hours", "days"]:
        if item in kwargs and "when" in kwargs:
            time_conflict = True

        if item in kwargs and "cron" in kwargs:
            time_conflict = True

    if time_conflict:
        ret["result"] = False
        ret["comment"] = (
            'Unable to use "seconds", "minutes", "hours", or "days" with "when" or'
            ' "cron" options.'
        )
        return ret

    if "when" in kwargs and "cron" in kwargs:
        ret["result"] = False
        ret["comment"] = 'Unable to use "when" and "cron" options together.  Ignoring.'
        return ret

    for item in ["seconds", "minutes", "hours", "days"]:
        if item in kwargs:
            schedule[name][item] = kwargs[item]

    if "return_job" in kwargs:
        schedule[name]["return_job"] = kwargs["return_job"]

    if "metadata" in kwargs:
        schedule[name]["metadata"] = kwargs["metadata"]

    if "job_args" in kwargs:
        if isinstance(kwargs["job_args"], list):
            schedule[name]["args"] = kwargs["job_args"]
        else:
            ret["result"] = False
            ret["comment"] = "job_args is not a list. please correct and try again."
            return ret

    if "job_kwargs" in kwargs:
        if isinstance(kwargs["job_kwargs"], dict):
            schedule[name]["kwargs"] = kwargs["job_kwargs"]
        else:
            ret["result"] = False
            ret["comment"] = "job_kwargs is not a dict. please correct and try again."
            return ret

    if "maxrunning" in kwargs:
        schedule[name]["maxrunning"] = kwargs["maxrunning"]
    else:
        schedule[name]["maxrunning"] = 1

    if "name" in kwargs:
        schedule[name]["name"] = kwargs["name"]
    else:
        schedule[name]["name"] = name

    if "enabled" in kwargs:
        schedule[name]["enabled"] = kwargs["enabled"]
    else:
        schedule[name]["enabled"] = True

    schedule[name]["jid_include"] = kwargs.get("jid_include", True)

    if "splay" in kwargs:
        if isinstance(kwargs["splay"], dict):
            # Ensure ordering of start and end arguments
            schedule[name]["splay"] = salt.utils.odict.OrderedDict()
            schedule[name]["splay"]["start"] = kwargs["splay"]["start"]
            schedule[name]["splay"]["end"] = kwargs["splay"]["end"]
        else:
            schedule[name]["splay"] = kwargs["splay"]

    if "when" in kwargs:
        if not _WHEN_SUPPORTED:
            ret["result"] = False
            ret["comment"] = 'Missing dateutil.parser, "when" is unavailable.'
            return ret
        else:
            validate_when = kwargs["when"]
            if not isinstance(validate_when, list):
                validate_when = [validate_when]
            for _when in validate_when:
                try:
                    dateutil_parser.parse(_when)
                except ValueError:
                    ret["result"] = False
                    ret["comment"] = 'Schedule item {} for "when" in invalid.'.format(
                        _when
                    )
                    return ret

    for item in [
        "range",
        "when",
        "once",
        "once_fmt",
        "cron",
        "returner",
        "after",
        "return_config",
        "return_kwargs",
        "until",
        "run_on_start",
        "skip_during_range",
    ]:
        if item in kwargs:
            schedule[name][item] = kwargs[item]

    return schedule[name]


def add(name, **kwargs):
    """
    Add a job to the schedule

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.add job1 function='test.ping' seconds=3600
        # If function have some arguments, use job_args
        salt '*' schedule.add job2 function='cmd.run' job_args="['date >> /tmp/date.log']" seconds=60

        # Add job to Salt minion when the Salt minion is not running
        salt '*' schedule.add job1 function='test.ping' seconds=3600 offline=True

    """

    ret = {
        "comment": f"Failed to add job {name} to schedule.",
        "result": False,
        "changes": {},
    }
    current_schedule = list_(
        show_all=True, return_yaml=False, offline=kwargs.get("offline")
    )

    if name in current_schedule:
        ret["comment"] = f"Job {name} already exists in schedule."
        ret["result"] = False
        return ret

    if not name:
        ret["comment"] = "Job name is required."
        ret["result"] = False

    time_conflict = False
    for item in ["seconds", "minutes", "hours", "days"]:
        if item in kwargs and "when" in kwargs:
            time_conflict = True
        if item in kwargs and "cron" in kwargs:
            time_conflict = True

    if time_conflict:
        ret["comment"] = (
            'Error: Unable to use "seconds", "minutes", "hours", or "days" with "when"'
            ' or "cron" options.'
        )
        return ret

    if "when" in kwargs and "cron" in kwargs:
        ret["comment"] = 'Unable to use "when" and "cron" options together.  Ignoring.'
        return ret

    persist = kwargs.get("persist", True)

    _new = build_schedule_item(name, **kwargs)
    if "result" in _new and not _new["result"]:
        return _new

    schedule_data = {}
    schedule_data[name] = _new

    if "test" in kwargs and kwargs["test"]:
        ret["comment"] = f"Job: {name} would be added to schedule."
        ret["result"] = True
    else:
        if kwargs.get("offline"):
            current_schedule.update(schedule_data)

            schedule_conf = _get_schedule_config_file()

            try:
                with salt.utils.files.fopen(schedule_conf, "wb+") as fp_:
                    fp_.write(
                        salt.utils.stringutils.to_bytes(
                            salt.utils.yaml.safe_dump({"schedule": current_schedule})
                        )
                    )
            except OSError:
                log.error(
                    "Failed to persist the updated schedule",
                    exc_info_on_loglevel=logging.DEBUG,
                )

            ret["result"] = True
            ret["comment"] = f"Added job: {name} to schedule."
            ret["changes"][name] = "added"
        else:
            try:
                with salt.utils.event.get_event("minion", opts=__opts__) as event_bus:
                    res = __salt__["event.fire"](
                        {
                            "name": name,
                            "schedule": schedule_data,
                            "func": "add",
                            "persist": persist,
                        },
                        "manage_schedule",
                    )
                    if res:
                        event_ret = event_bus.get_event(
                            tag="/salt/minion/minion_schedule_add_complete",
                            wait=30,
                        )
                        if event_ret and event_ret["complete"]:
                            schedule = event_ret["schedule"]
                            if name in schedule:
                                ret["result"] = True
                                ret["comment"] = "Added job: {} to schedule.".format(
                                    name
                                )
                                ret["changes"][name] = "added"
                                return ret
            except KeyError:
                # Effectively a no-op, since we can't really return without an event system
                ret["comment"] = "Event module not available. Schedule add failed."
    return ret


def modify(name, **kwargs):
    """
    Modify an existing job in the schedule

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.modify job1 function='test.ping' seconds=3600

        # Modify job on Salt minion when the Salt minion is not running
        salt '*' schedule.modify job1 function='test.ping' seconds=3600 offline=True

    """

    ret = {"comment": "", "changes": {}, "result": True}

    time_conflict = False
    for item in ["seconds", "minutes", "hours", "days"]:
        if item in kwargs and "when" in kwargs:
            time_conflict = True

        if item in kwargs and "cron" in kwargs:
            time_conflict = True

    if time_conflict:
        ret["result"] = False
        ret["comment"] = (
            'Error: Unable to use "seconds", "minutes", "hours", or "days" with "when"'
            " option."
        )
        return ret

    if "when" in kwargs and "cron" in kwargs:
        ret["result"] = False
        ret["comment"] = 'Unable to use "when" and "cron" options together.  Ignoring.'
        return ret

    current_schedule = list_(
        show_all=True, return_yaml=False, offline=kwargs.get("offline")
    )

    if name not in current_schedule:
        ret["comment"] = f"Job {name} does not exist in schedule."
        ret["result"] = False
        return ret

    _current = current_schedule[name]

    if "function" not in kwargs:
        kwargs["function"] = _current.get("function")

    # Remove the auto generated _seconds value
    if "_seconds" in _current:
        _current["seconds"] = _current.pop("_seconds")

    # Copy _current _new, then update values from kwargs
    _new = build_schedule_item(name, **kwargs)

    # Remove test from kwargs, it's not a valid schedule option
    _new.pop("test", None)

    if "result" in _new and not _new["result"]:
        return _new

    if _new == _current:
        ret["comment"] = f"Job {name} in correct state"
        return ret

    ret["changes"][name] = {
        "old": salt.utils.odict.OrderedDict(_current),
        "new": salt.utils.odict.OrderedDict(_new),
    }

    if "test" in kwargs and kwargs["test"]:
        ret["comment"] = f"Job: {name} would be modified in schedule."
    else:
        if kwargs.get("offline"):
            current_schedule[name].update(_new)

            schedule_conf = _get_schedule_config_file()

            try:
                with salt.utils.files.fopen(schedule_conf, "wb+") as fp_:
                    fp_.write(
                        salt.utils.stringutils.to_bytes(
                            salt.utils.yaml.safe_dump({"schedule": current_schedule})
                        )
                    )
            except OSError:
                log.error(
                    "Failed to persist the updated schedule",
                    exc_info_on_loglevel=logging.DEBUG,
                )

            ret["result"] = True
            ret["comment"] = f"Modified job: {name} in schedule."

        else:
            persist = kwargs.get("persist", True)
            if name in list_(show_all=True, where="opts", return_yaml=False):
                event_data = {
                    "name": name,
                    "schedule": _new,
                    "func": "modify",
                    "persist": persist,
                }
            elif name in list_(show_all=True, where="pillar", return_yaml=False):
                event_data = {
                    "name": name,
                    "schedule": _new,
                    "where": "pillar",
                    "func": "modify",
                    "persist": False,
                }

            out = __salt__["event.fire"](event_data, "manage_schedule")
            if out:
                ret["comment"] = f"Modified job: {name} in schedule."
            else:
                ret["comment"] = f"Failed to modify job {name} in schedule."
                ret["result"] = False
    return ret


def run_job(name, force=False):
    """
    Run a scheduled job on the minion immediately

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.run_job job1

        salt '*' schedule.run_job job1 force=True
        Force the job to run even if it is disabled.
    """

    ret = {"comment": [], "result": True}

    if not name:
        ret["comment"] = "Job name is required."
        ret["result"] = False

    schedule = list_(show_all=True, return_yaml=False)
    if name in schedule:
        data = schedule[name]
        if "enabled" in data and not data["enabled"] and not force:
            ret["comment"] = f"Job {name} is disabled."
        else:
            out = __salt__["event.fire"](
                {"name": name, "func": "run_job"}, "manage_schedule"
            )
            if out:
                ret["comment"] = f"Scheduling Job {name} on minion."
            else:
                ret["comment"] = f"Failed to run job {name} on minion."
                ret["result"] = False
    else:
        ret["comment"] = f"Job {name} does not exist."
        ret["result"] = False
    return ret


def enable_job(name, **kwargs):
    """
    Enable a job in the minion's schedule

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.enable_job job1
    """

    ret = {"comment": [], "result": True, "changes": {}}

    if not name:
        ret["comment"] = "Job name is required."
        ret["result"] = False

    if "test" in __opts__ and __opts__["test"]:
        ret["comment"] = f"Job: {name} would be enabled in schedule."
    else:
        persist = kwargs.get("persist", True)

        if name in list_(show_all=True, where="opts", return_yaml=False):
            event_data = {"name": name, "func": "enable_job", "persist": persist}
        elif name in list_(show_all=True, where="pillar", return_yaml=False):
            event_data = {
                "name": name,
                "where": "pillar",
                "func": "enable_job",
                "persist": False,
            }
        else:
            ret["comment"] = f"Job {name} does not exist."
            ret["result"] = False
            return ret

        try:
            with salt.utils.event.get_event("minion", opts=__opts__) as event_bus:
                res = __salt__["event.fire"](event_data, "manage_schedule")
                if res:
                    event_ret = event_bus.get_event(
                        tag="/salt/minion/minion_schedule_enabled_job_complete",
                        wait=30,
                    )
                    if event_ret and event_ret["complete"]:
                        schedule = event_ret["schedule"]
                        # check item exists in schedule and is enabled
                        if name in schedule and schedule[name]["enabled"]:
                            ret["result"] = True
                            ret["comment"] = f"Enabled Job {name} in schedule."
                            ret["changes"][name] = "enabled"
                        else:
                            ret["result"] = False
                            ret["comment"] = f"Failed to enable job {name} in schedule."
                        return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret["comment"] = "Event module not available. Schedule enable job failed."
    return ret


def disable_job(name, **kwargs):
    """
    Disable a job in the minion's schedule

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.disable_job job1
    """

    ret = {"comment": [], "result": True, "changes": {}}

    if not name:
        ret["comment"] = "Job name is required."
        ret["result"] = False

    if "test" in kwargs and kwargs["test"]:
        ret["comment"] = f"Job: {name} would be disabled in schedule."
    else:
        persist = kwargs.get("persist", True)

        if name in list_(show_all=True, where="opts", return_yaml=False):
            event_data = {"name": name, "func": "disable_job", "persist": persist}
        elif name in list_(show_all=True, where="pillar"):
            event_data = {
                "name": name,
                "where": "pillar",
                "func": "disable_job",
                "persist": False,
            }
        else:
            ret["comment"] = f"Job {name} does not exist."
            ret["result"] = False
            return ret

        try:
            with salt.utils.event.get_event("minion", opts=__opts__) as event_bus:
                res = __salt__["event.fire"](event_data, "manage_schedule")
                if res:
                    event_ret = event_bus.get_event(
                        tag="/salt/minion/minion_schedule_disabled_job_complete",
                        wait=30,
                    )
                    if event_ret and event_ret["complete"]:
                        schedule = event_ret["schedule"]
                        # check item exists in schedule and is enabled
                        if name in schedule and not schedule[name]["enabled"]:
                            ret["result"] = True
                            ret["comment"] = f"Disabled Job {name} in schedule."
                            ret["changes"][name] = "disabled"
                        else:
                            ret["result"] = False
                            ret["comment"] = (
                                f"Failed to disable job {name} in schedule."
                            )
                        return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret["comment"] = "Event module not available. Schedule enable job failed."
    return ret


def save(**kwargs):
    """
    Save all scheduled jobs on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.save
    """

    ret = {"comment": [], "result": True}

    if "test" in kwargs and kwargs["test"]:
        ret["comment"] = "Schedule would be saved."
    else:
        try:
            with salt.utils.event.get_event("minion", opts=__opts__) as event_bus:
                res = __salt__["event.fire"](
                    {"func": "save_schedule"}, "manage_schedule"
                )
                if res:
                    event_ret = event_bus.get_event(
                        tag="/salt/minion/minion_schedule_saved",
                        wait=30,
                    )
                    if event_ret and event_ret["complete"]:
                        ret["result"] = True
                        ret["comment"] = "Schedule (non-pillar items) saved."
                    else:
                        ret["result"] = False
                        ret["comment"] = "Failed to save schedule."
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret["comment"] = "Event module not available. Schedule save failed."
    return ret


def enable(**kwargs):
    """
    Enable all scheduled jobs on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.enable
    """

    ret = {"comment": [], "changes": {}, "result": True}

    if "test" in kwargs and kwargs["test"]:
        ret["comment"] = "Schedule would be enabled."
    else:
        persist = kwargs.get("persist", True)

        try:
            with salt.utils.event.get_event("minion", opts=__opts__) as event_bus:
                res = __salt__["event.fire"](
                    {"func": "enable", "persist": persist}, "manage_schedule"
                )
                if res:
                    event_ret = event_bus.get_event(
                        tag="/salt/minion/minion_schedule_enabled_complete",
                        wait=30,
                    )
                    if event_ret and event_ret["complete"]:
                        schedule = event_ret["schedule"]
                        if "enabled" in schedule and schedule["enabled"]:
                            ret["result"] = True
                            ret["comment"] = "Enabled schedule on minion."
                            ret["changes"]["schedule"] = "enabled"
                        else:
                            ret["result"] = False
                            ret["comment"] = "Failed to enable schedule on minion."
                        return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret["comment"] = "Event module not available. Schedule enable job failed."
    return ret


def disable(**kwargs):
    """
    Disable all scheduled jobs on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.disable
    """

    ret = {"comment": [], "changes": {}, "result": True}

    if "test" in kwargs and kwargs["test"]:
        ret["comment"] = "Schedule would be disabled."
    else:
        persist = kwargs.get("persist", True)

        try:
            with salt.utils.event.get_event("minion", opts=__opts__) as event_bus:
                res = __salt__["event.fire"](
                    {"func": "disable", "persist": persist}, "manage_schedule"
                )
                if res:
                    event_ret = event_bus.get_event(
                        tag="/salt/minion/minion_schedule_disabled_complete",
                        wait=30,
                    )
                    if event_ret and event_ret["complete"]:
                        schedule = event_ret["schedule"]
                        if "enabled" in schedule and not schedule["enabled"]:
                            ret["result"] = True
                            ret["comment"] = "Disabled schedule on minion."
                            ret["changes"]["schedule"] = "disabled"
                        else:
                            ret["result"] = False
                            ret["comment"] = "Failed to disable schedule on minion."
                        return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret["comment"] = "Event module not available. Schedule disable job failed."
    return ret


def reload_():
    """
    Reload saved scheduled jobs on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.reload
    """

    ret = {"comment": [], "result": True}

    # If there a schedule defined in pillar, refresh it.
    if "schedule" in __pillar__:
        out = __salt__["event.fire"]({}, "pillar_refresh")
        if out:
            ret["comment"].append("Reloaded schedule from pillar on minion.")
        else:
            ret["comment"].append("Failed to reload schedule from pillar on minion.")
            ret["result"] = False

    # move this file into an configurable opt
    sfn = "{}/{}/schedule.conf".format(
        __opts__["config_dir"], os.path.dirname(__opts__["default_include"])
    )
    if os.path.isfile(sfn):
        with salt.utils.files.fopen(sfn, "rb") as fp_:
            try:
                schedule = salt.utils.yaml.safe_load(fp_)
            except salt.utils.yaml.YAMLError as exc:
                ret["comment"].append(f"Unable to read existing schedule file: {exc}")

        if schedule:
            if "schedule" in schedule and schedule["schedule"]:
                out = __salt__["event.fire"](
                    {"func": "reload", "schedule": schedule}, "manage_schedule"
                )
                if out:
                    ret["comment"].append(
                        "Reloaded schedule on minion from schedule.conf."
                    )
                else:
                    ret["comment"].append(
                        "Failed to reload schedule on minion from schedule.conf."
                    )
                    ret["result"] = False
            else:
                ret["comment"].append(
                    "Failed to reload schedule on minion.  Saved file is empty or"
                    " invalid."
                )
                ret["result"] = False
        else:
            ret["comment"].append(
                "Failed to reload schedule on minion.  Saved file is empty or invalid."
            )
            ret["result"] = False
    return ret


def move(name, target, **kwargs):
    """
    Move scheduled job to another minion or minions.

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.move jobname target
    """

    ret = {"comment": [], "result": True}

    if not name:
        ret["comment"] = "Job name is required."
        ret["result"] = False

    if "test" in kwargs and kwargs["test"]:
        ret["comment"] = f"Job: {name} would be moved from schedule."
    else:
        opts_schedule = list_(show_all=True, where="opts", return_yaml=False)
        pillar_schedule = list_(show_all=True, where="pillar", return_yaml=False)

        if name in opts_schedule:
            schedule_data = opts_schedule[name]
            where = None
        elif name in pillar_schedule:
            schedule_data = pillar_schedule[name]
            where = "pillar"
        else:
            ret["comment"] = f"Job {name} does not exist."
            ret["result"] = False
            return ret

        schedule_opts = []
        for key, value in schedule_data.items():
            temp = f"{key}={value}"
            schedule_opts.append(temp)
        response = __salt__["publish.publish"](target, "schedule.add", schedule_opts)

        # Get errors and list of affeced minions
        errors = []
        minions = []
        for minion in response:
            minions.append(minion)
            if not response[minion]:
                errors.append(minion)

        # parse response
        if not response:
            ret["comment"] = "no servers answered the published schedule.add command"
            return ret
        elif errors:
            ret["comment"] = "the following minions return False"
            ret["minions"] = errors
            return ret
        else:
            delete(name, where=where)
            ret["result"] = True
            ret["comment"] = f"Moved Job {name} from schedule."
            ret["minions"] = minions
            return ret
    return ret


def copy(name, target, **kwargs):
    """
    Copy scheduled job to another minion or minions.

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.copy jobname target
    """

    ret = {"comment": [], "result": True}

    if not name:
        ret["comment"] = "Job name is required."
        ret["result"] = False

    if "test" in kwargs and kwargs["test"]:
        ret["comment"] = f"Job: {name} would be copied from schedule."
    else:
        opts_schedule = list_(show_all=True, where="opts", return_yaml=False)
        pillar_schedule = list_(show_all=True, where="pillar", return_yaml=False)

        if name in opts_schedule:
            schedule_data = opts_schedule[name]
        elif name in pillar_schedule:
            schedule_data = pillar_schedule[name]
        else:
            ret["comment"] = f"Job {name} does not exist."
            ret["result"] = False
            return ret

        schedule_opts = []
        for key, value in schedule_data.items():
            temp = f"{key}={value}"
            schedule_opts.append(temp)
        response = __salt__["publish.publish"](target, "schedule.add", schedule_opts)

        # Get errors and list of affeced minions
        errors = []
        minions = []
        for minion in response:
            minions.append(minion)
            if not response[minion]:
                errors.append(minion)

        # parse response
        if not response:
            ret["comment"] = "no servers answered the published schedule.add command"
            return ret
        elif errors:
            ret["comment"] = "the following minions return False"
            ret["minions"] = errors
            return ret
        else:
            ret["result"] = True
            ret["comment"] = f"Copied Job {name} from schedule to minion(s)."
            ret["minions"] = minions
            return ret
    return ret


def postpone_job(name, current_time, new_time, **kwargs):
    """
    Postpone a job in the minion's schedule

    Current time and new time should be in date string format,
    default value is %Y-%m-%dT%H:%M:%S.

    .. versionadded:: 2018.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.postpone_job job current_time new_time

        salt '*' schedule.postpone_job job current_time new_time time_fmt='%Y-%m-%dT%H:%M:%S'
    """

    time_fmt = kwargs.get("time_fmt") or "%Y-%m-%dT%H:%M:%S"
    ret = {"comment": [], "result": True}

    if not name:
        ret["comment"] = "Job name is required."
        ret["result"] = False
        return ret

    if not current_time:
        ret["comment"] = "Job current time is required."
        ret["result"] = False
        return ret
    else:
        try:
            # Validate date string
            datetime.datetime.strptime(current_time, time_fmt)
        except (TypeError, ValueError):
            log.error("Date string could not be parsed: %s, %s", new_time, time_fmt)

            ret["comment"] = "Date string could not be parsed."
            ret["result"] = False
            return ret

    if not new_time:
        ret["comment"] = "Job new_time is required."
        ret["result"] = False
        return ret
    else:
        try:
            # Validate date string
            datetime.datetime.strptime(new_time, time_fmt)
        except (TypeError, ValueError):
            log.error("Date string could not be parsed: %s, %s", new_time, time_fmt)

            ret["comment"] = "Date string could not be parsed."
            ret["result"] = False
            return ret

    if "test" in __opts__ and __opts__["test"]:
        ret["comment"] = f"Job: {name} would be postponed in schedule."
    else:

        if name in list_(show_all=True, where="opts", return_yaml=False):
            event_data = {
                "name": name,
                "time": current_time,
                "new_time": new_time,
                "time_fmt": time_fmt,
                "func": "postpone_job",
            }
        elif name in list_(show_all=True, where="pillar", return_yaml=False):
            event_data = {
                "name": name,
                "time": current_time,
                "new_time": new_time,
                "time_fmt": time_fmt,
                "where": "pillar",
                "func": "postpone_job",
            }
        else:
            ret["comment"] = f"Job {name} does not exist."
            ret["result"] = False
            return ret

        try:
            with salt.utils.event.get_event("minion", opts=__opts__) as event_bus:
                res = __salt__["event.fire"](event_data, "manage_schedule")
                if res:
                    event_ret = event_bus.get_event(
                        tag="/salt/minion/minion_schedule_postpone_job_complete",
                        wait=30,
                    )
                    if event_ret and event_ret["complete"]:
                        schedule = event_ret["schedule"]
                        # check item exists in schedule and is enabled
                        if name in schedule and schedule[name]["enabled"]:
                            ret["result"] = True
                            ret["comment"] = "Postponed Job {} in schedule.".format(
                                name
                            )
                        else:
                            ret["result"] = False
                            ret["comment"] = (
                                f"Failed to postpone job {name} in schedule."
                            )
                        return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret["comment"] = "Event module not available. Schedule postpone job failed."
    return ret


def skip_job(name, current_time, **kwargs):
    """
    Skip a job in the minion's schedule at specified time.

    Time to skip should be specified as date string format,
    default value is %Y-%m-%dT%H:%M:%S.

    .. versionadded:: 2018.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.skip_job job time
    """
    time_fmt = kwargs.get("time_fmt") or "%Y-%m-%dT%H:%M:%S"

    ret = {"comment": [], "result": True}

    if not name:
        ret["comment"] = "Job name is required."
        ret["result"] = False

    if not current_time:
        ret["comment"] = "Job time is required."
        ret["result"] = False
    else:
        # Validate date string
        try:
            datetime.datetime.strptime(current_time, time_fmt)
        except (TypeError, ValueError):
            log.error("Date string could not be parsed: %s, %s", current_time, time_fmt)

            ret["comment"] = "Date string could not be parsed."
            ret["result"] = False
            return ret

    if "test" in __opts__ and __opts__["test"]:
        ret["comment"] = f"Job: {name} would be skipped in schedule."
    else:

        if name in list_(show_all=True, where="opts", return_yaml=False):
            event_data = {
                "name": name,
                "time": current_time,
                "time_fmt": time_fmt,
                "func": "skip_job",
            }
        elif name in list_(show_all=True, where="pillar", return_yaml=False):
            event_data = {
                "name": name,
                "time": current_time,
                "time_fmt": time_fmt,
                "where": "pillar",
                "func": "skip_job",
            }
        else:
            ret["comment"] = f"Job {name} does not exist."
            ret["result"] = False
            return ret

        try:
            with salt.utils.event.get_event("minion", opts=__opts__) as event_bus:
                res = __salt__["event.fire"](event_data, "manage_schedule")
                if res:
                    event_ret = event_bus.get_event(
                        tag="/salt/minion/minion_schedule_skip_job_complete",
                        wait=30,
                    )
                    if event_ret and event_ret["complete"]:
                        schedule = event_ret["schedule"]
                        # check item exists in schedule and is enabled
                        if name in schedule and schedule[name]["enabled"]:
                            ret["result"] = True
                            ret["comment"] = "Added Skip Job {} in schedule.".format(
                                name
                            )
                        else:
                            ret["result"] = False
                            ret["comment"] = f"Failed to skip job {name} in schedule."
                        return ret
        except KeyError:
            # Effectively a no-op, since we can't really return without an event system
            ret["comment"] = "Event module not available. Schedule skip job failed."
    return ret


def show_next_fire_time(name, **kwargs):
    """
    Show the next fire time for scheduled job

    .. versionadded:: 2018.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.show_next_fire_time job_name

    """

    ret = {"result": True}

    if not name:
        ret["comment"] = "Job name is required."
        ret["result"] = False

    try:
        event_data = {"name": name, "func": "get_next_fire_time"}
        with salt.utils.event.get_event("minion", opts=__opts__) as event_bus:
            res = __salt__["event.fire"](event_data, "manage_schedule")
            if res:
                event_ret = event_bus.get_event(
                    tag="/salt/minion/minion_schedule_next_fire_time_complete",
                    wait=30,
                )
    except KeyError:
        # Effectively a no-op, since we can't really return without an event system
        ret = {}
        ret["comment"] = (
            "Event module not available. Schedule show next fire time failed."
        )
        ret["result"] = True
        return ret

    if "next_fire_time" in event_ret:
        ret["next_fire_time"] = event_ret["next_fire_time"]
    else:
        ret["comment"] = "next fire time not available."
    return ret


def job_status(name, time_fmt="%Y-%m-%dT%H:%M:%S"):
    """
    Show the information for a particular job.

    CLI Example:

    .. code-block:: bash

        salt '*' schedule.job_status job_name

    """

    def convert_datetime_objects_in_dict_to_string(data_dict, time_fmt):
        return {
            key: (
                value.strftime(time_fmt)
                if isinstance(value, datetime.datetime)
                else value
            )
            for key, value in data_dict.items()
        }

    schedule = {}
    try:
        with salt.utils.event.get_event("minion", opts=__opts__) as event_bus:
            res = __salt__["event.fire"](
                {"func": "job_status", "name": name, "fire_event": True},
                "manage_schedule",
            )
            if res:
                event_ret = event_bus.get_event(
                    tag="/salt/minion/minion_schedule_job_status_complete", wait=30
                )
                data = event_ret.get("data", {})
                return convert_datetime_objects_in_dict_to_string(data, time_fmt)
    except KeyError:
        # Effectively a no-op, since we can't really return without an event system
        ret = {}
        ret["comment"] = "Event module not available. Schedule list failed."
        ret["result"] = True
        log.debug("Event module not available. Schedule list failed.")
        return ret
