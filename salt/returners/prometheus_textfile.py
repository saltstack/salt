"""
Take data from salt and "return" it into a file formatted for Prometheus using
the `Text Exposition Format <https://prometheus.io/docs/instrumenting/exposition_formats/#text-format-example>`_
which rolls up state success and failure data.

.. versionadded:: 3005

The intended use case for this module is to have distributed success/failure
reporting from minions for unattended state or highstate runs.

Add the following to the minion or master configuration file to configure the
output location which Prometheus will monitor via Node Exporter.

.. code-block:: yaml

    prometheus_textfile.filename: <path_to_output_file>

Default is ``/var/cache/salt/minion/prometheus_textfile/salt.prom`` using the
``cachedir`` minion configuration.

The ``salt_procs`` metric will look for ``salt-minion`` processes by name. If
you have a custom installation of Salt, you might want to change the ``psutil``
process name to be matched or switch to matching the "exe" attribute of the
``Process.info`` dictionary.

.. code-block:: yaml

    prometheus_textfile.proc_name: custom-minion

.. code-block:: yaml

    prometheus_textfile.match_exe: True
    prometheus_textfile.exe: /opt/salt/bin/python3

The default operation of sending state metrics to a single file works well for
the use case of running distributed highstate or a single state run on minions.
However, there may be a use case for tracking multiple scheduled states in
separate files. To enable this behavior, set the following option in the
configuration file:

.. code-block:: yaml

    prometheus_textfile.add_state_name: True

This option will add the state name which was run as a filename suffix and also
inside the file as a metric parameter. Highstate runs will receive ``highstate``
as the state name, while running specific states will pass the first argument to
``state.apply`` or ``state.sls`` as the state name.

.. code-block:: bash

    # Filename is "salt-highstate.prom" and metrics get '{state="highstate"}'
    salt-call state.highstate

    # Filename is "salt-highstate.prom" and metrics get '{state="highstate"}'
    salt-call state.apply

    # Filename is "salt-test.prom" and metrics get '{state="test"}'
    salt-call state.apply test

    # Filename is "salt-test.prom" and metrics get '{state="test"}'
    salt-call state.sls test

Additionally, the inferred state name can be overridden on the command line by
passing the ``prom_textfile_state`` keyword argument to the state function.

.. code-block:: bash

    # Filename is "salt-hello.prom" and metrics get '{state="hello"}'
    salt-call state.highstate prom_textfile_state=hello

    # Filename is "salt-hello.prom" and metrics get '{state="hello"}'
    salt-call state.apply test prom_textfile_state=hello

Output file user, group, and mode can optionally be set through configuration
options:

.. code-block:: yaml

    prometheus_textfile.uid: 0
    prometheus_textfile.gid: 0
    prometheus_textfile.mode: "0644"

"""

import logging
import os
import time

import salt.exceptions
import salt.returners
import salt.utils.files

log = logging.getLogger(__name__)

HAS_PSUTIL = False
try:
    import psutil

    HAS_PSUTIL = True
except (ImportError, ModuleNotFoundError):
    log.warning("The psutil library is required for the salt_procs metric.")

# Define the module's virtual name
__virtualname__ = "prometheus_textfile"


def __virtual__():
    return __virtualname__


def _get_options(ret):
    """
    Returns options used for the prometheus_textfile returner.
    """
    defaults = {
        "exe": None,
        "filename": os.path.join(
            __opts__["cachedir"], "prometheus_textfile", "salt.prom"
        ),
        "uid": -1,  # fpopen default
        "gid": -1,  # fpopen default
        "mode": None,
        "match_exe": False,
        "proc_name": "salt-minion",
        "add_state_name": False,
    }
    attrs = {
        "exe": "exe",
        "filename": "filename",
        "uid": "uid",
        "gid": "gid",
        "mode": "mode",
        "match_exe": "match_exe",
        "proc_name": "proc_name",
        "add_state_name": "add_state_name",
    }
    _options = salt.returners.get_returner_options(
        __virtualname__,
        ret,
        attrs,
        __salt__=__salt__,
        __opts__=__opts__,
        defaults=defaults,
    )

    return _options


def _count_minion_procs(proc_name="salt-minion", match_exe=False, exe=None):
    """
    Return a list of processes with name matching "salt-minion"
    """
    ls = []
    if HAS_PSUTIL:
        for p in psutil.process_iter(["name", "exe"]):
            if match_exe and p.info["exe"] == exe:
                ls.append(p)
            elif p.info["name"] == proc_name:
                ls.append(p)
    return len(ls)


def returner(ret):
    """
    Write Prometheus metrics to a file on the minion.
    """
    state_functions = [
        "state.apply",
        "state.sls",
        "state.highstate",
    ]

    if ret["fun"] not in state_functions:
        log.warning(
            "The prometheus_textfile returner is only intended to run"
            " on %s functions... not %s",
            ", ".join(state_functions),
            ret["fun"],
        )
        raise  # pylint: disable=misplaced-bare-raise

    opts = _get_options(ret)

    prom_state = ""

    if opts["add_state_name"]:
        if ret["fun"] == "state.highstate":
            prom_state = "highstate"
        elif ret["fun"] == "state.apply" and (
            not ret["fun_args"] or "=" in ret["fun_args"][0]
        ):
            prom_state = "highstate"
        else:
            prom_state = ret["fun_args"][0]

    for fun_arg in ret["fun_args"]:
        if fun_arg.lower() == "test=true":
            log.warning("The prometheus_textfile returner is not enabled in Test mode.")
            raise  # pylint: disable=misplaced-bare-raise
        if opts["add_state_name"] and fun_arg.lower().startswith(
            "prom_textfile_state="
        ):
            prom_state = "".join(fun_arg.split("=")[1:])
            log.debug("Prometheus text file returner state name: %s", prom_state)

    out_dir = os.path.dirname(opts["filename"])

    if not os.path.isdir(out_dir):
        try:
            os.makedirs(out_dir)
        except OSError:
            log.error("Could not create directory for prometheus output: %s", out_dir)
            raise

    success = 0
    failure = 0
    changed = 0
    total = 0
    duration = 0
    for state, data in ret.get("return", {}).items():
        total += 1
        duration += data.get("duration", 0)
        if data["result"]:
            success += 1
        else:
            failure += 1
        if data.get("changes"):
            changed += 1

    if not total:
        log.error("Total states run equals 0. There may be something wrong...")
        raise salt.exceptions.SaltRunnerError

    salt_procs = _count_minion_procs(
        proc_name=opts["proc_name"],
        match_exe=opts["match_exe"],
        exe=opts["exe"],
    )

    now = int(time.time())

    output = {
        "salt_procs": {
            "help": "Number of salt minion processes running",
            "value": salt_procs,
        },
        "salt_states_succeeded": {
            "help": "Number of successful states in the run",
            "value": success,
        },
        "salt_states_failed": {
            "help": "Number of failed states in the run",
            "value": failure,
        },
        "salt_states_changed": {
            "help": "Number of changed states in the run",
            "value": changed,
        },
        "salt_states_total": {
            "help": "Total states in the run",
            "value": total,
        },
        "salt_states_success_pct": {
            "help": "Percent of successful states in the run",
            "value": round((success / total) * 100, 2),
        },
        "salt_states_failure_pct": {
            "help": "Percent of failed states in the run",
            "value": round((failure / total) * 100, 2),
        },
        "salt_states_changed_pct": {
            "help": "Percent of changed states in the run",
            "value": round((changed / total) * 100, 2),
        },
        "salt_elapsed_time": {
            "help": "Time spent for all operations during the state run",
            "value": round(duration, 3),
        },
        "salt_last_started": {
            "help": "Estimated time the state run started",
            "value": int(now - duration / 1000),
        },
        "salt_last_completed": {
            "help": "Time of last state run completion",
            "value": now,
        },
    }

    if opts["add_state_name"]:
        old_name, ext = os.path.splitext(opts["filename"])
        opts["filename"] = "{}-{}{}".format(old_name, prom_state, ext)
        log.debug(
            "Modified Prometheus filename from %s to %s",
            old_name + ext,
            opts["filename"],
        )
        for key in list(output.keys()):
            output[key + '{state="' + prom_state + '"}'] = output.pop(key)

    if opts["mode"]:
        try:
            opts["mode"] = int(opts["mode"], base=8)
        except ValueError:
            opts["mode"] = None
            log.exception("Unable to convert mode to octal. Using system default.")

    try:
        with salt.utils.files.fpopen(
            opts["filename"],
            "w",
            uid=opts["uid"],
            gid=opts["gid"],
            mode=opts["mode"],
        ) as textfile:
            outlines = []
            for key, val in output.items():
                metric = key.split("{")[0]
                outlines.append(
                    "# HELP {metric} {helptext}".format(
                        metric=metric, helptext=val["help"]
                    )
                )
                outlines.append("# TYPE {metric} gauge".format(metric=metric))
                outlines.append("{key} {value}".format(key=key, value=val["value"]))
            textfile.write("\n".join(outlines) + "\n")
    except Exception:  # pylint: disable=broad-except
        log.exception("Could not write to prometheus file: %s", opts["filename"])
        raise
