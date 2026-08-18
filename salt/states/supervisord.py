"""
Interaction with the Supervisor daemon
======================================

.. code-block:: yaml

    wsgi_server:
      supervisord.running:
        - require:
          - pkg: supervisor
        - watch:
          - file: /etc/nginx/sites-enabled/wsgi_server.conf
"""

import logging

log = logging.getLogger(__name__)


def _check_error(result, success_message):
    ret = {}

    if "ERROR" in result:
        if any(
            substring in result
            for substring in [
                "already started",
                "not running",
                "process group already active",
            ]
        ):
            ret["comment"] = success_message
        else:
            ret["comment"] = result
            ret["result"] = False
    else:
        ret["comment"] = success_message

    return ret


def _is_stopped_state(state):
    if state in ("STOPPED", "STOPPING", "EXITED", "FATAL", "BACKOFF"):
        return True
    if state in ("STARTING", "RUNNING"):
        return False
    return False


def running(
    name, restart=False, update=False, user=None, conf_file=None, bin_env=None, **kwargs
):
    """
    Ensure the named service is running.

    name
        Service name as defined in the supervisor configuration file

    restart
        Whether to force a restart

    update
        Whether to update the supervisor configuration.

    user
        Name of the user to run the supervisorctl command

        .. versionadded:: 0.17.0

    conf_file
        path to supervisorctl config file

    bin_env
        path to supervisorctl bin or path to virtualenv with supervisor
        installed

    """
    if name.endswith(":*"):
        name = name[:-1]

    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    if "supervisord.status" not in __salt__:
        ret["result"] = False
        ret["comment"] = (
            "Supervisord module not activated. Do you need to install supervisord?"
        )
        return ret

    all_processes = __salt__["supervisord.status"](
        user=user, conf_file=conf_file, bin_env=bin_env
    )

    # parse process groups
    process_groups = set()
    for proc in all_processes:
        if ":" in proc:
            process_groups.add(proc[: proc.index(":") + 1])
    process_groups = sorted(process_groups)

    matches = {}
    if name in all_processes:
        matches[name] = all_processes[name]["state"].lower() == "running"
    elif name in process_groups:
        for process in (x for x in all_processes if x.startswith(name)):
            matches[process] = all_processes[process]["state"].lower() == "running"
    to_add = not bool(matches)

    if __opts__["test"]:
        if not to_add:
            # Process/group already present, check if any need to be started
            to_start = [x for x, y in matches.items() if y is False]
            if to_start:
                ret["result"] = None
                if name.endswith(":"):
                    # Process group
                    if len(to_start) == len(matches):
                        ret["comment"] = (
                            f"All services in group '{name}' will be started"
                        )
                    else:
                        ret["comment"] = (
                            "The following services will be started: {}".format(
                                " ".join(to_start)
                            )
                        )
                else:
                    # Single program
                    ret["comment"] = f"Service {name} will be started"
            else:
                if name.endswith(":"):
                    # Process group
                    ret["comment"] = (
                        f"All services in group '{name}' are already running"
                    )
                else:
                    ret["comment"] = f"Service {name} is already running"
        else:
            ret["result"] = None
            # Process/group needs to be added
            if name.endswith(":"):
                _type = f"Group '{name}'"
            else:
                _type = f"Service {name}"
            ret["comment"] = f"{_type} will be added and started"
        return ret

    changes = []
    just_updated = False

    if update:
        # If the state explicitly asks to update, we don't care if the process
        # is being added or not, since it'll take care of this for us,
        # so give this condition priority in order
        #
        # That is, unless `to_add` somehow manages to contain processes
        # we don't want running, in which case adding them may be a mistake
        comment = "Updating supervisor"
        result = __salt__["supervisord.update"](
            user=user, conf_file=conf_file, bin_env=bin_env
        )
        ret.update(_check_error(result, comment))
        log.debug(comment)

        if f"{name}: updated" in result:
            just_updated = True
    elif to_add:
        # Not sure if this condition is precise enough.
        comment = f"Adding service: {name}"
        __salt__["supervisord.reread"](user=user, conf_file=conf_file, bin_env=bin_env)
        # Causes supervisorctl to throw `ERROR: process group already active`
        # if process group exists. At this moment, I'm not sure how to handle
        # this outside of grepping out the expected string in `_check_error`.
        result = __salt__["supervisord.add"](
            name, user=user, conf_file=conf_file, bin_env=bin_env
        )

        ret.update(_check_error(result, comment))
        changes.append(comment)
        log.debug(comment)

    is_stopped = None

    process_type = None
    if name in process_groups:
        process_type = "group"

        # check if any processes in this group are stopped
        is_stopped = False
        for proc in all_processes:
            if proc.startswith(name) and _is_stopped_state(
                all_processes[proc]["state"]
            ):
                is_stopped = True
                break

    elif name in all_processes:
        process_type = "service"

        if _is_stopped_state(all_processes[name]["state"]):
            is_stopped = True
        else:
            is_stopped = False

    if is_stopped is False:
        if restart and not just_updated:
            comment = "Restarting{}: {}".format(
                process_type is not None and f" {process_type}" or "", name
            )
            log.debug(comment)
            result = __salt__["supervisord.restart"](
                name, user=user, conf_file=conf_file, bin_env=bin_env
            )
            ret.update(_check_error(result, comment))
            changes.append(comment)
        elif just_updated:
            comment = "Not starting updated{}: {}".format(
                process_type is not None and f" {process_type}" or "", name
            )
            result = comment
            ret.update({"comment": comment})
        else:
            comment = "Not starting already running{}: {}".format(
                process_type is not None and f" {process_type}" or "", name
            )
            result = comment
            ret.update({"comment": comment})

    elif not just_updated:
        comment = "Starting{}: {}".format(
            process_type is not None and f" {process_type}" or "", name
        )
        changes.append(comment)
        log.debug(comment)
        result = __salt__["supervisord.start"](
            name, user=user, conf_file=conf_file, bin_env=bin_env
        )

        ret.update(_check_error(result, comment))
        log.debug(str(result))

    if ret["result"] and changes:
        ret["changes"][name] = " ".join(changes)
    return ret


def dead(name, user=None, conf_file=None, bin_env=None, **kwargs):
    """
    Ensure the named service is dead (not running).

    name
        Service name as defined in the supervisor configuration file

    user
        Name of the user to run the supervisorctl command

        .. versionadded:: 0.17.0

    conf_file
        path to supervisorctl config file

    bin_env
        path to supervisorctl bin or path to virtualenv with supervisor
        installed

    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    if __opts__["test"]:
        ret["result"] = None
        ret["comment"] = f"Service {name} is set to be stopped"
    else:
        comment = f"Stopping service: {name}"
        log.debug(comment)

        all_processes = __salt__["supervisord.status"](
            user=user, conf_file=conf_file, bin_env=bin_env
        )

        # parse process groups
        process_groups = []
        for proc in all_processes:
            if ":" in proc:
                process_groups.append(proc[: proc.index(":") + 1])
        process_groups = list(set(process_groups))

        is_stopped = None

        if name in process_groups:
            # check if any processes in this group are stopped
            is_stopped = False
            for proc in all_processes:
                if proc.startswith(name) and _is_stopped_state(
                    all_processes[proc]["state"]
                ):
                    is_stopped = True
                    break

        elif name in all_processes:
            if _is_stopped_state(all_processes[name]["state"]):
                is_stopped = True
            else:
                is_stopped = False
        else:
            # process name doesn't exist
            ret["comment"] = f"Service {name} doesn't exist"
            return ret

        if is_stopped is True:
            ret["comment"] = f"Service {name} is not running"
        else:
            result = {
                name: __salt__["supervisord.stop"](
                    name, user=user, conf_file=conf_file, bin_env=bin_env
                )
            }
            ret.update(_check_error(result, comment))
            ret["changes"][name] = comment
            log.debug(str(result))
    return ret


def mod_watch(
    name, restart=True, update=False, user=None, conf_file=None, bin_env=None, **kwargs
):
    """
    The supervisord watcher, called to invoke the watch command.
    Always restart on watch

    .. note::
        This state exists to support special handling of the ``watch``
        :ref:`requisite <requisites>`. It should not be called directly.

        Parameters for this function should be set by the state being triggered.
    """
    return running(
        name,
        restart=restart,
        update=update,
        user=user,
        conf_file=conf_file,
        bin_env=bin_env,
    )
