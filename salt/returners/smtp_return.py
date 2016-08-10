# -*- coding: utf-8 -*-
'''
Return salt data via email

The following fields can be set in the minion conf file. Fields are optional
unless noted otherwise.

* ``from`` (required) The name/address of the email sender.
* ``to`` (required) The name/address of the email recipient.
* ``host`` (required) The SMTP server hostname or address.
* ``port`` The SMTP server port; defaults to ``25``.
* ``username`` The username used to authenticate to the server. If specified a
    password is also required. It is recommended but not required to also use
    TLS with this option.
* ``password`` The password used to authenticate to the server.
* ``tls`` Whether to secure the connection using TLS; defaults to ``False``
* ``subject`` The email subject line.
* ``fields`` Which fields from the returned data to include in the subject line
    of the email; comma-delimited. For example: ``id,fun``. Please note, *the
    subject line is not encrypted*.
* ``gpgowner`` A user's :file:`~/.gpg` directory. This must contain a gpg
    public key matching the address the mail is sent to. If left unset, no
    encryption will be used. Requires :program:`python-gnupg` to be installed.
* ``template`` The path to a file to be used as a template for the email body.
* ``renderer`` A Salt renderer, or render-pipe, to use to render the email
    template. Default ``jinja``.

Below is an example of the above settings in a Salt Minion configuration file:

.. code-block:: yaml

    smtp.from: me@example.net
    smtp.to: you@example.com
    smtp.host: localhost
    smtp.port: 1025

Alternative configuration values can be used by prefacing the configuration.
Any values not found in the alternative configuration will be pulled from
the default location. For example:

.. code-block:: yaml

    alternative.smtp.username: saltdev
    alternative.smtp.password: saltdev
    alternative.smtp.tls: True

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

An easy way to test the SMTP returner is to use the development SMTP server
built into Python. The command below will start a single-threaded SMTP server
that prints any email it receives to the console.

.. code-block:: python

    python -m smtpd -n -c DebuggingServer localhost:1025
'''
from __future__ import absolute_import

# Import python libs
import os
import logging
import smtplib
import StringIO
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
             'port': 'port',
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
    subject = _options.get('subject') or 'Email from Salt'
    gpgowner = _options.get('gpgowner')
    fields = _options.get('fields').split(',') if 'fields' in _options else []
    smtp_tls = _options.get('tls')

    renderer = _options.get('renderer') or 'jinja'
    rend = salt.loader.render(__opts__, {})

    if not port:
        port = 25
    log.debug('SMTP port has been set to {0}'.format(port))
    for field in fields:
        if field in ret:
            subject += ' {0}'.format(ret[field])
    subject = compile_template(':string:', rend, renderer, input_data=subject, **ret)
    if isinstance(subject, StringIO.StringIO):
        subject = subject.read()

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

    if isinstance(content, StringIO.StringIO):
        content = content.read()

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
