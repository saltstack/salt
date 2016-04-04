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
    smtp.template (optional)
    smtp.renderer (optional)

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location::

    alternative.smtp.from
    alternative.smtp.to
    alternative.smtp.host
    alternative.smtp.port
    alternative.smtp.username
    alternative.smtp.password
    alternative.smtp.tls
    alternative.smtp.subject
    alternative.smtp.gpgowner
    alternative.smtp.fields
    alternative.smtp.template
    alternative.smtp.renderer

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

To use the SMTP returner, append '--return smtp' to the salt command.

.. code-block:: bash

    salt '*' test.ping --return smtp

To use the alternative configuration, append '--return_config alternative' to the salt command.

.. versionadded:: 2015.5.0

.. code-block:: bash

    salt '*' test.ping --return smtp --return_config alternative

To override individual configuration items, append --return_kwargs '{"key:": "value"}' to the salt command.

.. versionadded:: 2016.3.0

.. code-block:: bash

    salt '*' test.ping --return smtp --return_kwargs '{"to": "user@domain.com"}'

'''
from __future__ import absolute_import

# Import python libs
import os
import logging
import smtplib
from email.utils import formatdate

# Import Salt libs
import salt.utils.jid
import salt.returners
import salt.loader
from salt.template import compile_template

try:
    import gnupg
    HAS_GNUPG = True
except ImportError:
    HAS_GNUPG = False


log = logging.getLogger(__name__)

__virtualname__ = 'smtp'


def __virtual__():
    return __virtualname__


def _get_options(ret=None):
    '''
    Get the SMTP options from salt.
    '''
    attrs = {'from': 'from',
             'to': 'to',
             'host': 'host',
             'username': 'username',
             'password': 'password',
             'subject': 'subject',
             'gpgowner': 'gpgowner',
             'fields': 'fields',
             'tls': 'tls',
             'renderer': 'renderer',
             'template': 'template'}

    _options = salt.returners.get_returner_options(__virtualname__,
                                                   ret,
                                                   attrs,
                                                   __salt__=__salt__,
                                                   __opts__=__opts__)
    return _options


def returner(ret):
    '''
    Send an email with the data
    '''

    _options = _get_options(ret)
    from_addr = _options.get('from')
    to_addrs = _options.get('to')
    host = _options.get('host')
    port = _options.get('port')
    user = _options.get('username')
    passwd = _options.get('password')
    subject = _options.get('subject')
    gpgowner = _options.get('gpgowner')
    fields = _options.get('fields').split(',') if 'fields' in _options else []
    smtp_tls = _options.get('tls')

    renderer = _options.get('renderer', __opts__.get('renderer', 'yaml_jinja'))
    rend = salt.loader.render(__opts__, {})

    if not port:
        port = 25
    log.debug('SMTP port has been set to {0}'.format(port))
    for field in fields:
        if field in ret:
            subject += ' {0}'.format(ret[field])
    subject = compile_template(':string:', rend, renderer, input_data=subject, **ret)
    log.debug("smtp_return: Subject is '{0}'".format(subject))

    template = _options.get('template')
    if template:
        content = compile_template(template, rend, renderer, **ret)
    else:
        template = ('id: {{id}}\r\n'
                    'function: {{fun}}\r\n'
                    'function args: {{fun_args}}\r\n'
                    'jid: {{jid}}\r\n'
                    'return: {{return}}\r\n')
        content = compile_template(':string:', rend, renderer, input_data=template, **ret)

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
    server.set_debuglevel = 'debug'
    if smtp_tls is True:
        server.starttls()
        log.debug('smtp_return: TLS enabled')
    if user and passwd:
        server.login(user, passwd)
        log.debug('smtp_return: Authenticated')
    server.sendmail(from_addr, to_addrs, message)
    log.debug('smtp_return: Message sent.')
    server.quit()


def prep_jid(nocache=False, passed_jid=None):  # pylint: disable=unused-argument
    '''
    Do any work necessary to prepare a JID, including sending a custom id
    '''
    return passed_jid if passed_jid is not None else salt.utils.jid.gen_jid()
