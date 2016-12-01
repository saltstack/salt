# -*- coding: utf-8 -*-
'''
Module to provide icinga2 compatibility to salt.

:depends:   - icinga2 server
'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if the mysql libraries exist
    '''
    # TODO: This could work on windows with some love
    if salt.utils.is_windows():
        return (False, 'The module cannot be loaded on windows.')

    if salt.utils.which('icinga2'):
        return True
    return (False, 'Icinga2 not installed.')


def generate_ticket(domain):
    '''
    Generate and save an icinga2 ticket.

    Returns::
        icinga2 pki ticket --cn domain.tld

    CLI Example:

    .. code-block:: bash

        salt '*' icinga2.generate_ticket domain.tld

    '''
    result = __salt__['cmd.run']("icinga2 pki ticket --cn {0}".format(domain))
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
    result = __salt__['cmd.run']("icinga2 pki new-cert --cn {0} --key /etc/icinga2/pki/{0}.key --cert /etc/icinga2/pki/{0}.crt".format(domain))
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
    result = __salt__['cmd.run']("icinga2 pki save-cert --key /etc/icinga2/pki/{0}.key --cert /etc/icinga2/pki/{0}.cert --trustedcert /etc/icinga2/pki/trusted-master.crt \
                                 --host {1}".format(domain, master))
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
    result = __salt__['cmd.run']("icinga2 pki request --host {0} --port {1} --ticket {2} --key /etc/icinga2/pki/{3}.key --cert \
                       /etc/icinga2/pki/{3}.crt --trustedcert /etc/icinga2/pki/trusted-master.crt --ca /etc/icinga2/pki/ca.crt".format(master, port, ticket, domain))
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
    result = __salt__['cmd.run']("icinga2 node setup --ticket {0} --endpoint {1} --zone {2} --master_host {1} --trustedcert /etc/icinga2/pki/trusted-master.crt".format(ticket, master, domain))
    return result
