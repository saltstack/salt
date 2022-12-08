"""
An engine that reads messages from Slack and can act on them

.. versionadded:: 3006.0

:depends: `slack_bolt <https://pypi.org/project/slack_bolt/>`_ Python module

.. important::
    This engine requires a Slack app and a Slack Bot user. To create a
    bot user, first go to the **Custom Integrations** page in your
    Slack Workspace. Copy and paste the following URL, and log in with
    account credentials with administrative privileges:

    ``https://api.slack.com/apps/new``

    Next, click on the ``From scratch`` option from the ``Create an app`` popup.
    Give your new app a unique name, eg. ``SaltSlackEngine``, select the workspace
    where your app will be running, and click ``Create App``.

    Next, click on ``Socket Mode`` and then click on the toggle button for
    ``Enable Socket Mode``. In the dialog give your Socket Mode Token a unique
    name and then copy and save the app level token.  This will be used
    as the ``app_token`` parameter in the Slack engine configuration.

    Next, click on ``Event Subscriptions`` and ensure that ``Enable Events`` is in
    the on position.  Then  add the following bot events, ``message.channel``
    and ``message.im`` to the ``Subcribe to bot events`` list.

    Next, click on ``OAuth & Permissions`` and then under ``Bot Token Scope``, click
    on ``Add an OAuth Scope``.  Ensure the following scopes are included:

        - ``channels:history``
        - ``channels:read``
        - ``chat:write``
        - ``commands``
        - ``files:read``
        - ``files:write``
        - ``im:history``
        - ``mpim:history``
        - ``usergroups:read``
        - ``users:read``

    Once all the scopes have been added, click the ``Install to Workspace`` button
    under ``OAuth Tokens for Your Workspace``, then click ``Allow``.  Copy and save
    the ``Bot User OAuth Token``, this will be used as the ``bot_token`` parameter
    in the Slack engine configuration.

    Finally, add this bot user to a channel by switching to the channel and
    using ``/invite @mybotuser``. Keep in mind that this engine will process
    messages from each channel in which the bot is a member, so it is
    recommended to narrowly define the commands which can be executed, and the
    Slack users which are allowed to run commands.


This engine has two boolean configuration parameters that toggle specific
features (both default to ``False``):

1. ``control`` - If set to ``True``, then any message which starts with the
   trigger string (which defaults to ``!`` and can be overridden by setting the
   ``trigger`` option in the engine configuration) will be interpreted as a
   Salt CLI command and the engine will attempt to run it. The permissions
   defined in the various ``groups`` will determine if the Slack user is
   allowed to run the command. The ``targets`` and ``default_target`` options
   can be used to set targets for a given command, but the engine can also read
   the following two keyword arguments:

   - ``target`` - The target expression to use for the command

   - ``tgt_type`` - The match type, can be one of ``glob``, ``list``,
     ``pcre``, ``grain``, ``grain_pcre``, ``pillar``, ``nodegroup``, ``range``,
     ``ipcidr``, or ``compound``. The default value is ``glob``.

   Here are a few examples:

   .. code-block:: text

       !test.ping target=*
       !state.apply foo target=os:CentOS tgt_type=grain
       !pkg.version mypkg target=role:database tgt_type=pillar

2. ``fire_all`` - If set to ``True``, all messages which are not prefixed with
   the trigger string will fired as events onto Salt's ref:`event bus
   <event-system>`. The tag for these events will be prefixed with the string
   specified by the ``tag`` config option (default: ``salt/engines/slack``).


The ``groups_pillar_name`` config option can be used to pull group
configuration from the specified pillar key.

.. note::
    In order to use ``groups_pillar_name``, the engine must be running as a
    minion running on the master, so that the ``Caller`` client can be used to
    retrieve that minion's pillar data, because the master process does not have
    pillar data.


Configuration Examples
======================

.. versionchanged:: 2017.7.0
    Access control group support added

.. versionchanged:: 3006.0
    Updated to use slack_bolt Python library.

This example uses a single group called ``default``. In addition, other groups
are being loaded from pillar data. The users and commands defined within these
groups are used to determine whether the Slack user has permission to run
the desired command.

.. code-block:: text

    engines:
      - slack:
          app_token: "xapp-x-xxxxxxxxxxx-xxxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
          bot_token: 'xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx'
          control: True
          fire_all: False
          groups_pillar_name: 'slack_engine:groups_pillar'
          groups:
            default:
              users:
                - '*'
              commands:
                - test.ping
                - cmd.run
                - list_jobs
                - list_commands
              aliases:
                list_jobs:
                  cmd: jobs.list_jobs
                list_commands:
                  cmd: 'pillar.get salt:engines:slack:valid_commands target=saltmaster tgt_type=list'
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

This example shows multiple groups applying to different users, with all users
having access to run test.ping. Keep in mind that when using ``*``, the value
must be quoted, or else PyYAML will fail to load the configuration.

.. code-block:: text

    engines:
      - slack:
          groups_pillar: slack_engine_pillar
          app_token: "xapp-x-xxxxxxxxxxx-xxxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
          bot_token: 'xoxb-xxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx'
          control: True
          fire_all: True
          tag: salt/engines/slack
          groups_pillar_name: 'slack_engine:groups_pillar'
          groups:
            default:
              users:
                - '*'
              commands:
                - test.ping
              aliases:
                list_jobs:
                  cmd: jobs.list_jobs
                list_commands:
                  cmd: 'pillar.get salt:engines:slack:valid_commands target=saltmaster tgt_type=list'
            gods:
              users:
                - garethgreenaway
              commands:
                - '*'

"""

import ast
import collections
import datetime
import itertools
import logging
import re
import time
import traceback

import salt.client
import salt.loader
import salt.minion
import salt.output
import salt.runner
import salt.utils.args
import salt.utils.event
import salt.utils.http
import salt.utils.json
import salt.utils.slack
import salt.utils.yaml

try:
    # pylint: disable=import-error
    import slack_bolt
    import slack_bolt.adapter.socket_mode

    # pylint: enable=import-error

    HAS_SLACKBOLT = True
except ImportError:
    HAS_SLACKBOLT = False

log = logging.getLogger(__name__)

__virtualname__ = "slack_bolt"


def __virtual__():
    if not HAS_SLACKBOLT:
        return (False, "The 'slack_bolt' Python module could not be loaded")
    return __virtualname__


class SlackClient:
    def __init__(self, app_token, bot_token, trigger_string):
        self.master_minion = salt.minion.MasterMinion(__opts__)

        self.app = slack_bolt.App(token=bot_token)
        self.handler = slack_bolt.adapter.socket_mode.SocketModeHandler(
            self.app, app_token
        )
        self.handler.connect()

        self.app_token = app_token
        self.bot_token = bot_token

        self.msg_queue = collections.deque()

        trigger_pattern = "(^{}.*)".format(trigger_string)

        # Register message_trigger when we see messages that start
        # with the trigger string
        self.app.message(re.compile(trigger_pattern))(self.message_trigger)

    def _run_until(self):
        return True

    def message_trigger(self, message):
        # Add the received message to the queue
        self.msg_queue.append(message)

    def get_slack_users(self, token):
        """
        Get all users from Slack

        :type user: str
        :param token: The Slack token being used to allow Salt to interact with Slack.
        """

        ret = salt.utils.slack.query(function="users", api_key=token, opts=__opts__)
        users = {}
        if "message" in ret:
            for item in ret["message"]:
                if "is_bot" in item:
                    if not item["is_bot"]:
                        users[item["name"]] = item["id"]
                        users[item["id"]] = item["name"]
        return users

    def get_slack_channels(self, token):
        """
        Get all channel names from Slack

        :type token: str
        :param token: The Slack token being used to allow Salt to interact with Slack.
        """

        ret = salt.utils.slack.query(
            function="rooms",
            api_key=token,
            # These won't be honored until https://github.com/saltstack/salt/pull/41187/files is merged
            opts={"exclude_archived": True, "exclude_members": True},
        )
        channels = {}
        if "message" in ret:
            for item in ret["message"]:
                channels[item["id"]] = item["name"]
        return channels

    def get_config_groups(self, groups_conf, groups_pillar_name):
        """
        get info from groups in config, and from the named pillar

        :type group_conf: dict
        :param group_conf:
            The dictionary containing the groups, group members,
            and the commands those group members have access to.

        :type groups_pillar_name: str
        :param groups_pillar_name:
            can be used to pull group configuration from the specified pillar key.
        """
        # Get groups
        # Default to returning something that'll never match
        ret_groups = {
            "default": {
                "users": set(),
                "commands": set(),
                "aliases": {},
                "default_target": {},
                "targets": {},
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
        log.debug("use_groups %s", use_groups)
        try:
            groups_gen = itertools.chain(
                self._groups_from_pillar(groups_pillar_name).items(), use_groups.items()
            )
        except AttributeError:
            log.warning(
                "Failed to get groups from %s: %s or from config: %s",
                groups_pillar_name,
                self._groups_from_pillar(groups_pillar_name),
                use_groups,
            )
            groups_gen = []
        for name, config in groups_gen:
            log.info("Trying to get %s and %s to be useful", name, config)
            ret_groups.setdefault(
                name,
                {
                    "users": set(),
                    "commands": set(),
                    "aliases": {},
                    "default_target": {},
                    "targets": {},
                },
            )
            try:
                ret_groups[name]["users"].update(set(config.get("users", [])))
                ret_groups[name]["commands"].update(set(config.get("commands", [])))
                ret_groups[name]["aliases"].update(config.get("aliases", {}))
                ret_groups[name]["default_target"].update(
                    config.get("default_target", {})
                )
                ret_groups[name]["targets"].update(config.get("targets", {}))
            except (IndexError, AttributeError):
                log.warning(
                    "Couldn't use group %s. Check that targets is a dictionary and not"
                    " a list",
                    name,
                )

        log.debug("Got the groups: %s", ret_groups)
        return ret_groups

    def _groups_from_pillar(self, pillar_name):
        """

        :type pillar_name: str
        :param pillar_name: The pillar.get syntax for the pillar to be queried.

        returns a dictionary (unless the pillar is mis-formatted)
        """
        if pillar_name and __opts__["__role"] == "minion":
            pillar_groups = __salt__["pillar.get"](pillar_name, {})
            log.debug("Got pillar groups %s from pillar %s", pillar_groups, pillar_name)
            log.debug("pillar groups is %s", pillar_groups)
            log.debug("pillar groups type is %s", type(pillar_groups))
        else:
            pillar_groups = {}
        return pillar_groups

    def fire(self, tag, msg):
        """
        This replaces a function in main called 'fire'

        It fires an event into the salt bus.

        :type tag: str
        :param tag: The tag to use when sending events to the Salt event bus.

        :type msg: dict
        :param msg: The msg dictionary to send to the Salt event bus.

        """
        if __opts__.get("__role") == "master":
            fire_master = salt.utils.event.get_master_event(
                __opts__, __opts__["sock_dir"]
            ).fire_master
        else:
            fire_master = None

        if fire_master:
            fire_master(msg, tag)
        else:
            __salt__["event.send"](tag, msg)

    def can_user_run(self, user, command, groups):
        """
        Check whether a user is in any group, including whether a group has the '*' membership

        :type user: str
        :param user: The username being checked against

        :type command: str
        :param command: The command that is being invoked (e.g. test.ping)

        :type groups: dict
        :param groups: the dictionary with groups permissions structure.

        :rtype: tuple
        :returns: On a successful permitting match, returns 2-element tuple that contains
            the name of the group that successfully matched, and a dictionary containing
            the configuration of the group so it can be referenced.

            On failure it returns an empty tuple

        """
        log.info("%s wants to run %s with groups %s", user, command, groups)
        for key, val in groups.items():
            if user not in val["users"]:
                if "*" not in val["users"]:
                    continue  # this doesn't grant permissions, pass
            if (command not in val["commands"]) and (
                command not in val.get("aliases", {}).keys()
            ):
                if "*" not in val["commands"]:
                    continue  # again, pass
            log.info("Slack user %s permitted to run %s", user, command)
            return (
                key,
                val,
            )  # matched this group, return the group
        log.info("Slack user %s denied trying to run %s", user, command)
        return ()

    def commandline_to_list(self, cmdline_str, trigger_string):
        """
        cmdline_str is the string of the command line
        trigger_string is the trigger string, to be removed
        """
        cmdline = salt.utils.args.shlex_split(cmdline_str[len(trigger_string) :])
        # Remove slack url parsing
        #  Translate target=<http://host.domain.net|host.domain.net>
        #  to target=host.domain.net
        cmdlist = []
        for cmditem in cmdline:
            pattern = r"(?P<begin>.*)(<.*\|)(?P<url>.*)(>)(?P<remainder>.*)"
            mtch = re.match(pattern, cmditem)
            if mtch:
                origtext = (
                    mtch.group("begin") + mtch.group("url") + mtch.group("remainder")
                )
                cmdlist.append(origtext)
            else:
                cmdlist.append(cmditem)
        return cmdlist

    def control_message_target(
        self, slack_user_name, text, loaded_groups, trigger_string
    ):
        """Returns a tuple of (target, cmdline,) for the response

        Raises IndexError if a user can't be looked up from all_slack_users

        Returns (False, False) if the user doesn't have permission

        These are returned together because the commandline and the targeting
        interact with the group config (specifically aliases and targeting configuration)
        so taking care of them together works out.

        The cmdline that is returned is the actual list that should be
        processed by salt, and not the alias.

        """

        # Trim the trigger string from the front
        # cmdline = _text[1:].split(' ', 1)
        cmdline = self.commandline_to_list(text, trigger_string)
        permitted_group = self.can_user_run(slack_user_name, cmdline[0], loaded_groups)
        log.debug(
            "slack_user_name is %s and the permitted group is %s",
            slack_user_name,
            permitted_group,
        )

        if not permitted_group:
            return (False, None, cmdline[0])
        if not slack_user_name:
            return (False, None, cmdline[0])

        # maybe there are aliases, so check on that
        if cmdline[0] in permitted_group[1].get("aliases", {}).keys():
            use_cmdline = self.commandline_to_list(
                permitted_group[1]["aliases"][cmdline[0]].get("cmd", ""), ""
            )
            # Include any additional elements from cmdline
            use_cmdline.extend(cmdline[1:])
        else:
            use_cmdline = cmdline
        target = self.get_target(permitted_group, cmdline, use_cmdline)

        # Remove target and tgt_type from commandline
        # that is sent along to Salt
        use_cmdline = [
            item
            for item in use_cmdline
            if all(not item.startswith(x) for x in ("target", "tgt_type"))
        ]

        return (True, target, use_cmdline)

    def message_text(self, m_data):
        """
        Raises ValueError if a value doesn't work out, and TypeError if
        this isn't a message type

        :type m_data: dict
        :param m_data: The message sent from Slack

        """
        if m_data.get("type") != "message":
            raise TypeError("This is not a message")
        # Edited messages have text in message
        _text = m_data.get("text", None) or m_data.get("message", {}).get("text", None)
        try:
            log.info("Message is %s", _text)  # this can violate the ascii codec
        except UnicodeEncodeError as uee:
            log.warning("Got a message that I could not log. The reason is: %s", uee)

        # Convert UTF to string
        _text = salt.utils.json.dumps(_text)
        _text = salt.utils.yaml.safe_load(_text)

        if not _text:
            raise ValueError("_text has no value")
        return _text

    def generate_triggered_messages(
        self, token, trigger_string, groups, groups_pillar_name
    ):
        """
        slack_token = string
        trigger_string = string
        input_valid_users = set
        input_valid_commands = set

        When the trigger_string prefixes the message text, yields a dictionary
        of::

            {
                'message_data': m_data,
                'cmdline': cmdline_list, # this is a list
                'channel': channel,
                'user': m_data['user'],
                'slack_client': sc
            }

        else yields {'message_data': m_data} and the caller can handle that

        When encountering an error (e.g. invalid message), yields {}, the caller can proceed to the next message

        When the websocket being read from has given up all its messages, yields {'done': True} to
        indicate that the caller has read all of the relevant data for now, and should continue
        its own processing and check back for more data later.

        This relies on the caller sleeping between checks, otherwise this could flood
        """
        all_slack_users = self.get_slack_users(
            token
        )  # re-checks this if we have an negative lookup result
        all_slack_channels = self.get_slack_channels(
            token
        )  # re-checks this if we have an negative lookup result

        def just_data(m_data):
            """Always try to return the user and channel anyway"""
            if "user" not in m_data:
                if "message" in m_data and "user" in m_data["message"]:
                    log.debug(
                        "Message was edited, "
                        "so we look for user in "
                        "the original message."
                    )
                    user_id = m_data["message"]["user"]
                elif "comment" in m_data and "user" in m_data["comment"]:
                    log.debug("Comment was added, so we look for user in the comment.")
                    user_id = m_data["comment"]["user"]
            else:
                user_id = m_data.get("user")
            channel_id = m_data.get("channel")
            if channel_id.startswith("D"):  # private chate with bot user
                channel_name = "private chat"
            else:
                channel_name = all_slack_channels.get(channel_id)
            data = {
                "message_data": m_data,
                "user_id": user_id,
                "user_name": all_slack_users.get(user_id),
                "channel_name": channel_name,
            }
            if not data["user_name"]:
                all_slack_users.clear()
                all_slack_users.update(self.get_slack_users(token))
                data["user_name"] = all_slack_users.get(user_id)
            if not data["channel_name"]:
                all_slack_channels.clear()
                all_slack_channels.update(self.get_slack_channels(token))
                data["channel_name"] = all_slack_channels.get(channel_id)
            return data

        for sleeps in (5, 10, 30, 60):
            if self.handler:
                break
            else:
                # see https://api.slack.com/docs/rate-limits
                log.warning(
                    "Slack connection is invalid, sleeping %s",
                    sleeps,
                )
                time.sleep(
                    sleeps
                )  # respawning too fast makes the slack API unhappy about the next reconnection
        else:
            raise UserWarning(
                "Connection to slack is still invalid, giving up: {}".format(
                    self.handler
                )
            )  # Boom!
        while self._run_until():
            while self.msg_queue:
                msg = self.msg_queue.popleft()
                try:
                    msg_text = self.message_text(msg)
                except (ValueError, TypeError) as msg_err:
                    log.debug("Got an error trying to get the message text %s", msg_err)
                    yield {"message_data": msg}  # Not a message type from the API?
                    continue

                # Find the channel object from the channel name
                channel = msg["channel"]
                data = just_data(msg)
                if msg_text.startswith(trigger_string):
                    loaded_groups = self.get_config_groups(groups, groups_pillar_name)
                    if not data.get("user_name"):
                        log.error(
                            "The user %s can not be looked up via slack. What has"
                            " happened here?",
                            msg.get("user"),
                        )
                        channel.send_message(
                            "The user {} can not be looked up via slack.  Not"
                            " running {}".format(data["user_id"], msg_text)
                        )
                        yield {"message_data": msg}
                        continue
                    (allowed, target, cmdline) = self.control_message_target(
                        data["user_name"], msg_text, loaded_groups, trigger_string
                    )
                    if allowed:
                        ret = {
                            "message_data": msg,
                            "channel": msg["channel"],
                            "user": data["user_id"],
                            "user_name": data["user_name"],
                            "cmdline": cmdline,
                            "target": target,
                        }
                        yield ret
                        continue
                    else:
                        channel.send_message(
                            "{} is not allowed to use command {}.".format(
                                data["user_name"], cmdline
                            )
                        )
                        yield data
                        continue
                else:
                    yield data
                    continue
            yield {"done": True}

    def get_target(self, permitted_group, cmdline, alias_cmdline):
        """
        When we are permitted to run a command on a target, look to see
        what the default targeting is for that group, and for that specific
        command (if provided).

        It's possible for ``None`` or ``False`` to be the result of either, which means
        that it's expected that the caller provide a specific target.

        If no configured target is provided, the command line will be parsed
        for target=foo and tgt_type=bar

        Test for this::

            h = {'aliases': {}, 'commands': {'cmd.run', 'pillar.get'},
                'default_target': {'target': '*', 'tgt_type': 'glob'},
                'targets': {'pillar.get': {'target': 'you_momma', 'tgt_type': 'list'}},
                'users': {'dmangot', 'jmickle', 'pcn'}}
            f = {'aliases': {}, 'commands': {'cmd.run', 'pillar.get'},
                 'default_target': {}, 'targets': {},'users': {'dmangot', 'jmickle', 'pcn'}}

            g = {'aliases': {}, 'commands': {'cmd.run', 'pillar.get'},
                 'default_target': {'target': '*', 'tgt_type': 'glob'},
                 'targets': {}, 'users': {'dmangot', 'jmickle', 'pcn'}}

        Run each of them through ``get_configured_target(('foo', f), 'pillar.get')`` and confirm a valid target

        :type permitted_group: tuple
        :param permitted_group: A tuple containing the group name and group configuration to check for permission.

        :type cmdline: list
        :param cmdline: The command sent from Slack formatted as a list.

        :type alias_cmdline: str
        :param alias_cmdline: An alias to a cmdline.

        """
        # Default to targeting all minions with a type of glob
        null_target = {"target": "*", "tgt_type": "glob"}

        def check_cmd_against_group(cmd):
            """
            Validate cmd against the group to return the target, or a null target

            :type cmd: list
            :param cmd: The command sent from Slack formatted as a list.
            """
            name, group_config = permitted_group
            target = group_config.get("default_target")
            if not target:  # Empty, None, or False
                target = null_target
            if group_config.get("targets"):
                if group_config["targets"].get(cmd):
                    target = group_config["targets"][cmd]
            if not target.get("target"):
                log.debug(
                    "Group %s is not configured to have a target for cmd %s.", name, cmd
                )
            return target

        for this_cl in cmdline, alias_cmdline:
            _, kwargs = self.parse_args_and_kwargs(this_cl)
            if "target" in kwargs:
                log.debug("target is in kwargs %s.", kwargs)
                if "tgt_type" in kwargs:
                    log.debug("tgt_type is in kwargs %s.", kwargs)
                    return {"target": kwargs["target"], "tgt_type": kwargs["tgt_type"]}
                return {"target": kwargs["target"], "tgt_type": "glob"}

        for this_cl in cmdline, alias_cmdline:
            checked = check_cmd_against_group(this_cl[0])
            log.debug("this cmdline has target %s.", this_cl)
            if checked.get("target"):
                return checked
        return null_target

    def format_return_text(
        self, data, function, **kwargs
    ):  # pylint: disable=unused-argument
        """
        Print out YAML using the block mode

        :type user: dict
        :param token: The return data that needs to be formatted.

        :type user: str
        :param token: The function that was used to generate the return data.
        """
        # emulate the yaml_out output formatter. It relies on a global __opts__ object which
        # we can't obviously pass in
        try:
            try:
                outputter = data[next(iter(data))].get("out")
            except (StopIteration, AttributeError):
                outputter = None
            return salt.output.string_format(
                {x: y["return"] for x, y in data.items()},
                out=outputter,
                opts=__opts__,
            )
        except Exception as exc:  # pylint: disable=broad-except
            import pprint

            log.exception(
                "Exception encountered when trying to serialize %s",
                pprint.pformat(data),
            )
            return "Got an error trying to serialze/clean up the response"

    def parse_args_and_kwargs(self, cmdline):
        """

        :type cmdline: list
        :param cmdline: The command sent from Slack formatted as a list.

        returns tuple of: args (list), kwargs (dict)
        """
        # Parse args and kwargs
        args = []
        kwargs = {}

        if len(cmdline) > 1:
            for item in cmdline[1:]:
                if "=" in item:
                    (key, value) = item.split("=", 1)
                    kwargs[key] = value
                else:
                    args.append(item)
        return (args, kwargs)

    def get_jobs_from_runner(self, outstanding_jids):
        """
        Given a list of job_ids, return a dictionary of those job_ids that have
        completed and their results.

        Query the salt event bus via the jobs runner. jobs.list_job will show
        a job in progress, jobs.lookup_jid will return a job that has
        completed.

        :type outstanding_jids: list
        :param outstanding_jids: The list of job ids to check for completion.

        returns a dictionary of job id: result
        """
        # Can't use the runner because of https://github.com/saltstack/salt/issues/40671
        runner = salt.runner.RunnerClient(__opts__)
        source = __opts__.get("ext_job_cache")
        if not source:
            source = __opts__.get("master_job_cache")

        results = {}
        for jid in outstanding_jids:
            # results[jid] = runner.cmd('jobs.lookup_jid', [jid])
            if self.master_minion.returners["{}.get_jid".format(source)](jid):
                job_result = runner.cmd("jobs.list_job", [jid])
                jid_result = job_result.get("Result", {})
                jid_function = job_result.get("Function", {})
                # emulate lookup_jid's return, which is just minion:return
                results[jid] = {
                    "data": salt.utils.json.loads(salt.utils.json.dumps(jid_result)),
                    "function": jid_function,
                }

        return results

    def run_commands_from_slack_async(
        self, message_generator, fire_all, tag, control, interval=1
    ):
        """
        Pull any pending messages from the message_generator, sending each
        one to either the event bus, the command_async or both, depending on
        the values of fire_all and command

        :type message_generator: generator of dict
        :param message_generator: Generates messages from slack that should be run

        :type fire_all: bool
        :param fire_all: Whether to also fire messages to the event bus

        :type control: bool
        :param control: If set to True, whether Slack is allowed to control Salt.

        :type tag: str
        :param tag: The tag to send to use to send to the event bus

        :type interval: int
        :param interval: time to wait between ending a loop and beginning the next
        """

        outstanding = {}  # set of job_id that we need to check for

        while self._run_until():
            log.trace("Sleeping for interval of %s", interval)
            time.sleep(interval)
            # Drain the slack messages, up to 10 messages at a clip
            count = 0
            for msg in message_generator:
                if msg:
                    # The message_generator yields dicts.  Leave this loop
                    # on a dict that looks like {'done': True} or when we've done it
                    # 10 times without taking a break.
                    log.trace("Got a message from the generator: %s", msg.keys())
                    if count > 10:
                        log.warning(
                            "Breaking in getting messages because count is exceeded"
                        )
                        break
                    if not msg:
                        count += 1
                        log.warning("Skipping an empty message.")
                        continue  # This one is a dud, get the next message
                    if msg.get("done"):
                        log.trace("msg is done")
                        break
                    if fire_all:
                        log.debug("Firing message to the bus with tag: %s", tag)
                        log.debug("%s %s", tag, msg)
                        self.fire(
                            "{}/{}".format(tag, msg["message_data"].get("type")), msg
                        )
                    if control and (len(msg) > 1) and msg.get("cmdline"):
                        jid = self.run_command_async(msg)
                        log.debug("Submitted a job and got jid: %s", jid)
                        outstanding[
                            jid
                        ] = msg  # record so we can return messages to the caller
                        text_msg = "@{}'s job is submitted as salt jid {}".format(
                            msg["user_name"], jid
                        )
                        self.app.client.chat_postMessage(
                            channel=msg["channel"], text=text_msg
                        )
                    count += 1
            start_time = time.time()
            job_status = self.get_jobs_from_runner(
                outstanding.keys()
            )  # dict of job_ids:results are returned
            log.trace(
                "Getting %s jobs status took %s seconds",
                len(job_status),
                time.time() - start_time,
            )
            for jid in job_status:
                result = job_status[jid]["data"]
                function = job_status[jid]["function"]
                if result:
                    log.debug("ret to send back is %s", result)
                    # formatting function?
                    this_job = outstanding[jid]
                    channel = this_job["channel"]
                    return_text = self.format_return_text(result, function)
                    return_prefix = (
                        "@{}'s job `{}` (id: {}) (target: {}) returned".format(
                            this_job["user_name"],
                            this_job["cmdline"],
                            jid,
                            this_job["target"],
                        )
                    )
                    self.app.client.chat_postMessage(
                        channel=channel, text=return_prefix
                    )
                    ts = time.time()
                    st = datetime.datetime.fromtimestamp(ts).strftime("%Y%m%d%H%M%S%f")
                    filename = "salt-results-{}.yaml".format(st)
                    resp = self.app.client.files_upload(
                        channels=channel,
                        filename=filename,
                        content=return_text,
                    )
                    # Handle unicode return
                    log.debug("Got back %s via the slack client", resp)
                    if "ok" in resp and resp["ok"] is False:
                        this_job["channel"].send_message(
                            "Error: {}".format(resp["error"])
                        )
                    del outstanding[jid]

    def run_command_async(self, msg):

        """
        :type msg: dict
        :param msg: The message dictionary that contains the command and all information.

        """
        log.debug("Going to run a command asynchronous")
        runner_functions = sorted(salt.runner.Runner(__opts__).functions)
        # Parse args and kwargs
        cmd = msg["cmdline"][0]

        args, kwargs = self.parse_args_and_kwargs(msg["cmdline"])

        # Check for pillar string representation of dict and convert it to dict
        if "pillar" in kwargs:
            kwargs.update(pillar=ast.literal_eval(kwargs["pillar"]))

        # Check for target. Otherwise assume None
        target = msg["target"]["target"]
        # Check for tgt_type. Otherwise assume glob
        tgt_type = msg["target"]["tgt_type"]
        log.debug("target_type is: %s", tgt_type)

        if cmd in runner_functions:
            runner = salt.runner.RunnerClient(__opts__)
            log.debug("Command %s will run via runner_functions", cmd)
            # pylint is tripping
            # pylint: disable=missing-whitespace-after-comma
            job_id_dict = runner.asynchronous(cmd, {"arg": args, "kwarg": kwargs})
            job_id = job_id_dict["jid"]

        # Default to trying to run as a client module.
        else:
            log.debug(
                "Command %s will run via local.cmd_async, targeting %s", cmd, target
            )
            log.debug("Running %s, %s, %s, %s, %s", target, cmd, args, kwargs, tgt_type)
            # according to https://github.com/saltstack/salt-api/issues/164, tgt_type has changed to expr_form
            with salt.client.LocalClient() as local:
                job_id = local.cmd_async(
                    str(target),
                    cmd,
                    arg=args,
                    kwarg=kwargs,
                    tgt_type=str(tgt_type),
                )
            log.info("ret from local.cmd_async is %s", job_id)
        return job_id


def start(
    app_token,
    bot_token,
    control=False,
    trigger="!",
    groups=None,
    groups_pillar_name=None,
    fire_all=False,
    tag="salt/engines/slack",
):
    """
    Listen to slack events and forward them to salt, new version

    :type app_token: str
    :param app_token: The Slack application token used by Salt to communicate with Slack.

    :type bot_token: str
    :param bot_token: The Slack bot token used by Salt to communicate with Slack.

    :type control: bool
    :param control: Determines whether or not commands sent from Slack with the trigger string will control Salt, defaults to False.

    :type trigger: str
    :param trigger: The string that should preface all messages in Slack that should be treated as commands to send to Salt.

    :type group: str
    :param group: The string that should preface all messages in Slack that should be treated as commands to send to Salt.

    :type groups_pillar: str
    :param group_pillars: A pillar key that can be used to pull group configuration.

    :type fire_all: bool
    :param fire_all:
        If set to ``True``, all messages which are not prefixed with
        the trigger string will fired as events onto Salt's ref:`event bus
        <event-system>`. The tag for these events will be prefixed with the string
        specified by the ``tag`` config option (default: ``salt/engines/slack``).

    :type tag: str
    :param tag: The tag to prefix all events sent to the Salt event bus.
    """

    if (not bot_token) or (not bot_token.startswith("xoxb")):
        time.sleep(2)  # don't respawn too quickly
        log.error("Slack bot token not found, bailing...")
        raise UserWarning("Slack Engine bot token not configured")

    try:
        client = SlackClient(
            app_token=app_token, bot_token=bot_token, trigger_string=trigger
        )
        message_generator = client.generate_triggered_messages(
            bot_token, trigger, groups, groups_pillar_name
        )
        client.run_commands_from_slack_async(message_generator, fire_all, tag, control)
    except Exception:  # pylint: disable=broad-except
        raise Exception("{}".format(traceback.format_exc()))
