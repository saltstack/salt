# -*- coding: utf-8 -*-
'''An engine that reads messages from Slack. When the control parameter is set to ``True`` and using command
prefaced with the ``trigger`` (which defaults to ``!``).

In addition, when the parameter ``fire_all`` is set (defaults to False),
all messages will be fired off to the salt event bus, with the tag prefixed
by the string provided by the ``tag`` config option (defaults to ``salt/engines/slack``).

fire_all is broken at the moment with json serialization errors

.. versionadded: 2016.3.0

:configuration: Example configuration using only a "default" group.  The default group is not special.  In addition, other groups are being loaded from pillars

    .. code-block:: yaml

        engines:
            slack:
               token: 'xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx'
               control: True
               fire_all: False
               groups_pillar_name: "slack_engine:groups_pillar"
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
                   default_target:
                       target: saltmaster
                       tgt_type: glob
                   targets:
                       test.ping:
                         target: '*'
                         tgt_type: glob
                       cmd.run:
                         target: saltmaster
                         tgt_type: list


    :configuration: Example configuration using the "default" group and a non-default group and a pillar that will be merged in
        If the user is '*' (without the quotes) then the group's users or commands will match all users as appropriate
    .. versionadded: Nitrogen

        engines:
            slack:
               groups_pillar: slack_engine_pillar
               token: 'xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx'
               control: True
               fire_all: True
               tag: salt/engines/slack
               groups_pillar_name: "slack_engine:groups_pillar"
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

# XXX next step: change from sync (local.cmd) to async (local.cmd_async).  As commands are submitted,
# build an internal list of commands and their associated groups, and poll in a loop looking for
# results from the commands.
#
# On startup look for events that we may have lost from a shutdown/crash (within a reasonable time window),
# and re-build the internal list.
#
# Maybe fire events to the bus to indicate submission of jobs, and completion of jobs so the salt
# event bus can be used to record the state of the completion of each job.

# Import python libraries
from __future__ import absolute_import
import json
import itertools
import logging
import time
import re
import traceback
import yaml

try:
    import slackclient
    HAS_SLACKCLIENT = True
except ImportError:
    HAS_SLACKCLIENT = False
    log.error("The slack integration can't be loaded because of an ImportError.  Do you have the dependencies installed?")

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


def get_slack_users(token):
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

def get_config_groups(groups_conf, groups_pillar_name):
    """
    get info from groups in config, and from the named pillar

    XXX change to getting data from pillars
    """
    # Get groups
    # Default to returning something that'll never match
    ret_groups = {
        "default": {
            "users": set(),
            "commands": set(),
            "aliases": dict(),
            "default_target": dict(),
            "targets": dict()
        }
    }

    # allow for empty groups in the config file, and instead let some/all of this come
    # from pillar data.
    if not groups_conf:
        use_groups = {}
    else:
        use_groups = groups_conf
    # First obtain group lists from pillars, then in case there is any overlap, iterate over the groups
    # that come from pillars.  The configuration in files on disk/from startup
    # will override any configs from pillars.  They are meant to be complementary not to provide overrides.
    groups_gen = itertools.chain(_groups_from_pillar(groups_pillar_name).items(), use_groups.items())
    for name, config in groups_gen:
        log.info("Trying to get {} and {} to be useful".format(name, config))
        ret_groups.setdefault(name, {
            "users": set(), "commands": set(), "aliases": dict(), "default_target": dict(), "targets": dict()
        })
        ret_groups[name]['users'].update(set(config.get('users', [])))
        ret_groups[name]['commands'].update(set(config.get('commands', [])))
        ret_groups[name]['aliases'].update(config.get('aliases', {}))
        ret_groups[name]['default_target'].update(config.get('default_target', {}))
        ret_groups[name]['targets'].update(config.get('targets', {}))
    return ret_groups


def _groups_from_pillar(pillar_name):
    """pillar_prefix is the pillar.get syntax for the pillar to be queried.
    Group name is gotten via the equivalent of using
    ``salt['pillar.get']('{}:{}'.format(pillar_prefix, group_name))``
    in a jinja template.

    returns a dictionary (unless the pillar is mis-formatted)
    """
    caller = salt.client.Caller()
    pillar_groups = caller.cmd('pillar.get', pillar_name)
    # pillar_groups = __salt__['pillar.get'](pillar_name, {})
    log.info("Got pillar groups {} from pillar {}".format(pillar_groups, pillar_name))
    log.info("pillar groups type is {}".format(type(pillar_groups)))
    return pillar_groups


def fire(tag, msg):
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

def can_user_run(user, command, groups):
    """
    Break out the permissions into the folowing:

    Check whether a user is in any group, including whether a group has the '*' membership

    :type user: str
    :param user: The username being checked against

    :type command: str
    :param command: The command that is being invoked (e.g. test.ping)

    :type groups: dict
    :param groups: the dictionary with groups permissions structure.

    :rtype: tuple
    :returns: On a successful permitting match, returns 2-element tuple that contains
        the name of the group that successfuly matched, and a dictionary containing
        the configuration of the group so it can be referenced.

        On failure it returns an empty tuple

    """
    log.info("{} wants to run {} with groups {}".format(user, command, groups))
    for k, v in groups.items():
        if user not in v['users']:
            if '*' not in v['users']:
                continue # this doesn't grant permissions, pass
        if (command not in v['commands']) and (command not in v.get('aliases', {}).keys()):
            if '*' not in v['commands']:
                continue # again, pass
        log.info("Slack user {} permitted to run {}".format(user, command))
        return (k, v,) # matched this group, return the group
    log.info("Slack user {} denied trying to run {}".format(user, command))
    return ()


def generate_triggered_messages(token, trigger_string, groups, groups_pillar_name, control):
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
    all_slack_users = get_slack_users(token) # Aside here: re-check this if we have an empty lookup result
    # Check groups
    while True:
        if not slack_connect:
            # XXX  Add diagnosis and logging of slack connection failures
            # e.g. if the error message is too many requests, try to respect the retry-after header
            # see https://api.slack.com/docs/rate-limits
            time.sleep(30) # respawning too fast makes the slack API unhappy about the next reconnection
            raise UserWarning, "Connection to slack is invalid" # Boom!
        msg = sc.rtm_read()
        for m_data in msg:
            if m_data.get('type') != 'message':
                continue
            # Find the channel where the message came from
            channel = sc.server.channels.find(m_data['channel'])

            # Edited messages have text in message
            _text = m_data.get('text', None) or m_data.get('message', {}).get('text', None)
            try:
                log.info("Message is {}".format(_text)) # this can violate the ascii codec
            except UnicodeEncodeError as uee:
                log.warn("Got a message that I couldn't log.  The reason is: {}".format(uee))

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

                slack_user_name = all_slack_users.get(m_data['user'], None)
                if not slack_user_name:
                    all_slack_users = get_slack_users(token)
                    slack_user_name = all_slack_users.get(m_data['user'], None)

                log.warn("slack_user_name is {}".format(slack_user_name))

                # Ensure the command is allowed
                log.debug("Going to get groups")
                loaded_groups = get_config_groups(groups, groups_pillar_name)
                log.debug("Got the groups: {}".format(loaded_groups))

                permitted_group = can_user_run(slack_user_name, cmdline[0], loaded_groups)
                log.info("I am here")
                if slack_user_name and permitted_group:
                    # maybe there are no aliases, so check on that
                    if cmdline[0] in permitted_group[1].get('aliases', {}).keys():
                        use_cmdline = salt.utils.shlex_split(
                            permitted_group[1]['aliases'][cmdline[0]])
                    else:
                        use_cmdline = cmdline
                    yield {
                        "control": True,
                        "message_data": m_data,
                        "cmdline": use_cmdline,
                        "channel": channel,
                        "user": m_data['user'],
                        "slack_client": sc,
                        # this uses the real cmdline[0] as typed from the user to match
                        # to the expected targeting, to allow for alias targeting,
                        # though the alias could specify its own targeting as part of the
                        # provided command line.  Do one or the other, not both.
                        "target": get_configured_target(permitted_group, cmdline[0])
                    }
                else:
                    channel.send_message('{}, {} is not allowed to use command {}.'.format(m_data['user'], slack_user_name, cmdline))
                    continue

        time.sleep(1) # Sleep for a bit before asking slack again.

def get_configured_target(permitted_group, cmd):
    """When we are permitted to run a command on a target, look to see
    what the default targeting is for that group, and for that specific
    command (if provided).

    It's possible for None or False to be the result of either, which means
    that it's expected that the caller provide a specific target.

    Test for this:
    h = {'aliases': {}, 'commands': {'cmd.run', 'pillar.get'},
        'default_target': {'target': '*', 'tgt_type': 'glob'},
        'targets': {'pillar.get': {'target': 'you_momma', 'tgt_type': 'list'}},
        'users': {'dmangot', 'jmickle', 'pcn'}}
    f = {'aliases': {}, 'commands': {'cmd.run', 'pillar.get'},
         'default_target': {}, 'targets': {},'users': {'dmangot', 'jmickle', 'pcn'}}

    g = {'aliases': {}, 'commands': {'cmd.run', 'pillar.get'},
         'default_target': {'target': '*', 'tgt_type': 'glob'},
         'targets': {}, 'users': {'dmangot', 'jmickle', 'pcn'}}

    Run each of them through ``get_configured_target(("foo", f), "pillar.get")`` and confirm a valid target
    """
    name, group_config = permitted_group
    null_target =  {"target": None, "tgt_type": None}
    target = group_config.get('default_target')
    if not target: # Empty, None, or False
        target = null_target
    if group_config.get('targets'):
        if group_config['targets'].get(cmd):
            target = group_config['targets'][cmd]
    if not target.get("target"):
        log.debug("Group {} is not configured to have a target for cmd {}.".format(name, cmd))
    return target



def fire_msgs_to_event_bus(tag, message_generator, fire_all):
    """
    :type tag: str
    :param tag: The prefix of the tag to be sent onto the event bus

    :type message_generator: generator
    :param message_generator: A generator that yields dictionaries that
        contain messages that will be sent to the salt event bus
        as returned by _generate_triggered_messages when control=False
    """
    for _sg in message_generator:
        if fire_all:
            fire('{0}/{1}'.format(tag, msg.get('type')), msg)
            time.sleep(1)
        else:
            log.info("Not firing to the event bus, fire_all is not specified")


def run_commands_from_slack(message_generator, fire_all, tag):
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
        try:
            # This can fail with ascii codec impedence mismatching, remeber the str()
            log.debug("got message from message_generator: {}".format(str(msg)))
        except Exception as e:
            log.debug("Couldn't log the msg object's string because {}".format(e))

        if fire_all:
            log.debug("Firing message to the bus with tag: {}".format(tag))
            fire('{0}/{1}'.format(tag, msg.get('type')), msg)


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
            target = msg["target"].get('target', )
        else:
            target = kwargs['target']
            del kwargs['target']
        log.info("target is: {}".format(target))

        # Check for tgt_type. Otherwise assume glob
        if 'tgt_type' not in kwargs:
            tgt_type = msg["target"].get('tgt_type', 'glob')
        else:
            tgt_type = kwargs['tgt_type']
            del kwargs['tgt_type']
        if not tgt_type:
            tgt_type = 'glob' # I'm seeing this not cover everything
        log.debug("target_type is: {}".format(tgt_type))

        if cmd in runner_functions:
            runner = salt.runner.RunnerClient(__opts__)
            log.debug("Command {} will run via runner_functions".format(cmd))
            ret = runner.cmd(cmd, arg=args, kwarg=kwargs)

        # Default to trying to run as a client module.
        else:
            local = salt.client.LocalClient()
            log.debug("Command {} will run via local.cmd, targeting {}".format(cmd, target))
            log.debug("Running {}, {}, {}, {}, {}".format(str(target), cmd, args, kwargs, str(tgt_type)))
            # according to https://github.com/saltstack/salt-api/issues/164, tgt_type should change to expr_form
            ret = local.cmd(str(target), cmd, args, kwargs, expr_form=str(tgt_type))
            log.info("ret from local.cmd is {}".format(ret))

        if ret:
            log.debug("ret to send back is {}".format(ret))
            return_text = json.dumps(ret, sort_keys=True, indent=2)
            r = msg["slack_client"].api_call(
                "files.upload", channels=msg['channel'].id, files=None,
                content=return_text
            )
            # Handle unicode return
            log.debug("Got back {} via the slack client".format(r))
            result = yaml.safe_load(json.dumps(r))
            if 'ok' in result and result['ok'] is False:
                msg['channel'].send_message('Error: {0}'.format(result['error']))
        else:
            return_text = "Command {} on target {} completed".format(cmd, target)
            r = msg["slack_client"].api_call(
                "files.upload", channels=msg['channel'].id, files=None,
                content=return_text
            )


def start(token,
          control=False,
          trigger="!",
          groups=None,
          groups_pillar_name=None,
          fire_all=False,
          tag='salt/engines/slack'):
    '''
    Listen to slack events and forward them to salt, new version
    '''

    if (not token) or (not token.startswith('xoxb')):
        time.sleep(2) # don't respawn too quickly
        log.error("Slack bot token not found, bailing...")
        raise UserWarning('Slack Engine bot token not configured')

    try:
        message_generator = generate_triggered_messages(token, trigger, groups, groups_pillar_name, control)
        if control:
            log.info("Slack command mode enabled")
            run_commands_from_slack(message_generator, fire_all, tag)
        else:
            fire_msgs_to_event_bus(tag, message_generator, fire_all)
    except Exception as e:
        raise Exception("{}".format(traceback.format_exc()))
