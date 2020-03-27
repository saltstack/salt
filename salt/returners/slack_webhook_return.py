# -*- coding: utf-8 -*-
'''
Return salt data via Slack using Incoming Webhooks

:codeauthor: `Carlos D. Álvaro <github@cdalvaro.io>`

The following fields can be set in the minion conf file:

.. code-block:: none

    slack_webhook.webhook (required, the webhook id. Just the part after: 'https://hooks.slack.com/services/')
    slack_webhook.success_title (optional, short title for succeeded states. By default: '{id} | Succeeded')
    slack_webhook.failure_title (optional, short title for failed states. By default: '{id} | Failed')
    slack_webhook.author_icon (optional, a URL that with a small 16x16px image. Must be of type: GIF, JPEG, PNG, and BMP)
    slack_webhook.show_tasks (optional, show identifiers for changed and failed tasks. By default: False)

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location:

.. code-block:: none

    slack_webhook.webhook
    slack_webhook.success_title
    slack_webhook.failure_title
    slack_webhook.author_icon
    slack_webhook.show_tasks

Slack settings may also be configured as:

.. code-block:: none

    slack_webhook:
        webhook: T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX
        success_title: [{id}] | Success
        failure_title: [{id}] | Failure
        author_icon: https://platform.slack-edge.com/img/default_application_icon.png
        show_tasks: true

    alternative.slack_webhook:
        webhook: T00000000/C00000000/YYYYYYYYYYYYYYYYYYYYYYYY
        show_tasks: false

To use the Slack returner, append '--return slack_webhook' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return slack_webhook

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return slack_webhook --return_config alternative

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging
import json

# pylint: disable=import-error,no-name-in-module,redefined-builtin
import salt.ext.six.moves.http_client
from salt.ext.six.moves.urllib.parse import urlencode as _urlencode
from salt.ext import six
from salt.ext.six.moves import map
from salt.ext.six.moves import range
# pylint: enable=import-error,no-name-in-module,redefined-builtin

# Import Salt Libs
import salt.returners
import salt.utils.http
import salt.utils.yaml

log = logging.getLogger(__name__)

__virtualname__ = 'slack_webhook'


def _get_options(ret=None):
    '''
    Get the slack_webhook options from salt.
    :param ret: Salt return dictionary
    :return: A dictionary with options
    '''

    defaults = {
        'success_title': '{id} | Succeeded',
        'failure_title': '{id} | Failed',
        'author_icon': '',
        'show_tasks': False
    }

    attrs = {
        'webhook': 'webhook',
        'success_title': 'success_title',
        'failure_title': 'failure_title',
        'author_icon': 'author_icon',
        'show_tasks': 'show_tasks'
    }

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__,
                                                   defaults=defaults)
    return _options


def __virtual__():
    '''
    Return virtual name of the module.

    :return: The virtual name of the module.
    '''
    return __virtualname__


def _sprinkle(config_str):
    '''
    Sprinkle with grains of salt, that is
    convert 'test {id} test {host} ' types of strings
    :param config_str: The string to be sprinkled
    :return: The string sprinkled
    '''
    parts = [x for sub in config_str.split('{') for x in sub.split('}')]
    for i in range(1, len(parts), 2):
        parts[i] = six.text_type(__grains__.get(parts[i], ''))
    return ''.join(parts)


def _format_task(task):
    '''
    Return a dictionary with the task ready for slack fileds
    :param task: The name of the task

    :return: A dictionary ready to be inserted in Slack fields array
    '''
    return {'value': task, 'short': False}


def _generate_payload(author_icon, title, report):
    '''
    Prepare the payload for Slack
    :param author_icon: The url for the thumbnail to be displayed
    :param title: The title of the message
    :param report: A dictionary with the report of the Salt function
    :return: The payload ready for Slack
    '''

    title = _sprinkle(title)

    unchanged = {
        'color': 'good',
        'title': 'Unchanged: {unchanged}'.format(unchanged=report['unchanged'].get('counter', None))
    }

    changed = {
        'color': 'warning',
        'title': 'Changed: {changed}'.format(changed=report['changed'].get('counter', None))
    }

    if report['changed'].get('tasks'):
        changed['fields'] = list(
            map(_format_task, report['changed'].get('tasks')))

    failed = {
        'color': 'danger',
        'title': 'Failed: {failed}'.format(failed=report['failed'].get('counter', None))
    }

    if report['failed'].get('tasks'):
        failed['fields'] = list(
            map(_format_task, report['failed'].get('tasks')))

    text = 'Function: {function}\n'.format(function=report.get('function'))
    if report.get('arguments'):
        text += 'Function Args: {arguments}\n'.format(
            arguments=str(list(map(str, report.get('arguments')))))

    text += 'JID: {jid}\n'.format(jid=report.get('jid'))
    text += 'Total: {total}\n'.format(total=report.get('total'))
    text += 'Duration: {duration:.2f} secs'.format(
        duration=float(report.get('duration')))

    payload = {
        'attachments': [
            {
                'fallback': title,
                'color': "#272727",
                'author_name': _sprinkle('{id}'),
                'author_link': _sprinkle('{localhost}'),
                'author_icon': author_icon,
                'title': 'Success: {success}'.format(success=str(report.get('success'))),
                'text': text
            },
            unchanged,
            changed,
            failed
        ]
    }

    return payload


def _generate_report(ret, show_tasks):
    '''
    Generate a report of the Salt function
    :param ret: The Salt return
    :param show_tasks: Flag to show the name of the changed and failed states
    :return: The report
    '''

    returns = ret.get('return')

    sorted_data = sorted(
        returns.items(),
        key=lambda s: s[1].get('__run_num__', 0)
    )

    total = 0
    failed = 0
    changed = 0
    duration = 0.0

    changed_tasks = []
    failed_tasks = []

    # gather stats
    for state, data in sorted_data:
        # state: module, stateid, name, function
        _, stateid, _, _ = state.split('_|-')
        task = '{filename}.sls | {taskname}'.format(
            filename=str(data.get('__sls__')), taskname=stateid)

        if not data.get('result', True):
            failed += 1
            failed_tasks.append(task)

        if data.get('changes', {}):
            changed += 1
            changed_tasks.append(task)

        total += 1
        try:
            duration += float(data.get('duration', 0.0))
        except ValueError:
            pass

    unchanged = total - failed - changed

    log.debug('%s total: %s', __virtualname__, total)
    log.debug('%s failed: %s', __virtualname__, failed)
    log.debug('%s unchanged: %s', __virtualname__, unchanged)
    log.debug('%s changed: %s', __virtualname__, changed)

    report = {
        'id': ret.get('id'),
        'success': True if failed == 0 else False,
        'total': total,
        'function': ret.get('fun'),
        'arguments': ret.get('fun_args', []),
        'jid': ret.get('jid'),
        'duration': duration / 1000,
        'unchanged': {
            'counter': unchanged
        },
        'changed': {
            'counter': changed,
            'tasks': changed_tasks if show_tasks else []
        },
        'failed': {
            'counter': failed,
            'tasks': failed_tasks if show_tasks else []
        }
    }

    return report


def _post_message(webhook, author_icon, title, report):
    '''
    Send a message to a Slack room through a webhook
    :param webhook:     The url of the incoming webhook
    :param author_icon: The thumbnail image to be displayed on the right side of the message
    :param title:       The title of the message
    :param report:      The report of the function state
    :return:            Boolean if message was sent successfully
    '''

    payload = _generate_payload(author_icon, title, report)

    data = _urlencode({
        'payload': json.dumps(payload, ensure_ascii=False)
    })

    webhook_url = 'https://hooks.slack.com/services/{webhook}'.format(webhook=webhook)
    query_result = salt.utils.http.query(webhook_url, 'POST', data=data)

    if query_result['body'] == 'ok' or query_result['status'] <= 201:
        return True
    else:
        log.error('Slack incoming webhook message post result: %s', query_result)
        return {
            'res': False,
            'message': query_result.get('body', query_result['status'])
        }


def returner(ret):
    '''
    Send a slack message with the data through a webhook
    :param ret: The Salt return
    :return: The result of the post
    '''

    _options = _get_options(ret)

    webhook = _options.get('webhook', None)
    show_tasks = _options.get('show_tasks')
    author_icon = _options.get('author_icon')

    if not webhook or webhook is '':
        log.error('%s.webhook not defined in salt config', __virtualname__)
        return

    report = _generate_report(ret, show_tasks)

    if report.get('success'):
        title = _options.get('success_title')
    else:
        title = _options.get('failure_title')

    slack = _post_message(webhook, author_icon, title, report)

    return slack
