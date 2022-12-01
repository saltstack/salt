"""
Module to provide icinga2 compatibility to salt.

.. versionadded:: 2017.7.0

:depends:   - icinga2 server
"""


import logging

import salt.utils.path
import salt.utils.platform
from salt.utils.icinga2 import get_certs_path

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load this module if the mysql libraries exist
    """
    # TODO: This could work on windows with some love
    if salt.utils.platform.is_windows():
        return (False, "The module cannot be loaded on windows.")

    if salt.utils.path.which("icinga2"):
        return True
    return (False, "Icinga2 not installed.")


def generate_ticket(domain, salt):
    """
    Generate and save an icinga2 ticket.

    Returns::
        icinga2 pki ticket --cn domain.tld --salt SHARED_SECRET

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.generate_ticket domain.tld

    """
    result = __salt__["cmd.run_all"](
        ["icinga2", "pki", "ticket", "--cn", domain, "--salt", salt], python_shell=False
    )
    return result


def generate_cert(domain):
    """
    Generate an icinga2 client certificate and key.

    Returns::
        icinga2 pki new-cert --cn domain.tld --key /etc/icinga2/pki/domain.tld.key --cert /etc/icinga2/pki/domain.tld.crt

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.generate_cert domain.tld

    """
    result = __salt__["cmd.run_all"](
        [
            "icinga2",
            "pki",
            "new-cert",
            "--cn",
            domain,
            "--key",
            "{}{}.key".format(get_certs_path(), domain),
            "--cert",
            "{}{}.crt".format(get_certs_path(), domain),
        ],
        python_shell=False,
    )
    return result


def save_cert(domain, parent):
    """
    Save the certificate for parent icinga2 node.

    Returns::
        icinga2 pki save-cert --key /etc/icinga2/pki/domain.tld.key --cert /etc/icinga2/pki/domain.tld.crt --trustedcert /etc/icinga2/pki/trusted-parent.crt --host parent.domain.tld

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.save_cert domain.tld parent.domain.tld

    """
    result = __salt__["cmd.run_all"](
        [
            "icinga2",
            "pki",
            "save-cert",
            "--key",
            "{}{}.key".format(get_certs_path(), domain),
            "--cert",
            "{}{}.cert".format(get_certs_path(), domain),
            "--trustedcert",
            "{}trusted-parent.crt".format(get_certs_path()),
            "--host",
            parent,
        ],
        python_shell=False,
    )
    return result


def request_cert(domain, parent, ticket, port):
    """
    Request CA cert from parent icinga2 node.

    Returns::
        icinga2 pki request --host parent.domain.tld --port 5665 --ticket TICKET_ID --key /etc/icinga2/pki/domain.tld.key --cert /etc/icinga2/pki/domain.tld.crt --trustedcert \
                /etc/icinga2/pki/trusted-parent.crt --ca /etc/icinga2/pki/ca.crt

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.request_cert domain.tld parent.domain.tld TICKET_ID

    """
    result = __salt__["cmd.run_all"](
        [
            "icinga2",
            "pki",
            "request",
            "--host",
            parent,
            "--port",
            port,
            "--ticket",
            ticket,
            "--key",
            "{}{}.key".format(get_certs_path(), domain),
            "--cert",
            "{}{}.crt".format(get_certs_path(), domain),
            "--trustedcert",
            "{}trusted-parent.crt".format(get_certs_path()),
            "--ca",
            "{}ca.crt".format(get_certs_path()),
        ],
        python_shell=False,
    )
    return result


def node_setup(domain, parent, ticket):
    """
    Setup the icinga2 node.

    Returns::
        icinga2 node setup --ticket TICKET_ID --endpoint parent.domain.tld --zone domain.tld --parent_host parent.domain.tld --trustedcert \
                /etc/icinga2/pki/trusted-parent.crt

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.node_setup domain.tld parent.domain.tld TICKET_ID

    """
    result = __salt__["cmd.run_all"](
        [
            "icinga2",
            "node",
            "setup",
            "--ticket",
            ticket,
            "--endpoint",
            parent,
            "--zone",
            domain,
            "--parent_host",
            parent,
            "--trustedcert",
            "{}trusted-parent.crt".format(get_certs_path()),
        ],
        python_shell=False,
    )
    return result
