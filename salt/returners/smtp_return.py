# -*- coding: utf-8 -*-
'''
Return salt data via email

The following fields can be set in the minion conf file:

    smtp.from (required)
    smtp.to (required)
    smtp.host (required)
    smtp.username (optional)
    smtp.password (optional)
    smtp.tls (optional, defaults to False)
    smtp.subject (optional, but helpful)
    smtp.fields (optional)

There are a few things to keep in mind:

* If a username is used, a password is also required.
* You should at least declare a subject, but you don't have to.
* smtp.fields lets you include the value(s) of various fields in the subject
  line of the email. These are comma-delimited. For instance:

    smtp.fields: id,fun

  ...will display the id of the minion and the name of the function in the
  subject line. You may also use 'jid' (the job id), but it is generally
  recommended not to use 'return', which contains the entire return data
  structure (which can be very large).
'''

# Import python libs
import pprint
import logging
import smtplib
from email.utils import formatdate

log = logging.getLogger(__name__)


def __virtual__():
    return 'smtp_return'


def returner(ret):
    '''
    Send an email with the data
    '''

    from_addr = __salt__['config.option']('smtp.from')
    to_addrs = __salt__['config.option']('smtp.to')
    host = __salt__['config.option']('smtp.host')
    user = __salt__['config.option']('smtp.username')
    passwd = __salt__['config.option']('smtp.password')
    subject = __salt__['config.option']('smtp.subject')

    fields = __salt__['config.option']('smtp.fields').split(',')
    for field in fields:
        if field in ret.keys():
            subject += ' {0}'.format(ret[field])
    log.debug('subject')

    content = pprint.pformat(ret['return'])
    message = ('From: {0}\r\n'
               'To: {1}\r\n'
               'Date: {2}\r\n'
               'Subject: {3}\r\n'
               '\r\n'
               'id: {4}\r\n'
               'function: {5}\r\n'
               'jid: {6}\r\n'
               '{7}').format(from_addr,
                             to_addrs,
                             formatdate(localtime=True),
                             subject,
                             ret['id'],
                             ret['fun'],
                             ret['jid'],
                             content)

    server = smtplib.SMTP(host)
    if __salt__['config.option']('smtp.tls') is True:
        server.starttls()
    if user and passwd:
        server.login(user, passwd)
    server.sendmail(from_addr, to_addrs, message)
    server.quit()
