# -*- coding: utf-8 -*-
'''
Return salt data via xmpp

The following fields can be set in the minion conf file::

    xmpp.jid (required)
    xmpp.password (required)
    xmpp.recipient (required)

  To use the XMPP returner, append '--return xmpp' to the salt command. ex:

  .. code-block:: bash

    salt '*' test.ping --return xmpp

'''

# Import python libs
import distutils.version
import logging
import pprint

log = logging.getLogger(__name__)

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
    Only load this module if right version of sleekxmpp is installed on this minion.
    '''
    if HAS_LIBS:
        import sleekxmpp
        # Certain XMPP functionaility we're using doesn't work with versions under 1.3.1
        sleekxmpp_version = distutils.version.LooseVersion(sleekxmpp.__version__)
        valid_version = distutils.version.LooseVersion('1.3.1')
        if sleekxmpp_version >= valid_version:
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


def returner(ret):
    '''
    Send an xmpp message with the data
    '''

    if 'config.option' in __salt__:
        cfg = __salt__['config.option']
        c_cfg = cfg('xmpp', {})
        xmpp_profile = c_cfg.get('xmpp_profile', cfg('xmpp.profile', None))
        if xmpp_profile:
            creds = __salt__['config.option'](xmpp_profile)
            from_jid = creds.get('xmpp.jid')
            password = creds.get('xmpp.password')
        else:
            from_jid = c_cfg.get('from_jid', cfg('xmpp.jid', None))
            password = c_cfg.get('password', cfg('xmpp.password', None))
        recipient_jid = c_cfg.get('recipient_jid', cfg('xmpp.recipient', None))
    else:
        cfg = __opts__
        xmpp_profile = cfg.get('xmpp.profile', None)
        if xmpp_profile:
            creds = cfg.get(xmpp_profile)
            from_jid = creds.get('xmpp.jid', None)
            password = creds.get('xmpp.password', None)
        else:
            from_jid = cfg.get('xmpp.jid', None)
            password = cfg.get('xmpp.password', None)
        recipient_jid = cfg.get('xmpp.recipient', None)

    if not from_jid:
        log.error('xmpp.jid not defined in salt config')
        return

    if not password:
        log.error('xmpp.password not defined in salt config')
        return

    if not recipient_jid:
        log.error('xmpp.recipient not defined in salt config')
        return

    message = ('id: {0}\r\n'
               'function: {1}\r\n'
               'function args: {2}\r\n'
               'jid: {3}\r\n'
               'return: {4}\r\n').format(
                    ret.get('id'),
                    ret.get('fun'),
                    ret.get('fun_args'),
                    ret.get('jid'),
                    pprint.pformat(ret.get('return')))

    xmpp = SendMsgBot(from_jid, password, recipient_jid, message)
    xmpp.register_plugin('xep_0030')  # Service Discovery
    xmpp.register_plugin('xep_0199')  # XMPP Ping

    if xmpp.connect():
        xmpp.process(block=True)
        return True
    return False
