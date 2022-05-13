"""
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
"""


def __virtual__():
    """
    Only load if the SMTP module is available in __salt__
    """
    if "smtp.send_msg" in __salt__:
        return "smtp"
    return (False, "smtp module could not be loaded")


def send_msg(
    name,
    recipient,
    subject,
    sender=None,
    profile=None,
    use_ssl="True",
    attachments=None,
):
    """
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
            - attachments:
                - /var/log/syslog
                - /var/log/messages

    name
        The message to send via SMTP
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}

    if profile is None and sender is None:
        ret["result"] = False
        ret["comment"] = "Missing parameter sender or profile for state smtp.send_msg"
        return ret

    if __opts__["test"]:
        ret["comment"] = "Need to send message to {}: {}".format(
            recipient,
            name,
        )
        return ret
    command = __salt__["smtp.send_msg"](
        message=name,
        recipient=recipient,
        profile=profile,
        subject=subject,
        sender=sender,
        use_ssl=use_ssl,
        attachments=attachments,
    )

    if command:
        ret["result"] = True
        if attachments:
            atts = ", ".join(attachments)
            ret["comment"] = "Sent message to {0} with attachments ({2}): {1}".format(
                recipient, name, atts
            )
        else:
            ret["comment"] = "Sent message to {}: {}".format(recipient, name)
    else:
        ret["result"] = False
        ret["comment"] = "Unable to send message to {}: {}".format(recipient, name)
    return ret
