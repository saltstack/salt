# -*- coding: utf-8 -*-
'''
Namecheap nameservers management

.. versionadded:: 2017.7.0

 General Notes
 -------------

 Use this module to manage nameservers through the namecheap
 api.  The Namecheap settings will be set in grains.

 Installation Prerequisites
 --------------------------

 - This module uses the following python libraries to communicate to
   the namecheap API:

        * ``requests``

        .. code-block:: bash

            pip install requests

 - As saltstack depends on ``requests`` this shouldn't be a problem

 Prerequisite Configuration
 --------------------------

 - The namecheap username, api key and url should be set in a minion
   configuration file or pillar

   .. code-block:: yaml

        namecheap.name: companyname
        namecheap.key: a1b2c3d4e5f67a8b9c0d1e2f3
        namecheap.client_ip: 162.155.30.172
        #Real url
        namecheap.url: https://api.namecheap.com/xml.response
        #Sandbox url
        #namecheap.url: https://api.sandbox.namecheap.xml.response

'''
from __future__ import absolute_import, print_function, unicode_literals

CAN_USE_NAMECHEAP = True


try:
    import salt.utils.namecheap
except ImportError:
    CAN_USE_NAMECHEAP = False


__virtualname__ = 'namecheap_domains_ns'


def __virtual__():
    '''
    Check to make sure requests and xml are installed and requests
    '''
    if CAN_USE_NAMECHEAP:
        return 'namecheap_domains_ns'
    return False


def get_info(sld, tld, nameserver):
    '''
    Retrieves information about a registered nameserver

    returns the following information in a dictionary
        ipaddress set for the nameserver
        domain name for which you are trying to get nameserver details
        status an array of status about the nameservers

    sld
        string  SLD of the DomainName

    tld
        string  TLD of the DomainName

    nameserver
        string  Nameserver to retrieve

    CLI Example:

    .. code-block:: bash

        salt '*' namecheap_domains_ns.get_info sld tld nameserver
    '''
    opts = salt.utils.namecheap.get_opts('namecheap.domains.ns.delete')
    opts['SLD'] = sld
    opts['TLD'] = tld
    opts['Nameserver'] = nameserver

    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return {}

    domainnsinforesult = response_xml.getElementsByTagName('DomainNSInfoResult')[0]

    return salt.utils.namecheap.xml_to_dict(domainnsinforesult)


def update(sld, tld, nameserver, old_ip, new_ip):
    '''
    Deletes a nameserver

    returns True if the nameserver was updated successfully

    sld
        string  SLD of the DomainName

    tld
        string  TLD of the DomainName

    nameserver
        string  Nameserver to create

    old_ip
        string  existing ip address

    new_ip
        string  new ip address

    CLI Example:

    .. code-block:: bash

        salt '*' namecheap_domains_ns.update sld tld nameserver old_ip new_ip
    '''
    opts = salt.utils.namecheap.get_opts('namecheap.domains.ns.update')
    opts['SLD'] = sld
    opts['TLD'] = tld
    opts['Nameserver'] = nameserver
    opts['OldIP'] = old_ip
    opts['IP'] = new_ip

    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return False

    domainnsupdateresult = response_xml.getElementsByTagName('DomainNSUpdateResult')[0]
    return salt.utils.namecheap.string_to_value(domainnsupdateresult.getAttribute('IsSuccess'))


def delete(sld, tld, nameserver):
    '''
    Deletes a nameserver

    returns True if the nameserver was deleted successfully

    sld
        string  SLD of the DomainName

    tld
        string  TLD of the DomainName

    nameserver
        string  Nameserver to create

    CLI Example:

    .. code-block:: bash

        salt '*' namecheap_domains_ns.delete sld tld nameserver
    '''
    opts = salt.utils.namecheap.get_opts('namecheap.domains.ns.delete')
    opts['SLD'] = sld
    opts['TLD'] = tld
    opts['Nameserver'] = nameserver

    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return False

    domainnsdeleteresult = response_xml.getElementsByTagName('DomainNSDeleteResult')[0]
    return salt.utils.namecheap.string_to_value(domainnsdeleteresult.getAttribute('IsSuccess'))


def create(sld, tld, nameserver, ip):
    '''
    Creates a new nameserver

    returns True if the nameserver was created successfully

    sld
        string  SLD of the DomainName

    tld
        string  TLD of the DomainName

    nameserver
        string  Nameserver to create

    ip
        string  Nameserver IP address

    CLI Example:

    .. code-block:: bash

        salt '*' namecheap_domains_ns.create sld tld nameserver ip
    '''

    opts = salt.utils.namecheap.get_opts('namecheap.domains.ns.create')
    opts['SLD'] = sld
    opts['TLD'] = tld
    opts['Nameserver'] = nameserver
    opts['IP'] = ip

    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return False

    domainnscreateresult = response_xml.getElementsByTagName('DomainNSCreateResult')[0]
    return salt.utils.namecheap.string_to_value(domainnscreateresult.getAttribute('IsSuccess'))
