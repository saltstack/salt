"""
Return salt data via email

The following fields can be set in the minion conf file:

    smtp.from (required)
    smtp.to (required)
    smtp.host (required)
    smtp.port (optional, defaults to 25)
    smtp.username (optional)
    smtp.password (optional)
    smtp.tls (optional, defaults to False)
    smtp.subject (optional, but helpful)
    smtp.gpgowne' (optional)
    smtp.fields (optional)
    smtp.content (optional)

There are a few things to keep in mind:

* If a username is used, a password is also required. It is recommended (but
  not required) to use the TLS setting when authenticating.
* You should at least declare a subject, but you don't have to.
* The use of encryption, i.e. setting gpgowner in your settings, requires
  python-gnupg to be installed.
* The field gpgowner specifies a user's ~/.gpg directory. This must contain a
  gpg public key matching the address the mail is sent to. If left unset, no
  encryption will be used.
"""

import logging
import os
import smtplib
from email.utils import formatdate

try:
    import gnupg

    HAS_GNUPG = True
except ImportError:
    HAS_GNUPG = False


log = logging.getLogger(__name__)


def send(kwargs, opts):
    """
    Send an email with the data
    """
    opt_keys = (
        "smtp.to",
        "smtp.from",
        "smtp.host",
        "smtp.port",
        "smtp.tls",
        "smtp.username",
        "smtp.password",
        "smtp.subject",
        "smtp.gpgowner",
        "smtp.content",
    )

    config = {}
    for key in opt_keys:
        config[key] = opts.get(key, "")

    config.update(kwargs)

    if not config["smtp.port"]:
        config["smtp.port"] = 25

    log.debug("SMTP port has been set to %s", config["smtp.port"])
    log.debug("smtp_return: Subject is '%s'", config["smtp.subject"])

    if HAS_GNUPG and config["smtp.gpgowner"]:
        gpg = gnupg.GPG(
            gnupghome=os.path.expanduser("~{}/.gnupg".format(config["smtp.gpgowner"])),
            options=["--trust-model always"],
        )
        encrypted_data = gpg.encrypt(config["smtp.content"], config["smtp.to"])
        if encrypted_data.ok:
            log.debug("smtp_return: Encryption successful")
            config["smtp.content"] = str(encrypted_data)
        else:
            log.error("SMTP: Encryption failed, only an error message will be sent")
            config["smtp.content"] = (
                "Encryption failed, the return data was not sent.\r\n\r\n{}\r\n{}".format(
                    encrypted_data.status, encrypted_data.stderr
                )
            )

    message = "From: {}\r\nTo: {}\r\nDate: {}\r\nSubject: {}\r\n\r\n{}".format(
        config["smtp.from"],
        config["smtp.to"],
        formatdate(localtime=True),
        config["smtp.subject"],
        config["smtp.content"],
    )

    log.debug("smtp_return: Connecting to the server...")
    server = smtplib.SMTP(config["smtp.host"], int(config["smtp.port"]))

    if config["smtp.tls"] is True:
        server.starttls()
        log.debug("smtp_return: TLS enabled")

    if config["smtp.username"] and config["smtp.password"]:
        server.login(config["smtp.username"], config["smtp.password"])
        log.debug("smtp_return: Authenticated")

    server.sendmail(config["smtp.from"], config["smtp.to"], message)
    log.debug("smtp_return: Message sent.")
    server.quit()
