# -*- coding: utf-8 -*-
'''
An engine that reads messages from Slack and sends them to the Salt
event bus.  Alternatively Salt commands can be sent to the Salt master
via Slack by setting the control parameter to ``True`` and using command
prefaced with a ``!``.

.. versionadded: 2016.3.0

:configuration: Example configuration using only the "default" group, which is special

    .. code-block:: yaml

        engines:
            slack:
               token: 'xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx'
               control: True
               groups:
                 default:
                   users:
                       - *
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

    :configuration: Example configuration using the "default" group and a non-default group and a pillar that will be merged in
        If the user is '*' (without the quotes) then the group's users or commands will match all users as appropriate
    .. versionadded: Nitrogen

        engines:
            slack:
               groups_pillar: slack_engine_pillar
               token: 'xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx'
               control: True
               groups:
                 default:
                   valid_users:
                       - *
                   valid_commands:
                       - test.ping
                 aliases:
                     list_jobs:
                         cmd: jobs.list_jobs
                     list_commands:
                         cmd: pillar.get salt:engines:slack:valid_commands target=saltmaster tgt_type=list
                 gods:
                   users:
                     - garethgreenaway
                   commands:
                     - *

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

import time

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

def _get_groups(groups_conf, groups_pillar_name):
    """
    get info from groups in config, and from the named pillar

    XXX change to getting data from pillars
    """
    # Get groups
    # Default to returning something that'll never match
    # XXX: add pillars as group config sources
    ret_groups = {
        "default": {
            "users": set(),
            "commands": set(),
            "aliases": dict()
        }
    }
    if not groups:
        use_groups = {}
    # Merge in group lists from different sources
    for name, config in groups_conf.items():
        ret_groups.setdefault(name, {
            "users": set(), "commands": set(), "aliases": set()
        })
        ret_groups[name]['users'].update(set(config['users'], []))
        ret_groups[name]['commands'].update(set(config['commands'], []))
        ret_groups[name]['aliases'].update(config['aliases'], {}))
    return ret_groups


def _fire(tag, msg):
    """
    This replaces a function in main called "fire"

    It fires an event into the salt bus.
    """
    if __opts__.get('__role') == 'master':
        fire_master = salt.utils.event.get_master_event(
            __opts__,
            __opts__['sock_dir']).fire_event
    else:
        fire_master = None

    # XXX does this return anything?
    if fire_master:
        fire_master(msg, tag)
    else:
        __salt__['event.send'](tag, msg)

def _can_user_run(user, command, groups):
    """
    Break out the permissions into the folowing:

    Check whether a user is in any group, including whether a group has the '*' membership

    :type user: str
    :param user: The username being checked against

    :type command: str
    :param command: The command that will be run

    :type groups: dict
    :param groups: the dictionary with groups permissions structure.
    """

    for k, v in groups.items():
        # XXX Add logging
        if user not in v['users']:
            if '*' not in v['users']:
                continue # pass
        if command not in v['commands']:
            if '*' not in v['commands']:
                continue # again, pass
        return True # matched
    return False




def start(token,
          aliases=None,
          control=False,
          trigger="!",
          groups=None,
          tag='salt/engines/slack'):
    '''
    Listen to Slack events and forward them to Salt
    '''
    if not token:
        raise UserWarning('Slack Bot token not found') # Maybe a sleep and then an exit?

    # all_users = _get_users(token)

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

                                # Check groups
                                loaded_groups = _get_groups()

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
                                _fire('{0}/{1}'.format(tag, _m['type']), _m)
                    else:
                        # Fire event to event bus
                        _fire('{0}/{1}'.format(tag, _m['type']), _m)
            time.sleep(1)
    else:
        raise UserWarning("Could not connect to slack")
