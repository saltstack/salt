"""
Namecheap Nameserver Management

.. versionadded:: 2017.7.0

Prerequisites
-------------

This module uses the ``requests`` Python module to communicate to the namecheap
API.

Configuration
-------------

The Namecheap username, API key and URL should be set in the minion configuration
file, or in the Pillar data.

.. code-block:: yaml

    namecheap.name: companyname
    namecheap.key: a1b2c3d4e5f67a8b9c0d1e2f3
    namecheap.client_ip: 162.155.30.172
    #Real url
    namecheap.url: https://api.namecheap.com/xml.response
    #Sandbox url
    #namecheap.url: https://api.sandbox.namecheap.xml.response
"""

CAN_USE_NAMECHEAP = True


try:
    import salt.utils.namecheap
except ImportError:
    CAN_USE_NAMECHEAP = False


__virtualname__ = "namecheap_domains_ns"


def __virtual__():
    """
    Check to make sure requests and xml are installed and requests
    """
    if CAN_USE_NAMECHEAP:
        return "namecheap_domains_ns"
    return False


def get_info(sld, tld, nameserver):
    """
    Retrieves information about a registered nameserver. Returns the following
    information:

    - IP Address set for the nameserver
    - Domain name which was queried
    - A list of nameservers and their statuses

    sld
        SLD of the domain name

    tld
        TLD of the domain name

    nameserver
        Nameserver to retrieve

    CLI Example:

    .. code-block:: bash

        salt '*' namecheap_domains_ns.get_info sld tld nameserver
    """
    opts = salt.utils.namecheap.get_opts("namecheap.domains.ns.delete")
    opts["SLD"] = sld
    opts["TLD"] = tld
    opts["Nameserver"] = nameserver

    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return {}

    domainnsinforesult = response_xml.getElementsByTagName("DomainNSInfoResult")[0]

    return salt.utils.namecheap.xml_to_dict(domainnsinforesult)


def update(sld, tld, nameserver, old_ip, new_ip):
    """
    Deletes a nameserver. Returns ``True`` if the nameserver was updated
    successfully.

    sld
        SLD of the domain name

    tld
        TLD of the domain name

    nameserver
        Nameserver to create

    old_ip
        Current ip address

    new_ip
        New ip address

    CLI Example:

    .. code-block:: bash

        salt '*' namecheap_domains_ns.update sld tld nameserver old_ip new_ip
    """
    opts = salt.utils.namecheap.get_opts("namecheap.domains.ns.update")
    opts["SLD"] = sld
    opts["TLD"] = tld
    opts["Nameserver"] = nameserver
    opts["OldIP"] = old_ip
    opts["IP"] = new_ip

    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return False

    domainnsupdateresult = response_xml.getElementsByTagName("DomainNSUpdateResult")[0]
    return salt.utils.namecheap.string_to_value(
        domainnsupdateresult.getAttribute("IsSuccess")
    )


def delete(sld, tld, nameserver):
    """
    Deletes a nameserver. Returns ``True`` if the nameserver was deleted
    successfully

    sld
        SLD of the domain name

    tld
        TLD of the domain name

    nameserver
        Nameserver to delete

    CLI Example:

    .. code-block:: bash

        salt '*' namecheap_domains_ns.delete sld tld nameserver
    """
    opts = salt.utils.namecheap.get_opts("namecheap.domains.ns.delete")
    opts["SLD"] = sld
    opts["TLD"] = tld
    opts["Nameserver"] = nameserver

    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return False

    domainnsdeleteresult = response_xml.getElementsByTagName("DomainNSDeleteResult")[0]
    return salt.utils.namecheap.string_to_value(
        domainnsdeleteresult.getAttribute("IsSuccess")
    )


def create(sld, tld, nameserver, ip):
    """
    Creates a new nameserver. Returns ``True`` if the nameserver was created
    successfully.

    sld
        SLD of the domain name

    tld
        TLD of the domain name

    nameserver
        Nameserver to create

    ip
        Nameserver IP address

    CLI Example:

    .. code-block:: bash

        salt '*' namecheap_domains_ns.create sld tld nameserver ip
    """

    opts = salt.utils.namecheap.get_opts("namecheap.domains.ns.create")
    opts["SLD"] = sld
    opts["TLD"] = tld
    opts["Nameserver"] = nameserver
    opts["IP"] = ip

    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return False

    domainnscreateresult = response_xml.getElementsByTagName("DomainNSCreateResult")[0]
    return salt.utils.namecheap.string_to_value(
        domainnscreateresult.getAttribute("IsSuccess")
    )
