# -*- coding: utf-8 -*-
"""
Control the Salt command interface
==================================

This state is intended for use from the Salt Master. It provides access to
sending commands down to minions as well as access to executing master-side
modules. These state functions wrap Salt's :ref:`Python API <python-api>`.

    .. versionadded: 2016.11.0

    Support for masterless minions was added to the ``salt.state`` function,
    so they can run orchestration sls files. This is particularly useful when
    the rendering of a state is dependent on the execution of another state.
    Orchestration will render and execute each orchestration block
    independently, while honoring requisites to ensure the states are applied
    in the correct order.

.. seealso:: More Orchestrate documentation

    * :ref:`Full Orchestrate Tutorial <orchestrate-runner>`
    * :py:func:`The Orchestrate runner <salt.runners.state.orchestrate>`
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import fnmatch
import logging
import sys
import threading
import time

import salt.exceptions
import salt.output

# Import salt libs
import salt.syspaths
import salt.utils.data
import salt.utils.event
from salt.ext import six

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "salt"


def __virtual__():
    """
    Named salt
    """
    return __virtualname__


def _fire_args(tag_data):
    try:
        salt.utils.event.fire_args(__opts__, __orchestration_jid__, tag_data, "run")
    except NameError:
        log.debug("Unable to fire args event due to missing __orchestration_jid__")


def _parallel_map(func, inputs):
    """
    Applies a function to each element of a list, returning the resulting list.

    A separate thread is created for each element in the input list and the
    passed function is called for each of the elements. When all threads have
    finished execution a list with the results corresponding to the inputs is
    returned.

    If one of the threads fails (because the function throws an exception),
    that exception is reraised. If more than one thread fails, the exception
    from the first thread (according to the index of the input element) is
    reraised.

    func:
        function that is applied on each input element.
    inputs:
        list of elements that shall be processed. The length of this list also
        defines the number of threads created.
    """
    outputs = len(inputs) * [None]
    errors = len(inputs) * [None]

    def create_thread(index):
        def run_thread():
            try:
                outputs[index] = func(inputs[index])
            except:  # pylint: disable=bare-except
                errors[index] = sys.exc_info()

        thread = threading.Thread(target=run_thread)
        thread.start()
        return thread

    threads = list(six.moves.map(create_thread, six.moves.range(len(inputs))))
    for thread in threads:
        thread.join()
    for error in errors:
        if error is not None:
            exc_type, exc_value, exc_traceback = error
            six.reraise(exc_type, exc_value, exc_traceback)
    return outputs


def state(
    name,
    tgt,
    ssh=False,
    tgt_type="glob",
    ret="",
    ret_config=None,
    ret_kwargs=None,
    highstate=None,
    sls=None,
    top=None,
    saltenv=None,
    test=None,
    pillar=None,
    pillarenv=None,
    expect_minions=True,
    fail_minions=None,
    allow_fail=0,
    concurrent=False,
    timeout=None,
    batch=None,
    queue=False,
    subset=None,
    orchestration_jid=None,
    failhard=None,
    **kwargs
):
    """
    Invoke a state run on a given target

    name
        An arbitrary name used to track the state execution

    tgt
        The target specification for the state run.

        .. versionadded: 2016.11.0

        Masterless support: When running on a masterless minion, the ``tgt``
        is ignored and will always be the local minion.

    tgt_type
        The target type to resolve, defaults to ``glob``

    ret
        Optionally set a single or a list of returners to use

    ret_config
        Use an alternative returner configuration

    ret_kwargs
        Override individual returner configuration items

    highstate
        Defaults to None, if set to True the target systems will ignore any
        sls references specified in the sls option and call state.highstate
        on the targeted minions

    top
        Should be the name of a top file. If set state.top is called with this
        top file instead of state.sls.

    sls
        A group of sls files to execute. This can be defined as a single string
        containing a single sls file, or a list of sls files

    test
        Pass ``test=true`` or ``test=false`` through to the state function. This
        can be used to override a test mode set in the minion's config file. If
        left as the default of None and the 'test' mode is supplied on the
        command line, that value is passed instead.

    pillar
        Pass the ``pillar`` kwarg through to the state function

    pillarenv
        The pillar environment to grab pillars from

        .. versionadded:: 2017.7.0

    saltenv
        The default salt environment to pull sls files from

    ssh
        Set to `True` to use the ssh client instead of the standard salt client

    roster
        In the event of using salt-ssh, a roster system can be set

    expect_minions
        An optional boolean for failing if some minions do not respond

    fail_minions
        An optional list of targeted minions where failure is an option

    allow_fail
        Pass in the number of minions to allow for failure before setting
        the result of the execution to False

    concurrent
        Allow multiple state runs to occur at once.

        WARNING: This flag is potentially dangerous. It is designed
        for use when multiple state runs can safely be run at the same
        Do not use this flag for performance optimization.

    queue
        Pass ``queue=true`` through to the state function

    batch
        Execute the command :ref:`in batches <targeting-batch>`. E.g.: ``10%``.

        .. versionadded:: 2016.3.0

    subset
        Number of minions from the targeted set to randomly use

        .. versionadded:: 2017.7.0

    failhard
        pass failhard down to the executing state

        .. versionadded:: 2019.2.2

    Examples:

    Run a list of sls files via :py:func:`state.sls <salt.state.sls>` on target
    minions:

    .. code-block:: yaml

        webservers:
          salt.state:
            - tgt: 'web*'
            - sls:
              - apache
              - django
              - core
            - saltenv: prod

    Run a full :py:func:`state.highstate <salt.state.highstate>` on target
    mininons.

    .. code-block:: yaml

        databases:
          salt.state:
            - tgt: role:database
            - tgt_type: grain
            - highstate: True
    """
    cmd_kw = {"arg": [], "kwarg": {}, "ret": ret, "timeout": timeout}

    if ret_config:
        cmd_kw["ret_config"] = ret_config

    if ret_kwargs:
        cmd_kw["ret_kwargs"] = ret_kwargs

    state_ret = {"name": name, "changes": {}, "comment": "", "result": True}

    try:
        allow_fail = int(allow_fail)
    except ValueError:
        state_ret["result"] = False
        state_ret["comment"] = "Passed invalid value for 'allow_fail', must be an int"
        return state_ret

    cmd_kw["tgt_type"] = tgt_type
    cmd_kw["ssh"] = ssh
    if "roster" in kwargs:
        cmd_kw["roster"] = kwargs["roster"]
    cmd_kw["expect_minions"] = expect_minions
    if highstate:
        fun = "state.highstate"
    elif top:
        fun = "state.top"
        cmd_kw["arg"].append(top)
    elif sls:
        fun = "state.sls"
        if isinstance(sls, list):
            sls = ",".join(sls)
        cmd_kw["arg"].append(sls)
    else:
        state_ret["comment"] = "No highstate or sls specified, no execution made"
        state_ret["result"] = False
        return state_ret

    if test is not None or __opts__.get("test"):
        cmd_kw["kwarg"]["test"] = test if test is not None else __opts__.get("test")

    if pillar:
        cmd_kw["kwarg"]["pillar"] = pillar

    if pillarenv is not None:
        cmd_kw["kwarg"]["pillarenv"] = pillarenv

    if saltenv is not None:
        cmd_kw["kwarg"]["saltenv"] = saltenv

    cmd_kw["kwarg"]["queue"] = queue

    if isinstance(concurrent, bool):
        cmd_kw["kwarg"]["concurrent"] = concurrent
    else:
        state_ret["comment"] = "Must pass in boolean for value of 'concurrent'"
        state_ret["result"] = False
        return state_ret

    if batch is not None:
        cmd_kw["batch"] = six.text_type(batch)

    if subset is not None:
        cmd_kw["subset"] = subset

    if failhard is True or __opts__.get("failhard"):
        cmd_kw["failhard"] = True

    masterless = __opts__["__role"] == "minion" and __opts__["file_client"] == "local"
    if not masterless:
        _fire_args({"type": "state", "tgt": tgt, "name": name, "args": cmd_kw})
        cmd_ret = __salt__["saltutil.cmd"](tgt, fun, **cmd_kw)
    else:
        if top:
            cmd_kw["topfn"] = "".join(cmd_kw.pop("arg"))
        elif sls:
            cmd_kw["mods"] = "".join(cmd_kw.pop("arg"))
        cmd_kw.update(cmd_kw.pop("kwarg"))
        tmp_ret = __salt__[fun](**cmd_kw)
        cmd_ret = {
            __opts__["id"]: {
                "ret": tmp_ret,
                "out": tmp_ret.get("out", "highstate")
                if isinstance(tmp_ret, dict)
                else "highstate",
            }
        }

    try:
        state_ret["__jid__"] = cmd_ret[next(iter(cmd_ret))]["jid"]
    except (StopIteration, KeyError):
        pass

    changes = {}
    fail = set()
    no_change = set()

    if fail_minions is None:
        fail_minions = ()
    elif isinstance(fail_minions, six.string_types):
        fail_minions = [minion.strip() for minion in fail_minions.split(",")]
    elif not isinstance(fail_minions, list):
        state_ret.setdefault("warnings", []).append(
            "'fail_minions' needs to be a list or a comma separated " "string. Ignored."
        )
        fail_minions = ()

    if not cmd_ret and expect_minions:
        state_ret["result"] = False
        state_ret["comment"] = "No minions returned"
        return state_ret

    for minion, mdata in six.iteritems(cmd_ret):
        if mdata.get("out", "") != "highstate":
            log.warning("Output from salt state not highstate")

        m_ret = False

        if "return" in mdata and "ret" not in mdata:
            mdata["ret"] = mdata.pop("return")

        m_state = True
        if mdata.get("failed", False):
            m_state = False
        else:
            try:
                m_ret = mdata["ret"]
            except KeyError:
                m_state = False
            if m_state:
                m_state = __utils__["state.check_result"](m_ret, recurse=True)

        if not m_state:
            if minion not in fail_minions:
                fail.add(minion)
            changes[minion] = m_ret
            continue
        try:
            for state_item in six.itervalues(m_ret):
                if isinstance(state_item, dict):
                    if "changes" in state_item and state_item["changes"]:
                        changes[minion] = m_ret
                        break
            else:
                no_change.add(minion)
        except AttributeError:
            log.error("m_ret did not have changes %s %s", type(m_ret), m_ret)
            no_change.add(minion)

    if changes:
        state_ret["changes"] = {"out": "highstate", "ret": changes}
    if len(fail) > allow_fail:
        state_ret["result"] = False
        state_ret["comment"] = "Run failed on minions: {0}".format(", ".join(fail))
    else:
        state_ret["comment"] = "States ran successfully."
        if changes:
            state_ret["comment"] += " Updating {0}.".format(", ".join(changes))
        if no_change:
            state_ret["comment"] += " No changes made to {0}.".format(
                ", ".join(no_change)
            )
    if test or __opts__.get("test"):
        if state_ret["changes"] and state_ret["result"] is True:
            # Test mode with changes is the only case where result should ever be none
            state_ret["result"] = None
    return state_ret


def function(
    name,
    tgt,
    ssh=False,
    tgt_type="glob",
    ret="",
    ret_config=None,
    ret_kwargs=None,
    expect_minions=False,
    fail_minions=None,
    fail_function=None,
    arg=None,
    kwarg=None,
    timeout=None,
    batch=None,
    subset=None,
    failhard=None,
    **kwargs
):  # pylint: disable=unused-argument
    """
    Execute a single module function on a remote minion via salt or salt-ssh

    name
        The name of the function to run, aka cmd.run or pkg.install

    tgt
        The target specification, aka '*' for all minions

    tgt_type
        The target type, defaults to ``glob``

    arg
        The list of arguments to pass into the function

    kwarg
        The dict (not a list) of keyword arguments to pass into the function

    ret
        Optionally set a single or a list of returners to use

    ret_config
        Use an alternative returner configuration

    ret_kwargs
        Override individual returner configuration items

    expect_minions
        An optional boolean for failing if some minions do not respond

    fail_minions
        An optional list of targeted minions where failure is an option

    fail_function
        An optional string that points to a salt module that returns True or False
        based on the returned data dict for individual minions

    ssh
        Set to `True` to use the ssh client instead of the standard salt client

    batch
        Execute the command :ref:`in batches <targeting-batch>`. E.g.: ``10%``.

    subset
        Number of minions from the targeted set to randomly use

        .. versionadded:: 2017.7.0

    failhard
        pass failhard down to the executing state

        .. versionadded:: 2019.2.2

    """
    func_ret = {"name": name, "changes": {}, "comment": "", "result": True}
    if kwarg is None:
        kwarg = {}
    if isinstance(arg, six.string_types):
        func_ret["warnings"] = ["Please specify 'arg' as a list of arguments."]
        arg = arg.split()

    cmd_kw = {"arg": arg or [], "kwarg": kwarg, "ret": ret, "timeout": timeout}

    if batch is not None:
        cmd_kw["batch"] = six.text_type(batch)
    if subset is not None:
        cmd_kw["subset"] = subset

    cmd_kw["tgt_type"] = tgt_type
    cmd_kw["ssh"] = ssh
    cmd_kw["expect_minions"] = expect_minions
    cmd_kw["_cmd_meta"] = True

    if failhard is True or __opts__.get("failhard"):
        cmd_kw["failhard"] = True

    if ret_config:
        cmd_kw["ret_config"] = ret_config

    if ret_kwargs:
        cmd_kw["ret_kwargs"] = ret_kwargs

    fun = name
    if __opts__["test"] is True:
        func_ret["comment"] = "Function {0} would be executed on target {1}".format(
            fun, tgt
        )
        func_ret["result"] = None
        return func_ret
    try:
        _fire_args({"type": "function", "tgt": tgt, "name": name, "args": cmd_kw})
        cmd_ret = __salt__["saltutil.cmd"](tgt, fun, **cmd_kw)
    except Exception as exc:  # pylint: disable=broad-except
        func_ret["result"] = False
        func_ret["comment"] = six.text_type(exc)
        return func_ret

    try:
        func_ret["__jid__"] = cmd_ret[next(iter(cmd_ret))]["jid"]
    except (StopIteration, KeyError):
        pass

    changes = {}
    fail = set()

    if fail_minions is None:
        fail_minions = ()
    elif isinstance(fail_minions, six.string_types):
        fail_minions = [minion.strip() for minion in fail_minions.split(",")]
    elif not isinstance(fail_minions, list):
        func_ret.setdefault("warnings", []).append(
            "'fail_minions' needs to be a list or a comma separated " "string. Ignored."
        )
        fail_minions = ()
    for minion, mdata in six.iteritems(cmd_ret):
        m_ret = False
        if mdata.get("retcode"):
            func_ret["result"] = False
            fail.add(minion)
        if mdata.get("failed", False):
            m_func = False
        else:
            if "return" in mdata and "ret" not in mdata:
                mdata["ret"] = mdata.pop("return")
            m_ret = mdata["ret"]
            m_func = (not fail_function and True) or __salt__[fail_function](m_ret)

            if m_ret is False:
                m_func = False

        if not m_func:
            if minion not in fail_minions:
                fail.add(minion)
        changes[minion] = m_ret
    if not cmd_ret:
        func_ret["result"] = False
        func_ret["command"] = "No minions responded"
    else:
        if changes:
            func_ret["changes"] = {"out": "highstate", "ret": changes}
        if fail:
            func_ret["result"] = False
            func_ret["comment"] = "Running function {0} failed on minions: {1}".format(
                name, ", ".join(fail)
            )
        else:
            func_ret["comment"] = "Function ran successfully."
        if changes:
            func_ret["comment"] += " Function {0} ran on {1}.".format(
                name, ", ".join(changes)
            )
    return func_ret


def wait_for_event(name, id_list, event_id="id", timeout=300, node="master"):
    """
    Watch Salt's event bus and block until a condition is met

    .. versionadded:: 2014.7.0

    name
        An event tag to watch for; supports Reactor-style globbing.
    id_list
        A list of event identifiers to watch for -- usually the minion ID. Each
        time an event tag is matched the event data is inspected for
        ``event_id``, if found it is removed from ``id_list``. When ``id_list``
        is empty this function returns success.
    event_id : id
        The name of a key in the event data. Default is ``id`` for the minion
        ID, another common value is ``name`` for use with orchestrating
        salt-cloud events.
    timeout : 300
        The maximum time in seconds to wait before failing.

    The following example blocks until all the listed minions complete a
    restart and reconnect to the Salt master:

    .. code-block:: yaml

        reboot_all_minions:
          salt.function:
            - name: system.reboot
            - tgt: '*'

        wait_for_reboots:
          salt.wait_for_event:
            - name: salt/minion/*/start
            - id_list:
              - jerry
              - stuart
              - dave
              - phil
              - kevin
              - mike
            - require:
              - salt: reboot_all_minions
    """
    ret = {"name": name, "changes": {}, "comment": "", "result": False}

    if __opts__.get("test"):
        ret["comment"] = "Orchestration would wait for event '{0}'".format(name)
        ret["result"] = None
        return ret

    sevent = salt.utils.event.get_event(
        node, __opts__["sock_dir"], __opts__["transport"], opts=__opts__, listen=True
    )

    del_counter = 0
    starttime = time.time()
    timelimit = starttime + timeout
    while True:
        event = sevent.get_event(full=True)
        is_timedout = time.time() > timelimit

        if event is None and not is_timedout:
            log.trace("wait_for_event: No event data; waiting.")
            continue
        elif event is None and is_timedout:
            ret["comment"] = "Timeout value reached."
            return ret

        if fnmatch.fnmatch(event["tag"], name):
            val = event["data"].get(event_id)
            if val is None and "data" in event["data"]:
                val = event["data"]["data"].get(event_id)

            if val is not None:
                try:
                    val_idx = id_list.index(val)
                except ValueError:
                    log.trace(
                        "wait_for_event: Event identifier '%s' not in "
                        "id_list; skipping.",
                        event_id,
                    )
                else:
                    del id_list[val_idx]
                    del_counter += 1
                    minions_seen = ret["changes"].setdefault("minions_seen", [])
                    minions_seen.append(val)

                    log.debug(
                        "wait_for_event: Event identifier '%s' removed "
                        "from id_list; %s items remaining.",
                        val,
                        len(id_list),
                    )
            else:
                log.trace(
                    "wait_for_event: Event identifier '%s' not in event "
                    "'%s'; skipping.",
                    event_id,
                    event["tag"],
                )
        else:
            log.debug("wait_for_event: Skipping unmatched event '%s'", event["tag"])

        if len(id_list) == 0:
            ret["result"] = True
            ret["comment"] = "All events seen in {0} seconds.".format(
                time.time() - starttime
            )
            return ret

        if is_timedout:
            ret["comment"] = "Timeout value reached."
            return ret


def runner(name, **kwargs):
    """
    Execute a runner module on the master

    .. versionadded:: 2014.7.0

    name
        The name of the function to run
    kwargs
        Any keyword arguments to pass to the runner function

    .. code-block:: yaml

         run-manage-up:
          salt.runner:
            - name: manage.up
    """
    try:
        jid = __orchestration_jid__
    except NameError:
        log.debug("Unable to fire args event due to missing __orchestration_jid__")
        jid = None

    if __opts__.get("test", False):
        ret = {
            "name": name,
            "result": None,
            "changes": {},
            "comment": "Runner function '{0}' would be executed.".format(name),
        }
        return ret

    out = __salt__["saltutil.runner"](
        name, __orchestration_jid__=jid, __env__=__env__, full_return=True, **kwargs
    )

    runner_return = out.get("return")
    if isinstance(runner_return, dict) and "Error" in runner_return:
        out["success"] = False

    success = out.get("success", True)
    ret = {"name": name, "changes": {"return": runner_return}, "result": success}
    ret["comment"] = "Runner function '{0}' {1}.".format(
        name, "executed" if success else "failed",
    )

    ret["__orchestration__"] = True
    if "jid" in out:
        ret["__jid__"] = out["jid"]

    return ret


def parallel_runners(name, runners, **kwargs):  # pylint: disable=unused-argument
    """
    Executes multiple runner modules on the master in parallel.

    .. versionadded:: 2017.x.0 (Nitrogen)

    A separate thread is spawned for each runner. This state is intended to be
    used with the orchestrate runner in place of the ``saltmod.runner`` state
    when different tasks should be run in parallel. In general, Salt states are
    not safe when used concurrently, so ensure that they are used in a safe way
    (e.g. by only targeting separate minions in parallel tasks).

    name:
        name identifying this state. The name is provided as part of the
        output, but not used for anything else.

    runners:
        list of runners that should be run in parallel. Each element of the
        list has to be a dictionary. This dictionary's name entry stores the
        name of the runner function that shall be invoked. The optional kwarg
        entry stores a dictionary of named arguments that are passed to the
        runner function.

    .. code-block:: yaml

        parallel-state:
           salt.parallel_runners:
             - runners:
                 my_runner_1:
                   - name: state.orchestrate
                   - kwarg:
                       mods: orchestrate_state_1
                 my_runner_2:
                   - name: state.orchestrate
                   - kwarg:
                       mods: orchestrate_state_2
    """
    # For the sake of consistency, we treat a single string in the same way as
    # a key without a value. This allows something like
    #     salt.parallel_runners:
    #       - runners:
    #           state.orchestrate
    # Obviously, this will only work if the specified runner does not need any
    # arguments.
    if isinstance(runners, six.string_types):
        runners = {runners: [{name: runners}]}
    # If the runners argument is not a string, it must be a dict. Everything
    # else is considered an error.
    if not isinstance(runners, dict):
        return {
            "name": name,
            "result": False,
            "changes": {},
            "comment": "The runners parameter must be a string or dict.",
        }
    # The configuration for each runner is given as a list of key-value pairs.
    # This is not very useful for what we want to do, but it is the typical
    # style used in Salt. For further processing, we convert each of these
    # lists to a dict. This also makes it easier to check whether a name has
    # been specified explicitly.
    for runner_id, runner_config in six.iteritems(runners):
        if runner_config is None:
            runner_config = {}
        else:
            runner_config = salt.utils.data.repack_dictlist(runner_config)
        if "name" not in runner_config:
            runner_config["name"] = runner_id
        runners[runner_id] = runner_config

    try:
        jid = __orchestration_jid__
    except NameError:
        log.debug("Unable to fire args event due to missing __orchestration_jid__")
        jid = None

    def call_runner(runner_config):
        return __salt__["saltutil.runner"](
            runner_config["name"],
            __orchestration_jid__=jid,
            __env__=__env__,
            full_return=True,
            **(runner_config.get("kwarg", {}))
        )

    try:
        outputs = _parallel_map(call_runner, list(six.itervalues(runners)))
    except salt.exceptions.SaltException as exc:
        return {
            "name": name,
            "result": False,
            "success": False,
            "changes": {},
            "comment": "One of the runners raised an exception: {0}".format(exc),
        }
    # We bundle the results of the runners with the IDs of the runners so that
    # we can easily identify which output belongs to which runner. At the same
    # time we exctract the actual return value of the runner (saltutil.runner
    # adds some extra information that is not interesting to us).
    outputs = {
        runner_id: out["return"]
        for runner_id, out in six.moves.zip(six.iterkeys(runners), outputs)
    }

    # If each of the runners returned its output in the format compatible with
    # the 'highstate' outputter, we can leverage this fact when merging the
    # outputs.
    highstate_output = all(
        [
            out.get("outputter", "") == "highstate" and "data" in out
            for out in six.itervalues(outputs)
        ]
    )

    # The following helper function is used to extract changes from highstate
    # output.

    def extract_changes(obj):
        if not isinstance(obj, dict):
            return {}
        elif "changes" in obj:
            if (
                isinstance(obj["changes"], dict)
                and obj["changes"].get("out", "") == "highstate"
                and "ret" in obj["changes"]
            ):
                return obj["changes"]["ret"]
            else:
                return obj["changes"]
        else:
            found_changes = {}
            for key, value in six.iteritems(obj):
                change = extract_changes(value)
                if change:
                    found_changes[key] = change
            return found_changes

    if highstate_output:
        failed_runners = [
            runner_id
            for runner_id, out in six.iteritems(outputs)
            if out["data"].get("retcode", 0) != 0
        ]
        all_successful = not failed_runners
        if all_successful:
            comment = "All runner functions executed successfully."
        else:
            runner_comments = [
                "Runner {0} failed with return value:\n{1}".format(
                    runner_id,
                    salt.output.out_format(
                        outputs[runner_id], "nested", __opts__, nested_indent=2
                    ),
                )
                for runner_id in failed_runners
            ]
            comment = "\n".join(runner_comments)
        changes = {}
        for runner_id, out in six.iteritems(outputs):
            runner_changes = extract_changes(out["data"])
            if runner_changes:
                changes[runner_id] = runner_changes
    else:
        failed_runners = [
            runner_id
            for runner_id, out in six.iteritems(outputs)
            if out.get("exit_code", 0) != 0
        ]
        all_successful = not failed_runners
        if all_successful:
            comment = "All runner functions executed successfully."
        else:
            if len(failed_runners) == 1:
                comment = "Runner {0} failed.".format(failed_runners[0])
            else:
                comment = "Runners {0} failed.".format(", ".join(failed_runners))
        changes = {"ret": {runner_id: out for runner_id, out in six.iteritems(outputs)}}
    ret = {
        "name": name,
        "result": all_successful,
        "changes": changes,
        "comment": comment,
    }

    # The 'runner' function includes out['jid'] as '__jid__' in the returned
    # dict, but we cannot do this here because we have more than one JID if
    # we have more than one runner.

    return ret


def wheel(name, **kwargs):
    """
    Execute a wheel module on the master

    .. versionadded:: 2014.7.0

    name
        The name of the function to run
    kwargs
        Any keyword arguments to pass to the wheel function

    .. code-block:: yaml

        accept_minion_key:
          salt.wheel:
            - name: key.accept
            - match: frank
    """
    ret = {"name": name, "result": False, "changes": {}, "comment": ""}
    try:
        jid = __orchestration_jid__
    except NameError:
        log.debug("Unable to fire args event due to missing __orchestration_jid__")
        jid = None

    if __opts__.get("test", False):
        ret["result"] = (None,)
        ret["changes"] = {}
        ret["comment"] = "Wheel function '{0}' would be executed.".format(name)
        return ret

    out = __salt__["saltutil.wheel"](
        name, __orchestration_jid__=jid, __env__=__env__, **kwargs
    )

    wheel_return = out.get("return")
    if isinstance(wheel_return, dict) and "Error" in wheel_return:
        out["success"] = False

    success = out.get("success", True)
    ret = {"name": name, "changes": {"return": wheel_return}, "result": success}
    ret["comment"] = "Wheel function '{0}' {1}.".format(
        name, "executed" if success else "failed",
    )

    ret["__orchestration__"] = True
    if "jid" in out:
        ret["__jid__"] = out["jid"]

    return ret
