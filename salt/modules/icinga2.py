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


def generate_ticket(domain):
    """
    Generate and save an icinga2 ticket.

    Returns::
        icinga2 pki ticket --cn domain.tld

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.generate_ticket domain.tld

    """
    result = __salt__["cmd.run_all"](
        ["icinga2", "pki", "ticket", "--cn", domain], python_shell=False
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


def save_cert(domain, master):
    """
    Save the certificate for master icinga2 node.

    Returns::
        icinga2 pki save-cert --key /etc/icinga2/pki/domain.tld.key --cert /etc/icinga2/pki/domain.tld.crt --trustedcert /etc/icinga2/pki/trusted-master.crt --host master.domain.tld

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.save_cert domain.tld master.domain.tld

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
            "{}trusted-master.crt".format(get_certs_path()),
            "--host",
            master,
        ],
        python_shell=False,
    )
    return result


def request_cert(domain, master, ticket, port):
    """
    Request CA cert from master icinga2 node.

    Returns::
        icinga2 pki request --host master.domain.tld --port 5665 --ticket TICKET_ID --key /etc/icinga2/pki/domain.tld.key --cert /etc/icinga2/pki/domain.tld.crt --trustedcert \
                /etc/icinga2/pki/trusted-master.crt --ca /etc/icinga2/pki/ca.crt

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.request_cert domain.tld master.domain.tld TICKET_ID

    """
    result = __salt__["cmd.run_all"](
        [
            "icinga2",
            "pki",
            "request",
            "--host",
            master,
            "--port",
            port,
            "--ticket",
            ticket,
            "--key",
            "{}{}.key".format(get_certs_path(), domain),
            "--cert",
            "{}{}.crt".format(get_certs_path(), domain),
            "--trustedcert",
            "{}trusted-master.crt".format(get_certs_path()),
            "--ca",
            "{}ca.crt".format(get_certs_path()),
        ],
        python_shell=False,
    )
    return result


def node_setup(domain, master, ticket):
    """
    Setup the icinga2 node.

    Returns::
        icinga2 node setup --ticket TICKET_ID --endpoint master.domain.tld --zone domain.tld --master_host master.domain.tld --trustedcert \
                /etc/icinga2/pki/trusted-master.crt

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.node_setup domain.tld master.domain.tld TICKET_ID

    """
    result = __salt__["cmd.run_all"](
        [
            "icinga2",
            "node",
            "setup",
            "--ticket",
            ticket,
            "--endpoint",
            master,
            "--zone",
            domain,
            "--master_host",
            master,
            "--trustedcert",
            "{}trusted-master.crt".format(get_certs_path()),
        ],
        python_shell=False,
    )
    return result
