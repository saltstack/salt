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

def _get_groups(groups_conf): # , groups_pillar_name):
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
    if not groups_conf:
        use_groups = {}
    # Merge in group lists from different sources
    for name, config in groups_conf.items():
        ret_groups.setdefault(name, {
            "users": set(), "commands": set(), "aliases": set()
        })
        ret_groups[name]['users'].update(set(config.get('users', [])))
        ret_groups[name]['commands'].update(set(config.get('commands', [])))
        ret_groups[name]['aliases'].update(config.get('aliases', {}))
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


def _generate_triggered_messages(token, trigger_string, groups, control):
    """
    slack_token = string
    trigger_string = string
    input_valid_users = set
    input_valid_commands = set

    when control is False, yields a dictionary of {
        "control": False,
        "message_data": m_data
    }

    When control is True, yields a dictionary of {
        "control": True,
        "message_data": m_data,
        "cmdline": cmdline_list, # this is a list
        "channel": channel,
        "user": m_data['user'],
        "slack_client": sc
    }

    """
    sc = slackclient.SlackClient(token)
    slack_connect = sc.rtm_connect()
    log.info('connected to slack')
    all_users = _get_users(token) # Aside here: re-check this if we have an empty lookup result
    # Check groups
    loaded_groups = _get_groups(groups)
    while True:
        if not slack_connect:
            # XXX  VERY IMPORTANT ADD DIAGNOSIS
            # e.g. if the error message is too many requests, try to respect the retry-after header
            # see https://api.slack.com/docs/rate-limits
            time.sleep(1)
            raise UserWarning, "Connection to slack is invalid" # Boom!

        msg = sc.rtm_read()
        for m_data in msg:
            if m_data.get('type') != 'message':
                continue
            # Find the channel where the message came from
            channel = sc.server.channels.find(m_data['channel'])

            # Edited messages have text in message
            _text = m_data.get('text', None) or m_data.get('message', {}).get('text', None)

            # Convert UTF to string
            _text = json.dumps(_text)
            _text = yaml.safe_load(_text)

            if not control:
                yield {
                    "control": False,
                    "message": m_data
                }

            if not _text:
                continue
            if _text.startswith(trigger_string) and control:
                # Trim the trigger string from the front
                # cmdline = _text[1:].split(' ', 1)
                cmdline = salt.utils.shlex_split(_text[len(trigger_string):])

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

                # XXX: fix aliases
                # # Evaluate aliases
                # if 'keys' in dir(aliases) and cmd in aliases.keys():
                #     cmdline = aliases[cmd].get('cmd')
                #     cmdline = salt.utils.shlex_split(cmdline)
                #     cmd = cmdline[0]

                # Ensure the command is allowed
                if _can_user_run(m_data['user'], cmdline[0], groups):
                    yield {
                        "control": True,
                        "message_data": m_data,
                        "cmdline": cmdline,
                        "channel": channel,
                        "user": m_data['user'],
                        "slack_client": sc
                    }
                else:
                    channel.send_message('{0} is not allowed to use command {1}.'.format(all_users[m_data['user']], cmdline))
                    continue

        time.sleep(1) # Sleep for a bit before asking slack again.



def fire_msgs_to_event_bus(tag, message_generator):
    """
    :type tag: str
    :param tag: The prefix of the tag to be sent onto the event bus

    :type message_generator: generator
    :param message_generator: A generator that yields dictionaries that
        contain messages that will be sent to the salt event bus
        as returned by _generate_triggered_messages when control=False
    """
    for _msg in message_generator:
        _fire('{0}/{1}'.format(tag, _msg['type']), _msg)
        time.sleep(1)


def run_commands_from_slack(message_generator):
    """
    :type tag: str
    :param tag: The prefix of the tag to be sent onto the event bus

    :type message_generator: generator
    :param message_generator: A generator that yields dictionaries that
        contain the keys/values as returned by _generate_triggered_messages
        when control=False
    """

    runner_functions = sorted(salt.runner.Runner(__opts__).functions)

    for msg in message_generator:
        log.info("got message from message_generator: {}".format(msg))
        # Parse args and kwargs
        cmdline = msg['cmdline']
        cmd = cmdline[0]
        args = []
        kwargs = {}
        ret = {}

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
        log.info("target is: {}".format(target))

        # Check for tgt_type. Otherwise assume glob
        if 'tgt_type' not in kwargs:
            tgt_type = 'glob'
        else:
            tgt_type = kwargs['tgt_type']
            del kwargs['tgt_type']
        log.info("target_type is: {}".format(tgt_type))

        if cmd in runner_functions:
            runner = salt.runner.RunnerClient(__opts__)
            log.info("Command {} will run via runner_functions".format(cmd))
            ret = runner.cmd(cmd, arg=args, kwarg=kwargs)

        # Default to trying to run as a client module.
        else:
            local = salt.client.LocalClient()
            log.info("Command {} will be run via local.cmd, targeting {}".format(cmd, target))
            log.info("Running {}, {}, {}, {}, {}".format(str(target), cmd, args, kwargs, str(tgt_type)))
            # according to https://github.com/saltstack/salt-api/issues/164, tgt_type should change to expr_form
            ret = local.cmd(str(target), cmd, args, kwargs, expr_form=str(tgt_type))
            log.info("ret from local.cmd is {}".format(ret))

        if ret:
            log.info("ret to send back is {}".format(ret))
            return_text = json.dumps(ret, sort_keys=True, indent=1)
            ts = time.time()
            st = datetime.datetime.fromtimestamp(ts).strftime('%Y%m%d%H%M%S%f')
            filename = '/tmp/salt-results-{0}.yaml'.format(st)
            with open(filename, 'w') as retfile:
                log.info("Returning {} via the slack client".format(filename))
                json.dump(ret, retfile, sort_keys=True)
                # r = msg["slack_client"].api_call(
                #     "files.upload", channels=msg['channel'], file=open(filename),
                #     content=return_text
                # )
                log.info("the channel objects' dir looks like: {}".format(dir(msg['channel'])))
                r = msg["slack_client"].api_call(
                    "files.upload", channels=msg['channel'].id, files=filename,
                    content=return_text
                )
                # Handle unicode return
                log.info("Got back {} via the slack client".format(r))
                result = yaml.safe_load(json.dumps(r))
                if 'ok' in result and result['ok'] is False:
                    msg['channel'].send_message('Error: {0}'.format(result['error']))


def start(token,
          aliases=None,
          control=False,
          trigger="!",
          groups=None,
          tag='salt/engines/slack'):
    '''
    Listen to slack events and forward them to salt, new version
    '''

    if not token:
        time.sleep(2) # don't respawn too quickly
        raise UserWarning('Slack Engine token not found')

    message_generator = _generate_triggered_messages(token, trigger, groups, control)

    if control:
        run_commands_from_slack(message_generator)
    else:
        fire_msgs_to_event_bus(tag, message_generator)
