# -*- coding: utf-8 -*-
'''
Return salt data via email

The following fields can be set in the minion conf file::

    smtp.from (required)
    smtp.to (required)
    smtp.host (required)
    smtp.port (optional, defaults to 25)
    smtp.username (optional)
    smtp.password (optional)
    smtp.tls (optional, defaults to False)
    smtp.subject (optional, but helpful)
    smtp.gpgowner (optional)
    smtp.fields (optional)

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
import os
import pprint
import logging
import smtplib
from email.utils import formatdate

# Import Salt libs
import salt.utils

try:
    import gnupg
    HAS_GNUPG = True
except ImportError:
    HAS_GNUPG = False


log = logging.getLogger(__name__)

__virtualname__ = 'smtp'


def __virtual__():
    return __virtualname__


def returner(ret):
    '''
    Send an email with the data
    '''

    if 'config.option' in __salt__:
        from_addr = __salt__['config.option']('smtp.from')
        to_addrs = __salt__['config.option']('smtp.to')
        host = __salt__['config.option']('smtp.host')
        port = __salt__['config.option']('smtp.port')
        user = __salt__['config.option']('smtp.username')
        passwd = __salt__['config.option']('smtp.password')
        subject = __salt__['config.option']('smtp.subject')
        gpgowner = __salt__['config.option']('smtp.gpgowner')
        fields = __salt__['config.option']('smtp.fields').split(',')
        smtp_tls = __salt__['config.option']('smtp.tls')
    else:
        cfg = __opts__
        from_addr = cfg.get('smtp.from', None)
        to_addrs = cfg.get('smtp.to', None)
        host = cfg.get('smtp.host', None)
        port = cfg.get('smtp.port', None)
        user = cfg.get('smtp.username', None)
        passwd = cfg.get('smtp.password', None)
        subject = cfg.get('smtp.subject', None)
        gpgowner = cfg.get('smtp.gpgowner', None)
        fields = cfg.get('smtp.fields', '').split(',')
        smtp_tls = cfg.get('smtp.tls', False)

    if not port:
        port = 25
    log.debug('SMTP port has been set to {0}'.format(port))
    for field in fields:
        if field in ret:
            subject += ' {0}'.format(ret[field])
    log.debug("smtp_return: Subject is '{0}'".format(subject))

    content = ('id: {0}\r\n'
               'function: {1}\r\n'
               'function args: {2}\r\n'
               'jid: {3}\r\n'
               'return: {4}\r\n').format(
                    ret.get('id'),
                    ret.get('fun'),
                    ret.get('fun_args'),
                    ret.get('jid'),
                    pprint.pformat(ret.get('return')))
    if HAS_GNUPG and gpgowner:
        gpg = gnupg.GPG(gnupghome=os.path.expanduser('~{0}/.gnupg'.format(gpgowner)),
                        options=['--trust-model always'])
        encrypted_data = gpg.encrypt(content, to_addrs)
        if encrypted_data.ok:
            log.debug('smtp_return: Encryption successful')
            content = str(encrypted_data)
        else:
            log.error('smtp_return: Encryption failed, only an error message will be sent')
            content = 'Encryption failed, the return data was not sent.\r\n\r\n{0}\r\n{1}'.format(
                    encrypted_data.status, encrypted_data.stderr)

    message = ('From: {0}\r\n'
               'To: {1}\r\n'
               'Date: {2}\r\n'
               'Subject: {3}\r\n'
               '\r\n'
               '{4}').format(from_addr,
                             to_addrs,
                             formatdate(localtime=True),
                             subject,
                             content)

    log.debug('smtp_return: Connecting to the server...')
    server = smtplib.SMTP(host, int(port))
    if smtp_tls is True:
        server.starttls()
        log.debug('smtp_return: TLS enabled')
    if user and passwd:
        server.login(user, passwd)
        log.debug('smtp_return: Authenticated')
    server.sendmail(from_addr, to_addrs, message)
    log.debug('smtp_return: Message sent.')
    server.quit()


def prep_jid(nocache, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.gen_jid()
