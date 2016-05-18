# -*- coding: utf-8 -*-
'''
An engine that reads messages from Slack and sends them to the Salt
event bus.  Alternatively Salt commands can be sent to the Salt master
via Slack by setting the control parameter to ``True`` and using command
prefaced with a ``!``.

.. versionadded: 2016.3.0

:configuration: Example configuration

    .. code-block:: yaml

        engines:
            slack:
               token: 'xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx'
               control: True
               valid_users:
                   - garethgreenaway
               valid_commands:
                   - test.ping
                   - cmd.run
               aliases:
                   list_jobs:
                       type: runner
                       cmd: jobs.list_jobs

:depends: slackclient
'''

# Import python libraries
from __future__ import absolute_import
import datetime
import json
import logging
import pprint
import time
try:
    import slackclient
    HAS_SLACKCLIENT = True
except ImportError:
    HAS_SLACKCLIENT = False

# Import salt libs
import salt.client
import salt.loader
import salt.runner
import salt.utils
import salt.utils.event
import salt.utils.http
import salt.utils.slack


def __virtual__():
    if not HAS_SLACKCLIENT:
        return False
    else:
        return True

log = logging.getLogger(__name__)


def _get_users(token):
    '''
    Get all users from Slack
    '''

    log.debug('running _get_users')
    ret = salt.utils.slack.query(function='users',
                                 api_key=token,
                                 opts=__opts__)
    users = {}
    if 'message' in ret:
        for item in ret['message']:
            if not item['is_bot']:
                users[item['name']] = item['id']
                users[item['id']] = item['name']
    return users


def start(token,
          aliases=None,
          valid_users=None,
          valid_commands=None,
          control=False,
          trigger="!",
          tag='salt/engines/slack'):
    '''
    Listen to Slack events and forward them to Salt
    '''
    if __opts__.get('__role') == 'master':
        fire_master = salt.utils.event.get_master_event(
            __opts__,
            __opts__['sock_dir']).fire_event
    else:
        fire_master = None

    def fire(tag, msg):
        if fire_master:
            fire_master(msg, tag)
        else:
            __salt__['event.send'](tag, msg)

    if not token:
        log.debug('Slack Bot token not found')
        return
    all_users = _get_users(token)

    sc = slackclient.SlackClient(token)
    slack_connect = sc.rtm_connect()

    runner_functions = sorted(salt.runner.Runner(__opts__).functions)

    if slack_connect:
        while True:
            _msg = sc.rtm_read()
            for _m in _msg:
                if 'type' in _m:
                    if _m['type'] == 'message':
                        # Find the channel where the message came from
                        channel = sc.server.channels.find(_m['channel'])

                        # Edited messages have text in message
                        _text = _m.get('text', None) or _m.get('message', {}).get('text', None)
                        if _text:
                            if _text.startswith(trigger) and control:

                                # Ensure the user is allowed to run commands
                                if valid_users:
                                    log.debug('{0} {1}'.format(all_users, _m['user']))
                                    if _m['user'] not in valid_users and all_users.get(_m['user'], None) not in valid_users:
                                        channel.send_message('{0} not authorized to run Salt commands'.format(all_users[_m['user']]))
                                        return

                                # Trim the ! from the front
                                # cmdline = _text[1:].split(' ', 1)
                                cmdline = salt.utils.shlex_split(_text[len(trigger):])
                                cmd = cmdline[0]
                                args = []
                                kwargs = {}

                                # Ensure the command is allowed
                                if valid_commands:
                                    if cmd not in valid_commands:
                                        channel.send_message('Using {0} is not allowed.'.format(cmd))
                                        return

                                if len(cmdline) > 1:
                                    for item in cmdline[1:]:
                                        if '=' in item:
                                            (key, value) = item.split('=', 1)
                                            kwargs[key] = value
                                        else:
                                            args.append(item)

                                if 'target' not in kwargs:
                                    target = '*'
                                else:
                                    target = kwargs['target']
                                    del kwargs['target']

                                ret = {}
                                if aliases and isinstance(aliases, dict) and cmd in aliases.keys():
                                    salt_cmd = aliases[cmd].get('cmd')

                                    if 'type' in aliases[cmd]:
                                        if aliases[cmd]['type'] == 'runner':
                                            runner = salt.runner.RunnerClient(__opts__)
                                            ret = runner.cmd(salt_cmd, arg=args, kwarg=kwargs)
                                    else:
                                        local = salt.client.LocalClient()
                                        ret = local.cmd('{0}'.format(target), salt_cmd, args, kwargs)

                                elif cmd in runner_functions:
                                    runner = salt.runner.RunnerClient(__opts__)
                                    ret = runner.cmd(cmd, arg=args, kwarg=kwargs)

                                # default to trying to run as a client module.
                                else:
                                    local = salt.client.LocalClient()
                                    ret = local.cmd('{0}'.format(target), cmd, args, kwargs)

                                if ret:
                                    pp = pprint.PrettyPrinter(width=1)
                                    return_text = pp.pformat(ret)
                                    ts = time.time()
                                    st = datetime.datetime.fromtimestamp(ts).strftime('%Y%m%d%H%M%S%f')
                                    filename = 'salt-results-{0}.yaml'.format(st)
                                    result = sc.api_call(
                                        "files.upload", channels=_m['channel'], filename=filename,
                                        content=return_text
                                    )
                                    _result = json.loads(result)
                                    if 'ok' in _result and _result['ok'] is False:
                                        channel.send_message('Error: {0}'.format(_result['error']))
                            else:
                                # Fire event to event bus
                                fire('{0}/{1}'.format(tag, _m['type']), _m)
                    else:
                        # Fire event to event bus
                        fire('{0}/{1}'.format(tag, _m['type']), _m)
