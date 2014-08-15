# -*- coding: utf-8 -*-
'''
Return salt data via xmpp

The following fields can be set in the minion conf file::

    xmpp.host (required)
    xmpp.jid (optional)
    xmpp.password (optional)

There are a few things to keep in mind:

* If a username is used, a password is also required. It is recommended (but
  not required) to use the TLS setting when authenticating.
* You should at least declare a subject, but you don't have to.
* The use of encryption, i.e. setting gpgowner in your settings, requires
  python-gnupg to be installed.
* The field gpgowner specifies a user's ~/.gpg directory. This must contain a
  gpg public key matching the address the mail is sent to. If left unset, no
  encryption will be used.
* smtp.fields lets you include the value(s) of various fields in the subject
  line of the email. These are comma-delimited. For instance::

    smtp.fields: id,fun

  ...will display the id of the minion and the name of the function in the
  subject line. You may also use 'jid' (the job id), but it is generally
  recommended not to use 'return', which contains the entire return data
  structure (which can be very large). Also note that the subject is always
  unencrypted.

  To use the SMTP returner, append '--return smtp' to the salt command. ex:

  .. code-block:: bash

    salt '*' test.ping --return smtp

'''

# Import python libs
import pprint
import logging

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


def returner(ret):
    '''
    Send an xmpp message with the data
    '''

    if 'config.option' in __salt__:
        cfg = __salt__['config.option']
        c_cfg = cfg('xmpp', {})
        from_jid = c_cfg.get('from_jid', cfg('xmpp.jid', None))
        to_jid = c_cfg.get('to_jid', cfg('xmpp.to', None))
        password = c_cfg.get('password', cfg('xmpp.password', None))
    else:
        cfg = __opts__
        from_jid = cfg.get('xmpp.jid', None)
        to_jid = cfg.get('xmpp.to', None)
        password = cfg.get('xmpp.password', None)

    log.debug('cfg {0}'.format(cfg))

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

    xmpp = SendMsgBot(from_jid, str(password), to_jid, message)
    xmpp.register_plugin('xep_0030')  # Service Discovery
    xmpp.register_plugin('xep_0199')  # XMPP Ping

    if xmpp.connect():
        xmpp.process(block=True)
        return True
    return False
