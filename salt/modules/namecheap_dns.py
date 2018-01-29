# -*- coding: utf-8 -*-
'''
Namecheap dns management

.. versionadded:: 2017.7.0

 General Notes
 -------------

 Use this module to manage dns through the namecheap
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

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
from salt.ext import six

CAN_USE_NAMECHEAP = True


try:
    import salt.utils.namecheap
except ImportError:
    CAN_USE_NAMECHEAP = False

__virtualname__ = 'namecheap_domains_dns'


def __virtual__():
    '''
    Check to make sure requests and xml are installed and requests
    '''
    if CAN_USE_NAMECHEAP:
        return 'namecheap_domains_dns'
    return False


def get_hosts(sld, tld):
    '''
    Retrieves DNS host record settings for the requested domain.

    returns a dictionary of information about the requested domain

    sld
        string  sld of the domainname

    tld
        string  tld of the domainname

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_domains_dns.get_hosts sld tld
    '''
    opts = salt.utils.namecheap.get_opts('namecheap.domains.dns.gethosts')
    opts['TLD'] = tld
    opts['SLD'] = sld

    response_xml = salt.utils.namecheap.get_request(opts)
    if response_xml is None:
        return {}

    domaindnsgethostsresult = response_xml.getElementsByTagName('DomainDNSGetHostsResult')[0]

    return salt.utils.namecheap.xml_to_dict(domaindnsgethostsresult)


def get_list(sld, tld):
    '''
    Gets a list of DNS servers associated with the requested domain.

    returns a dictionary of information about requested domain

    sld
        string  sld of the domainname

    tld
        string  tld of the domain name

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_domains_dns.get_list sld tld
    '''
    opts = salt.utils.namecheap.get_opts('namecheap.domains.dns.getlist')
    opts['TLD'] = tld
    opts['SLD'] = sld

    response_xml = salt.utils.namecheap.get_request(opts)
    if response_xml is None:
        return {}

    domaindnsgetlistresult = response_xml.getElementsByTagName('DomainDNSGetListResult')[0]

    return salt.utils.namecheap.xml_to_dict(domaindnsgetlistresult)


def set_hosts(sld, tld, hosts):
    '''
    Sets DNS host records settings for the requested domain.

    returns True if the host records were set successfully

    sld
        string  sld of the domainname

    tld
        string  tld of the domain name

    hosts
        array of dictionaries  each dictionary should contain the following keys:
                               'hostname', 'recordtype', and 'address'
                               'ttl' is optional, Default value is 1800
                               'mxpref' is optional but must be included with 'emailtype'

                               'hostname' should be the subdomain/hostname
                               'recordtype' should be A,AAAA,CNAME,MX,MXE,TXT,URL,URL301,FRAME
                               'address' should be url or ip address
                               'ttl' should be an integer between 60 to 60000

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_domains_dns.set_hosts sld tld hosts
    '''
    opts = salt.utils.namecheap.get_opts('namecheap.domains.dns.setHosts')
    opts['SLD'] = sld
    opts['TLD'] = tld
    i = 1
    for hostrecord in hosts:
        str_i = six.text_type(i)
        opts['HostName' + str_i] = hostrecord['hostname']
        opts['RecordType' + str_i] = hostrecord['recordtype']
        opts['Address' + str_i] = hostrecord['address']
        if 'ttl' in hostrecord:
            opts['TTL' + str_i] = hostrecord['ttl']
        if 'mxpref' in hostrecord:
            opts['MXPref' + str_i] = hostrecord['mxpref']
            opts['EmailType'] = hostrecord['emailtype']
        i += 1

    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return False

    dnsresult = response_xml.getElementsByTagName('DomainDNSSetHostsResult')[0]
    return salt.utils.namecheap.string_to_value(dnsresult.getAttribute('IsSuccess'))


def set_custom(sld, tld, nameservers):
    '''
    Sets domain to use custom DNS servers.

    returns True if the custom nameservers were set successfully

    sld
        string  sld of the domainname

    tld
        string  tld of the domain name

    nameservers
        array of strings  List of nameservers to be associated with this domain

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_domains_dns.set_custom sld tld nameserver
    '''
    opts = salt.utils.namecheap.get_opts('namecheap.domains.dns.setCustom')
    opts['SLD'] = sld
    opts['TLD'] = tld
    opts['Nameservers'] = ','.join(nameservers)
    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return False

    dnsresult = response_xml.getElementsByTagName('DomainDNSSetCustomResult')[0]
    return salt.utils.namecheap.string_to_value(dnsresult.getAttribute('Update'))


def set_default(sld, tld):
    '''
    Sets domain to use namecheap default DNS servers.
    Required for free services like Host record management,
    URL forwarding, email forwarding, dynamic dns and other value added services.

    returns True if the domain was set to default

    sld
        string  sld of the domainname

    tld
        string  tld of the domain name

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_domains_dns.set_default sld tld
    '''
    opts = salt.utils.namecheap.get_opts('namecheap.domains.dns.setDefault')
    opts['SLD'] = sld
    opts['TLD'] = tld
    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return False

    dnsresult = response_xml.getElementsByTagName('DomainDNSSetDefaultResult')[0]
    return salt.utils.namecheap.string_to_value(dnsresult.getAttribute('Updated'))
