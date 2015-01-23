# -*- coding: utf-8 -*-
'''
Sending Messages via SMTP
==========================

.. versionadded:: 2014.7.0

This state is useful for firing messages during state runs, using the SMTP
protocol

.. code-block:: yaml

    server-warning-message:
      smtp.send_msg:
        - name: 'This is a server warning message'
        - profile: my-smtp-account
        - recipient: admins@example.com
'''


def __virtual__():
    '''
    Only load if the SMTP module is available in __salt__
    '''
    return 'smtp' if 'smtp.send_msg' in __salt__ else False


def send_msg(name, recipient, subject, sender, profile, use_ssl='True'):
    '''
    Send a message via SMTP

    .. code-block:: yaml

        server-warning-message:
          smtp.send_msg:
            - name: 'This is a server warning message'
            - profile: my-smtp-account
            - subject: 'Message from Salt'
            - recipient: admin@example.com
            - sender: admin@example.com
            - use_ssl: True

    name
        The message to send via SMTP
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    if __opts__['test']:
        ret['comment'] = 'Need to send message to {0}: {1}'.format(
            recipient,
            name,
        )
        return ret
    command = __salt__['smtp.send_msg'](
        message=name,
        recipient=recipient,
        profile=profile,
        subject=subject,
        sender=sender,
        use_ssl=use_ssl,
    )

    if command:
        ret['result'] = True
        ret['comment'] = 'Sent message to {0}: {1}'.format(recipient, name)
    else:
        ret['result'] = False
        ret['comment'] = 'Unable to send message to {0}: {1}'.format(recipient, name)
    return ret
