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
                   - list_jobs
                   - list_commands
               aliases:
                   list_jobs:
                       cmd: jobs.list_jobs
                   list_commands:
                       cmd: pillar.get salt:engines:slack:valid_commands target=saltmaster tgt_type=list

    :configuration: Example configuration using groups
    .. versionadded: Nitrogen

        engines:
            slack:
               token: 'xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx'
               control: True
               groups:
                 gods:
                   users:
                     - garethgreenaway
                   commands:
                     - test.ping
                     - cmd.run
                     - list_jobs
                     - list_commands
               aliases:
                   list_jobs:
                       cmd: jobs.list_jobs
                   list_commands:
                       cmd: pillar.get salt:engines:slack:valid_commands target=saltmaster tgt_type=list


:depends: slackclient
'''

# Import python libraries
from __future__ import absolute_import
import datetime
import json
import logging
import time
import re
import yaml

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
    return HAS_SLACKCLIENT

log = logging.getLogger(__name__)


def _get_users(token):
    '''
    Get all users from Slack
    '''

    ret = salt.utils.slack.query(function='users',
                                 api_key=token,
                                 opts=__opts__)
    users = {}
    if 'message' in ret:
        for item in ret['message']:
            if 'is_bot' in item:
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
          groups=None,
          tag='salt/engines/slack'):
    '''
    Listen to Slack events and forward them to Salt
    '''

    if valid_users is None:
        valid_users = []

    if valid_commands is None:
        valid_commands = []

    if __opts__.get('__role') == 'master':
        fire_master = salt.utils.event.get_master_event(
            __opts__,
            __opts__['sock_dir']).fire_event
    else:
        fire_master = None

    def fire(tag, msg):
        '''
        Fire event to salt bus
        '''
        if fire_master:
            fire_master(msg, tag)
        else:
            __salt__['event.send'](tag, msg)

    if not token:
        raise UserWarning('Slack Bot token not found')

    all_users = _get_users(token)

    sc = slackclient.SlackClient(token)
    slack_connect = sc.rtm_connect()
    log.debug('connected to slack')

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

                        # Convert UTF to string
                        _text = json.dumps(_text)
                        _text = yaml.safe_load(_text)

                        if _text:
                            if _text.startswith(trigger) and control:

                                # Get groups
                                if groups:
                                    for group in groups:
                                        if 'users' in groups[group]:
                                            # Add users to valid_users
                                            valid_users.extend(groups[group]['users'])

                                            # Add commands to valid_commands
                                            if 'commands' in groups[group]:
                                                valid_commands.extend(groups[group]['commands'])

                                            # Add group aliases to aliases
                                            if 'aliases' in groups[group]:
                                                aliases.update(groups[group]['aliases'])

                                # Ensure the user is allowed to run commands
                                if valid_users:
                                    log.debug('{0} {1}'.format(all_users, _m['user']))
                                    if _m['user'] not in valid_users and all_users.get(_m['user'], None) not in valid_users:
                                        channel.send_message('{0} not authorized to run Salt commands'.format(all_users[_m['user']]))
                                        return

                                # Trim the ! from the front
                                # cmdline = _text[1:].split(' ', 1)
                                cmdline = salt.utils.shlex_split(_text[len(trigger):])

                                # Remove slack url parsing
                                #  Translate target=<http://host.domain.net|host.domain.net>
                                #  to target=host.domain.net
                                cmdlist = []
                                for cmditem in cmdline:
                                    pattern = r'(?P<begin>.*)(<.*\|)(?P<url>.*)(>)(?P<remainder>.*)'
                                    m = re.match(pattern, cmditem)
                                    if m:
                                        origtext = m.group('begin') + m.group('url') + m.group('remainder')
                                        cmdlist.append(origtext)
                                    else:
                                        cmdlist.append(cmditem)
                                cmdline = cmdlist

                                cmd = cmdline[0]
                                args = []
                                kwargs = {}

                                # Evaluate aliases
                                if aliases and isinstance(aliases, dict) and cmd in aliases.keys():
                                    cmdline = aliases[cmd].get('cmd')
                                    cmdline = salt.utils.shlex_split(cmdline)
                                    cmd = cmdline[0]

                                # Ensure the command is allowed
                                if valid_commands:
                                    if cmd not in valid_commands:
                                        channel.send_message('{0} is not allowed to use command {1}.'.format(all_users[_m['user']], cmd))
                                        return

                                # Parse args and kwargs
                                if len(cmdline) > 1:
                                    for item in cmdline[1:]:
                                        if '=' in item:
                                            (key, value) = item.split('=', 1)
                                            kwargs[key] = value
                                        else:
                                            args.append(item)

                                # Check for target. Otherwise assume *
                                if 'target' not in kwargs:
                                    target = '*'
                                else:
                                    target = kwargs['target']
                                    del kwargs['target']

                                # Check for tgt_type. Otherwise assume glob
                                if 'tgt_type' not in kwargs:
                                    tgt_type = 'glob'
                                else:
                                    tgt_type = kwargs['tgt_type']
                                    del kwargs['tgt_type']

                                ret = {}

                                if cmd in runner_functions:
                                    runner = salt.runner.RunnerClient(__opts__)
                                    ret = runner.cmd(cmd, arg=args, kwarg=kwargs)

                                # Default to trying to run as a client module.
                                else:
                                    local = salt.client.LocalClient()
                                    ret = local.cmd('{0}'.format(target), cmd, args, kwargs, tgt_type='{0}'.format(tgt_type))

                                if ret:
                                    return_text = json.dumps(ret, sort_keys=True, indent=1)
                                    ts = time.time()
                                    st = datetime.datetime.fromtimestamp(ts).strftime('%Y%m%d%H%M%S%f')
                                    filename = 'salt-results-{0}.yaml'.format(st)
                                    result = sc.api_call(
                                        "files.upload", channels=_m['channel'], filename=filename,
                                        content=return_text
                                    )
                                    # Handle unicode return
                                    result = json.dumps(result)
                                    result = yaml.safe_load(result)
                                    if 'ok' in result and result['ok'] is False:
                                        channel.send_message('Error: {0}'.format(result['error']))
                            else:
                                # Fire event to event bus
                                fire('{0}/{1}'.format(tag, _m['type']), _m)
                    else:
                        # Fire event to event bus
                        fire('{0}/{1}'.format(tag, _m['type']), _m)
            time.sleep(1)
    else:
        raise UserWarning("Could not connect to slack")
