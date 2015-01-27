# -*- coding: utf-8 -*-
'''
Module for Sending Messages via XMPP (a.k.a. Jabber)

.. versionadded:: 2014.1.0

:depends:   - sleekxmpp python module
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

HAS_LIBS = False
try:
    from sleekxmpp import ClientXMPP as _ClientXMPP
    HAS_LIBS = True
except ImportError:
    class _ClientXMPP(object):
        '''
        Fake class in order not to raise errors
        '''


__virtualname__ = 'xmpp'


def __virtual__():
    '''
    Only load this module if sleekxmpp is installed on this minion.
    '''
    if HAS_LIBS:
        return __virtualname__
    return False


class SendMsgBot(_ClientXMPP):

    def __init__(self, jid, password, recipient, msg):  # pylint: disable=E1002
        # PyLint wrongly reports an error when calling super, hence the above
        # disable call
        super(SendMsgBot, self).__init__(jid, password)

        self.recipient = recipient
        self.msg = msg

        self.add_event_handler('session_start', self.start)

    def start(self, event):
        self.send_presence()

        self.send_message(mto=self.recipient,
                          mbody=self.msg,
                          mtype='chat')

        self.disconnect(wait=True)


def send_msg(recipient, message, jid=None, password=None, profile=None):
    '''
    Send a message to an XMPP recipient. Designed for use in states.

    CLI Examples::

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
