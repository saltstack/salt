# -*- coding: utf-8 -*-
'''
Module to provide icinga2 compatibility to salt.

.. versionadded:: 2017.7.0

:depends:   - icinga2 server
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import subprocess

# Import Salt libs
import salt.utils.path
import salt.utils.platform

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if the mysql libraries exist
    '''
    # TODO: This could work on windows with some love
    if salt.utils.platform.is_windows():
        return (False, 'The module cannot be loaded on windows.')

    if salt.utils.path.which('icinga2'):
        return True
    return (False, 'Icinga2 not installed.')


def _execute(cmd, ret_code=False):
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    if ret_code:
        return process.wait()
    output, error = process.communicate()
    if output:
        log.debug(output)
        return output
    log.debug(error)
    return error


def generate_ticket(domain):
    '''
    Generate and save an icinga2 ticket.

    Returns::
        icinga2 pki ticket --cn domain.tld

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.generate_ticket domain.tld

    '''
    result = _execute(["icinga2", "pki", "ticket", "--cn", domain])
    return result


def generate_cert(domain):
    '''
    Generate an icinga2 client certificate and key.

    Returns::
        icinga2 pki new-cert --cn domain.tld --key /etc/icinga2/pki/domain.tld.key --cert /etc/icinga2/pki/domain.tld.crt

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.generate_cert domain.tld

    '''
    result = _execute(["icinga2", "pki", "new-cert", "--cn", domain, "--key", "/etc/icinga2/pki/{0}.key".format(domain), "--cert", "/etc/icinga2/pki/{0}.crt".format(domain)], ret_code=True)
    return result


def save_cert(domain, master):
    '''
    Save the certificate for master icinga2 node.

    Returns::
        icinga2 pki save-cert --key /etc/icinga2/pki/domain.tld.key --cert /etc/icinga2/pki/domain.tld.crt --trustedcert /etc/icinga2/pki/trusted-master.crt --host master.domain.tld

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.save_cert domain.tld master.domain.tld

    '''
    result = _execute(["icinga2", "pki", "save-cert", "--key", "/etc/icinga2/pki/{0}.key".format(domain), "--cert", "/etc/icinga2/pki/{0}.cert".format(domain), "--trustedcert",
                       "/etc/icinga2/pki/trusted-master.crt", "--host", master], ret_code=True)
    return result


def request_cert(domain, master, ticket, port):
    '''
    Request CA cert from master icinga2 node.

    Returns::
        icinga2 pki request --host master.domain.tld --port 5665 --ticket TICKET_ID --key /etc/icinga2/pki/domain.tld.key --cert /etc/icinga2/pki/domain.tld.crt --trustedcert \
                /etc/icinga2/pki/trusted-master.crt --ca /etc/icinga2/pki/ca.crt

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.request_cert domain.tld master.domain.tld TICKET_ID

    '''
    result = _execute(["icinga2", "pki", "request", "--host", master, "--port", port, "--ticket", ticket, "--key", "/etc/icinga2/pki/{0}.key".format(domain), "--cert",
                       "/etc/icinga2/pki/{0}.crt".format(domain), "--trustedcert", "/etc/icinga2/pki/trusted-master.crt", "--ca", "/etc/icinga2/pki/ca.crt"], ret_code=True)
    return result


def node_setup(domain, master, ticket):
    '''
    Setup the icinga2 node.

    Returns::
        icinga2 node setup --ticket TICKET_ID --endpoint master.domain.tld --zone domain.tld --master_host master.domain.tld --trustedcert \
                /etc/icinga2/pki/trusted-master.crt

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.node_setup domain.tld master.domain.tld TICKET_ID

    '''
    result = _execute(["icinga2", "node", "setup", "--ticket", ticket, "--endpoint", master, "--zone", domain, "--master_host", master, "--trustedcert", "/etc/icinga2/pki/trusted-master.crt"],
                       ret_code=True)
    return result
