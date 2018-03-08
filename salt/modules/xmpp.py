# -*- coding: utf-8 -*-
'''
Module for Sending Messages via XMPP (a.k.a. Jabber)

.. versionadded:: 2014.1.0

:depends:   - sleekxmpp>=1.3.1
            - pyasn1
            - pyasn1-modules
            - dnspython
:configuration: This module can be used by either passing a jid and password
    directly to send_message, or by specifying the name of a configuration
    profile in the minion config, minion pillar, or master config.

    For example:

    .. code-block:: yaml

        my-xmpp-login:
            xmpp.jid: myuser@jabber.example.org/resourcename
            xmpp.password: verybadpass

    The resourcename refers to the resource that is using this account. It is
    user-definable, and optional. The following configurations are both valid:

    .. code-block:: yaml

        my-xmpp-login:
            xmpp.jid: myuser@jabber.example.org/salt
            xmpp.password: verybadpass

        my-xmpp-login:
            xmpp.jid: myuser@jabber.example.org
            xmpp.password: verybadpass

'''

# Import Python Libs
from __future__ import absolute_import, print_function, unicode_literals

import logging

HAS_LIBS = False
try:
    from sleekxmpp import ClientXMPP as _ClientXMPP
    from sleekxmpp.exceptions import XMPPError
    HAS_LIBS = True
except ImportError:
    class _ClientXMPP(object):
        '''
        Fake class in order not to raise errors
        '''

log = logging.getLogger(__name__)

__virtualname__ = 'xmpp'

MUC_DEPRECATED = "Use of send mask waiters is deprecated."


def __virtual__():
    '''
    Only load this module if sleekxmpp is installed on this minion.
    '''
    if HAS_LIBS:
        return __virtualname__
    return (False, "Module xmpp: required libraries failed to load")


class SleekXMPPMUC(logging.Filter):
    def filter(self, record):
        return not record.getMessage() == MUC_DEPRECATED


class SendMsgBot(_ClientXMPP):

    def __init__(self, jid, password, recipient, msg):  # pylint: disable=E1002
        # PyLint wrongly reports an error when calling super, hence the above
        # disable call
        super(SendMsgBot, self).__init__(jid, password)

        self.recipients = [] if recipient is None else [recipient]
        self.rooms = []

        self.msg = msg

        self.add_event_handler('session_start', self.start)

    @classmethod
    def create_multi(cls, jid, password, msg, recipients=None, rooms=None,
                     nick="SaltStack Bot"):
        '''
        Alternate constructor that accept multiple recipients and rooms
        '''
        obj = SendMsgBot(jid, password, None, msg)
        obj.recipients = [] if recipients is None else recipients
        obj.rooms = [] if rooms is None else rooms
        obj.nick = nick
        return obj

    def start(self, event):
        self.send_presence()
        self.get_roster()

        for recipient in self.recipients:
            self.send_message(mto=recipient,
                              mbody=self.msg,
                              mtype='chat')

        for room in self.rooms:
            self.plugin['xep_0045'].joinMUC(room,
                                            self.nick,
                                            wait=True)
            self.send_message(mto=room,
                              mbody=self.msg,
                              mtype='groupchat')

        self.disconnect(wait=True)


def send_msg(recipient, message, jid=None, password=None, profile=None):
    '''
    Send a message to an XMPP recipient. Designed for use in states.

    CLI Examples:

    .. code-block:: bash

        xmpp.send_msg 'admins@xmpp.example.com' 'This is a salt module test' \
            profile='my-xmpp-account'
        xmpp.send_msg 'admins@xmpp.example.com' 'This is a salt module test' \
            jid='myuser@xmpp.example.com/salt' password='verybadpass'
    '''
    if profile:
        creds = __salt__['config.option'](profile)
        jid = creds.get('xmpp.jid')
        password = creds.get('xmpp.password')

    xmpp = SendMsgBot(jid, password, recipient, message)
    xmpp.register_plugin('xep_0030')  # Service Discovery
    xmpp.register_plugin('xep_0199')  # XMPP Ping

    if xmpp.connect():
        xmpp.process(block=True)
        return True
    return False


def send_msg_multi(message,
                   recipients=None,
                   rooms=None,
                   jid=None,
                   password=None,
                   nick="SaltStack Bot",
                   profile=None):
    '''
    Send a message to an XMPP recipient, support send message to
    multiple recipients or chat room.

    CLI Examples:

    .. code-block:: bash

        xmpp.send_msg recipients=['admins@xmpp.example.com'] \
            rooms=['secret@conference.xmpp.example.com'] \
            'This is a salt module test' \
            profile='my-xmpp-account'
        xmpp.send_msg recipients=['admins@xmpp.example.com'] \
            rooms=['secret@conference.xmpp.example.com'] \
           'This is a salt module test' \
            jid='myuser@xmpp.example.com/salt' password='verybadpass'

    '''

    # Remove: [WARNING ] Use of send mask waiters is deprecated.
    for handler in logging.root.handlers:
        handler.addFilter(SleekXMPPMUC())

    if profile:
        creds = __salt__['config.option'](profile)
        jid = creds.get('xmpp.jid')
        password = creds.get('xmpp.password')

    xmpp = SendMsgBot.create_multi(
        jid, password, message, recipients=recipients, rooms=rooms, nick=nick)

    if rooms:
        xmpp.register_plugin('xep_0045')  # MUC plugin
    if xmpp.connect():
        try:
            xmpp.process(block=True)
            return True
        except XMPPError as err:
            log.error("Could not send message, error: %s", err)
    else:
        log.error("Could not connect to XMPP server")
    return False
