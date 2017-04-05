# -*- coding: utf-8 -*-
'''
An engine that reads messages from Hipchat and sends them to the Salt
event bus.  Alternatively Salt commands can be sent to the Salt master
via Hipchat by setting the control parameter to ``True`` and using command
prefaced with a ``!``. Only token key is required, but room and control
keys make the engine interactive.

.. versionadded: 2016.11.0

:depends: hypchat
:configuration: Example configuration

    .. code-block:: yaml

        engines:
            hipchat:
               api_url: http://api.hipchat.myteam.com
               token: 'XXXXXX'
               room: 'salt'
               control: True
               valid_users:
                   - SomeUser
               valid_commands:
                   - test.ping
                   - cmd.run
                   - list_jobs
                   - list_commands
               aliases:
                   list_jobs:
                       cmd: jobs.list_jobs
                   list_commands:
                       cmd: pillar.get salt:engines:hipchat:valid_commands target=saltmaster tgt_type=list
                max_rooms: 0
                wait_time: 1
'''

from __future__ import absolute_import
import logging
import time
import json
import os


try:
    import hypchat
    HAS_HYPCHAT = True
except ImportError:
    HAS_HYPCHAT = False

import salt.utils
import salt.utils.files
import salt.runner
import salt.client
import salt.loader


def __virtual__():
    return HAS_HYPCHAT

log = logging.getLogger(__name__)

_DEFAULT_API_URL = 'https://api.hipchat.com'
_DEFAULT_SLEEP = 5
_DEFAULT_MAX_ROOMS = 1000


def _publish_file(token, room, filepath, message='', api_url=None):
    """ Send file to a HipChat room via API version 2
    Parameters
    ----------
    token : str
        HipChat API version 2 compatible token - must be token for active user
    room: str
        Name or API ID of the room to notify
    filepath: str
        Full path of file to be sent
    message: str, optional
        Message to send to room
    api_url: str, optional
        Hipchat API URL to use, defaults to http://api.hipchat.com
    """

    if not os.path.isfile(filepath):
        raise ValueError("File '{0}' does not exist".format(filepath))
    if len(message) > 1000:
        raise ValueError('Message too long')

    url = "{0}/v2/room/{1}/share/file".format(api_url, room)
    headers = {'Content-type': 'multipart/related; boundary=boundary123456'}
    headers['Authorization'] = "Bearer " + token
    msg = json.dumps({'message': message})

    with salt.utils.fopen(filepath, 'rb') as rfh:
        payload = """\
--boundary123456
Content-Type: application/json; charset=UTF-8
Content-Disposition: attachment; name="metadata"

{0}

--boundary123456
Content-Disposition: attachment; name="file"; filename="{1}"

{2}

--boundary123456--\
""".format(msg, os.path.basename(filepath), rfh.read())

    salt.utils.http.query(url, method='POST', header_dict=headers, data=payload)


def start(token,
          room='salt',
          aliases=None,
          valid_users=None,
          valid_commands=None,
          control=False,
          trigger="!",
          tag='salt/engines/hipchat/incoming',
          api_key=None,
          api_url=None,
          max_rooms=None,
          wait_time=None):
    '''
    Listen to Hipchat messages and forward them to Salt
    '''
    target_room = None

    if __opts__.get('__role') == 'master':
        fire_master = salt.utils.event.get_master_event(
            __opts__,
            __opts__['sock_dir']).fire_event
    else:
        fire_master = None

    def fire(tag, msg):
        '''
        fire event to salt bus
        '''

        if fire_master:
            fire_master(msg, tag)
        else:
            __salt__['event.send'](tag, msg)

    def _eval_bot_mentions(all_messages, trigger):
        ''' yield partner message '''
        for message in all_messages:
            message_text = message['message']
            if message_text.startswith(trigger):
                fire(tag, message)
                text = message_text.replace(trigger, '').strip()
                yield message['from']['mention_name'], text

    token = token or api_key
    if not token:
        raise UserWarning("Hipchat token not found")

    runner_functions = sorted(salt.runner.Runner(__opts__).functions)

    if not api_url:
        api_url = _DEFAULT_API_URL
    hipc = hypchat.HypChat(token, endpoint=api_url)
    if not hipc:
        raise UserWarning("Unable to connect to hipchat")

    log.debug('Connected to Hipchat')
    rooms_kwargs = {}
    if max_rooms is None:
        max_rooms = _DEFAULT_MAX_ROOMS
        rooms_kwargs['max_results'] = max_rooms
    elif max_rooms > 0:
        rooms_kwargs['max_results'] = max_rooms
    # if max_rooms is 0 => retrieve all (rooms_kwargs is empty dict)
    all_rooms = hipc.rooms(**rooms_kwargs)['items']
    for a_room in all_rooms:
        if a_room['name'] == room:
            target_room = a_room
    if not target_room:
        log.debug("Unable to connect to room {0}".format(room))
        # wait for a bit as to not burn through api calls
        time.sleep(30)
        raise UserWarning("Unable to connect to room {0}".format(room))

    after_message_id = target_room.latest(maxResults=1)['items'][0]['id']

    while True:
        try:
            new_messages = target_room.latest(
                not_before=after_message_id)['items']
        except hypchat.requests.HttpServiceUnavailable:
            time.sleep(15)
            continue

        after_message_id = new_messages[-1]['id']
        for partner, text in _eval_bot_mentions(new_messages[1:], trigger):
            # bot summoned by partner

            if not control:
                log.debug("Engine not configured for control")
                return

            # Ensure the user is allowed to run commands
            if valid_users:
                if partner not in valid_users:
                    target_room.message('{0} not authorized to run Salt commands'.format(partner))
                    return

            args = []
            kwargs = {}

            cmdline = salt.utils.shlex_split(text)
            cmd = cmdline[0]

            # Evaluate aliases
            if aliases and isinstance(aliases, dict) and cmd in aliases.keys():
                cmdline = aliases[cmd].get('cmd')
                cmdline = salt.utils.shlex_split(cmdline)
                cmd = cmdline[0]

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

            # Ensure the command is allowed
            if valid_commands:
                if cmd not in valid_commands:
                    target_room.message('Using {0} is not allowed.'.format(cmd))
                    return

            ret = {}
            if cmd in runner_functions:
                runner = salt.runner.RunnerClient(__opts__)
                ret = runner.cmd(cmd, arg=args, kwarg=kwargs)

            # Default to trying to run as a client module.
            else:
                local = salt.client.LocalClient()
                ret = local.cmd('{0}'.format(target), cmd, args, kwargs, tgt_type='{0}'.format(tgt_type))

            tmp_path_fn = salt.utils.files.mkstemp()
            with salt.utils.fopen(tmp_path_fn, 'w+') as fp_:
                fp_.write(json.dumps(ret, sort_keys=True, indent=4))
            message_string = '@{0} Results for: {1} {2} {3} on {4}'.format(partner, cmd, args, kwargs, target)
            _publish_file(token, room, tmp_path_fn, message=message_string, api_url=api_url)
            salt.utils.safe_rm(tmp_path_fn)
        time.sleep(wait_time or _DEFAULT_SLEEP)
