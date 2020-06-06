"""
Return salt data via Slack using Incoming Webhooks

:codeauthor: `Carlos D. Álvaro <github@cdalvaro.io>`

The following fields can be set in the minion conf file:

.. code-block:: yaml

    slack_webhook.webhook (required, the webhook id. Just the part after: 'https://hooks.slack.com/services/')
    slack_webhook.success_title (optional, short title for succeeded states. By default: '{id} | Succeeded')
    slack_webhook.failure_title (optional, short title for failed states. By default: '{id} | Failed')
    slack_webhook.author_icon (optional, a URL that with a small 16x16px image. Must be of type: GIF, JPEG, PNG, and BMP)
    slack_webhook.show_tasks (optional, show identifiers for changed and failed tasks. By default: False)

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location:

.. code-block:: yaml

    slack_webhook.webhook
    slack_webhook.success_title
    slack_webhook.failure_title
    slack_webhook.author_icon
    slack_webhook.show_tasks

Slack settings may also be configured as:

.. code-block:: yaml

    slack_webhook:
      webhook: T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX
      success_title: '[{id}] | Success'
      failure_title: '[{id}] | Failure'
      author_icon: https://platform.slack-edge.com/img/default_application_icon.png
      show_tasks: true

    alternative.slack_webhook:
      webhook: T00000000/C00000000/YYYYYYYYYYYYYYYYYYYYYYYY
      show_tasks: false

To use the Slack returner,
append '--return slack_webhook' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return slack_webhook

To use the alternative configuration,
append '--return_config alternative' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return slack_webhook --return_config alternative

"""

import json
import logging
import urllib.parse

import salt.returners
import salt.utils.http
import salt.utils.yaml

log = logging.getLogger(__name__)

__virtualname__ = "slack_webhook"

UNCHANGED_KEY = "unchanged"
CHANGED_KEY = "changed"
FAILED_KEY = "failed"
TASKS_KEY = "tasks"
COUNTER_KEY = "counter"
DURATION_KEY = "duration"
TOTAL_KEY = "total"


def _get_options(ret=None):
    """
    Get the slack_webhook options from salt.
    :param ret: Salt return dictionary
    :return: A dictionary with options
    """

    defaults = {
        "success_title": "{id} | Succeeded",
        "failure_title": "{id} | Failed",
        "author_icon": "",
        "show_tasks": False,
    }

    attrs = {
        "webhook": "webhook",
        "success_title": "success_title",
        "failure_title": "failure_title",
        "author_icon": "author_icon",
        "show_tasks": "show_tasks",
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


def __virtual__():
    """
    Return virtual name of the module.

    :return: The virtual name of the module.
    """

    return __virtualname__


def _sprinkle(config_str):
    """
    Sprinkle with grains of salt, that is
    convert "test {id} test {host} " types of strings
    :param config_str: The string to be sprinkled
    :return: The string sprinkled
    """

    parts = [x for sub in config_str.split("{") for x in sub.split("}")]
    for i in range(1, len(parts), 2):
        parts[i] = str(__grains__.get(parts[i], ""))
    return "".join(parts)


def _format_task(task):
    """
    Return a dictionary with the task ready for slack fileds
    :param task: The name of the task

    :return: A dictionary ready to be inserted in Slack fields array
    """

    return {"value": task, "short": False}


def _generate_payload(author_icon, title, report, **kwargs):
    """
    Prepare the payload for Slack
    :param author_icon: The url for the thumbnail to be displayed
    :param title: The title of the message
    :param report: A dictionary with the report of the Salt function
    :return: The payload ready for Slack
    """

    event_rtn = kwargs.get("event_rtn", False)

    if event_rtn is True:
        author_name = report["id"]
    else:
        author_name = _sprinkle("{id}")

    title = _sprinkle(title)

    text = "Function: {}\n".format(report.get("function"))
    if len(report.get("arguments", [])) > 0:
        text += "Function Args: {}\n".format(str(list(map(str, report["arguments"]))))

    text += "JID: {}\n".format(report.get("jid"))

    if TOTAL_KEY in report:
        text += "Total: {}\n".format(report[TOTAL_KEY])

    if DURATION_KEY in report:
        text += "Duration: {:.2f} secs".format(float(report[DURATION_KEY]))

    attachments = [
        {
            "fallback": title,
            "color": "#272727",
            "author_name": author_name,
            "author_link": _sprinkle("{localhost}"),
            "author_icon": author_icon,
            "title": "Success: {}".format(str(report["success"])),
            "text": text,
        }
    ]

    if UNCHANGED_KEY in report:
        # Unchanged
        attachments.append(
            {
                "color": "good",
                "title": "Unchanged: {}".format(
                    report[UNCHANGED_KEY].get(COUNTER_KEY, 0)
                ),
            }
        )

        # Changed
        changed = {
            "color": "warning",
            "title": "Changed: {}".format(report[CHANGED_KEY].get(COUNTER_KEY, 0)),
        }

        if len(report[CHANGED_KEY].get(TASKS_KEY, [])) > 0:
            changed["fields"] = list(map(_format_task, report[CHANGED_KEY][TASKS_KEY]))

        attachments.append(changed)

        # Failed
        failed = {
            "color": "danger",
            "title": "Failed: {}".format(report[FAILED_KEY].get(COUNTER_KEY, None)),
        }

        if len(report[FAILED_KEY].get(TASKS_KEY, [])) > 0:
            failed["fields"] = list(map(_format_task, report[FAILED_KEY][TASKS_KEY]))

        attachments.append(failed)

    else:
        attachments.append(
            {
                "color": "good" if report["success"] else "danger",
                "title": "Return: {}".format(report.get("return", None)),
            }
        )

    payload = {"attachments": attachments}

    return payload


def _process_state(returns):
    """
    Process the received output state
    :param returns A dictionary with the returns of the recipe
    :return A dictionary with Unchanges, Changed and Failed tasks
    """

    sorted_data = sorted(returns.items(), key=lambda s: s[1].get("__run_num__", 0))

    n_total = 0
    n_failed = 0
    n_changed = 0
    duration = 0.0

    changed_tasks = []
    failed_tasks = []

    # gather stats
    for state, data in sorted_data:
        # state: module, stateid, name, function
        _, stateid, _, _ = state.split("_|-")
        task = "{filename}.sls | {taskname}".format(
            filename=str(data.get("__sls__")), taskname=stateid
        )

        if not data.get("result", True):
            n_failed += 1
            failed_tasks.append(task)

        if data.get("changes", {}):
            n_changed += 1
            changed_tasks.append(task)

        n_total += 1
        try:
            duration += float(data.get("duration", 0.0))
        except ValueError:
            pass

    n_unchanged = n_total - n_failed - n_changed

    return {
        TOTAL_KEY: n_total,
        UNCHANGED_KEY: {COUNTER_KEY: n_unchanged},
        CHANGED_KEY: {COUNTER_KEY: n_changed, TASKS_KEY: changed_tasks},
        FAILED_KEY: {COUNTER_KEY: n_failed, TASKS_KEY: failed_tasks},
        DURATION_KEY: duration / 1000,
    }


def _state_return(ret):
    """
    Return True if ret is a Salt state return
    :param ret: The Salt return
    """

    ret_data = ret.get("return")
    if not isinstance(ret_data, dict):
        return False

    return ret_data and "__id__" in next(iter(ret_data.values()))


def _generate_report(ret, show_tasks):
    """
    Generate a report of the Salt function
    :param ret: The Salt return
    :param show_tasks: Flag to show the name of the changed and failed states
    :return: The report
    """

    report = {
        "id": ret.get("id"),
        "success": True if ret.get("retcode", 1) == 0 else False,
        "function": ret.get("fun"),
        "arguments": ret.get("fun_args", []),
        "jid": ret.get("jid"),
    }

    ret_return = ret.get("return")
    if _state_return(ret):
        ret_return = _process_state(ret_return)
        if not show_tasks:
            del ret_return[CHANGED_KEY][TASKS_KEY]
            del ret_return[FAILED_KEY][TASKS_KEY]
    elif isinstance(ret_return, dict):
        ret_return = {
            "return": "\n{}".format(salt.utils.yaml.safe_dump(ret_return, indent=2))
        }
    else:
        ret_return = {"return": ret_return}

    report.update(ret_return)

    return report


def _post_message(webhook, author_icon, title, report, **kwargs):
    """
    Send a message to a Slack room through a webhook
    :param webhook:     The url of the incoming webhook
    :param author_icon: The thumbnail image to be displayed on the right side of the message
    :param title:       The title of the message
    :param report:      The report of the function state
    :return:            Boolean if message was sent successfully
    """

    event_rtn = kwargs.get("event_rtn", False)

    payload = _generate_payload(author_icon, title, report, event_rtn=event_rtn)

    data = urllib.parse.urlencode({"payload": json.dumps(payload, ensure_ascii=False)})

    webhook_url = urllib.parse.urljoin("https://hooks.slack.com/services/", webhook)
    query_result = salt.utils.http.query(webhook_url, "POST", data=data)

    # Sometimes the status is not available, so status 200 is assumed when it is not present
    if (
        query_result.get("body", "failed") == "ok"
        and query_result.get("status", 200) == 200
    ):
        return True
    else:
        log.error("Slack incoming webhook message post result: %s", query_result)
        return {"res": False, "message": query_result.get("body", query_result)}


def returner(ret, **kwargs):
    """
    Send a slack message with the data through a webhook
    :param ret: The Salt return
    :return: The result of the post
    """

    event_rtn = kwargs.get("event_rtn", False)

    _options = _get_options(ret)

    webhook = _options.get("webhook", None)
    show_tasks = _options.get("show_tasks")
    author_icon = _options.get("author_icon")

    if not webhook or webhook == "":
        log.error("%s.webhook not defined in salt config", __virtualname__)
        return

    report = _generate_report(ret, show_tasks)

    if report.get("success"):
        title = _options.get("success_title")
    else:
        title = _options.get("failure_title")

    slack = _post_message(webhook, author_icon, title, report, event_rtn=event_rtn)

    return slack


def event_return(events):
    """
    Send event data to returner function
    :param events: The Salt event return
    :return: The result of the post
    """

    results = None

    for event in events:
        ret = event.get("data", False)

        if (
            ret
            and "saltutil.find_job" not in ret["fun"]
            or "salt/auth" not in ret["tag"]
        ):
            results = returner(ret, event_rtn=True)

    return results
