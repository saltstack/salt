"""
Salt returner that reports execution results back to sentry. The returner will
inspect the payload to identify errors and flag them as such.

Pillar needs something like:

.. code-block:: yaml

    raven:
      servers:
        - http://192.168.1.1
        - https://sentry.example.com
      public_key: deadbeefdeadbeefdeadbeefdeadbeef
      secret_key: beefdeadbeefdeadbeefdeadbeefdead
      project: 1
      tags:
        - os
        - master
        - saltversion
        - cpuarch

or using a dsn:

.. code-block:: yaml

    raven:
      dsn: https://aaaa:bbbb@app.getsentry.com/12345
      tags:
        - os
        - master
        - saltversion
        - cpuarch

https://pypi.python.org/pypi/raven must be installed.

The pillar can be hidden on sentry return by setting hide_pillar: true.

The tags list (optional) specifies grains items that will be used as sentry
tags, allowing tagging of events in the sentry ui.

To report only errors to sentry, set report_errors_only: true.
"""

import logging

import salt.utils.jid

try:
    from raven import Client
    from raven.transport.http import HTTPTransport

    has_raven = True
except ImportError:
    has_raven = False

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = "sentry"


def __virtual__():
    if not has_raven:
        return (
            False,
            "Could not import sentry returner; raven python client is not installed.",
        )
    return __virtualname__


def returner(ret):
    """
    Log outcome to sentry. The returner tries to identify errors and report
    them as such. All other messages will be reported at info level.
    Failed states will be appended as separate list for convenience.
    """

    try:
        _connect_sentry(_get_message(ret), ret)
    except Exception as err:  # pylint: disable=broad-except
        log.error("Can't run connect_sentry: %s", err, exc_info=True)


def _ret_is_not_error(result):
    if result.get("return") and isinstance(result["return"], dict):
        result_dict = result["return"]
        is_staterun = all("-" in key for key in result_dict.keys())
        if is_staterun:
            failed_states = {}
            for state_id, state_result in result_dict.items():
                if not state_result["result"]:
                    failed_states[state_id] = state_result

            if failed_states:
                result["failed_states"] = failed_states
                return False
            return True

    if result.get("success"):
        return True

    return False


def _get_message(ret):
    if not ret.get("fun_args"):
        return "salt func: {}".format(ret["fun"])
    arg_string = " ".join([arg for arg in ret["fun_args"] if isinstance(arg, str)])
    kwarg_string = ""
    if isinstance(ret["fun_args"], list) and len(ret["fun_args"]) > 0:
        kwargs = ret["fun_args"][-1]
        if isinstance(kwargs, dict):
            kwarg_string = " ".join(
                sorted(
                    "{}={}".format(k, v)
                    for k, v in kwargs.items()
                    if not k.startswith("_")
                )
            )
    return "salt func: {fun} {argstr} {kwargstr}".format(
        fun=ret["fun"], argstr=arg_string, kwargstr=kwarg_string
    ).strip()


def _connect_sentry(message, result):
    """
    Connect to the Sentry server
    """
    pillar_data = __salt__["pillar.raw"]()
    grains = __salt__["grains.items"]()
    raven_config = pillar_data["raven"]
    hide_pillar = raven_config.get("hide_pillar")
    sentry_data = {
        "result": result,
        "pillar": "HIDDEN" if hide_pillar else pillar_data,
        "grains": grains,
    }
    data = {"platform": "python", "culprit": message, "level": "error"}
    tags = {}
    if "tags" in raven_config:
        for tag in raven_config["tags"]:
            tags[tag] = grains[tag]

    if _ret_is_not_error(result):
        data["level"] = "info"

    if raven_config.get("report_errors_only") and data["level"] != "error":
        return

    if raven_config.get("dsn"):
        client = Client(raven_config.get("dsn"), transport=HTTPTransport)
    else:
        try:
            servers = []
            for server in raven_config["servers"]:
                servers.append(server + "/api/store/")
            client = Client(
                servers=servers,
                public_key=raven_config["public_key"],
                secret_key=raven_config["secret_key"],
                project=raven_config["project"],
                transport=HTTPTransport,
            )
        except KeyError as missing_key:
            log.error("Sentry returner needs key '%s' in pillar", missing_key)
            return

    try:
        msgid = client.capture(
            "raven.events.Message",
            message=message,
            data=data,
            extra=sentry_data,
            tags=tags,
        )
        log.info("Message id %s written to sentry", msgid)
    except Exception as exc:  # pylint: disable=broad-except
        log.error("Can't send message to sentry: %s", exc, exc_info=True)


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    """
    Do any work necessary to prepare a JID, including sending a custom id
    """
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid(__opts__)
