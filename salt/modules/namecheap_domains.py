# -*- coding: utf-8 -*-
"""
Namecheap Domain Management

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
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import 3rd-party libs
from salt.ext import six

CAN_USE_NAMECHEAP = True

try:
    import salt.utils.namecheap
except ImportError:
    CAN_USE_NAMECHEAP = False


log = logging.getLogger(__name__)


def __virtual__():
    """
    Check to make sure requests and xml are installed and requests
    """
    if CAN_USE_NAMECHEAP:
        return "namecheap_domains"
    return False


def reactivate(domain_name):
    """
    Try to reactivate the expired domain name

    Returns the following information:

    - Whether or not the domain was reactivated successfully
    - The amount charged for reactivation
    - The order ID
    - The transaction ID

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_domains.reactivate my-domain-name
    """
    opts = salt.utils.namecheap.get_opts("namecheap.domains.reactivate")
    opts["DomainName"] = domain_name

    response_xml = salt.utils.namecheap.post_request(opts)

    if response_xml is None:
        return {}

    domainreactivateresult = response_xml.getElementsByTagName(
        "DomainReactivateResult"
    )[0]
    return salt.utils.namecheap.xml_to_dict(domainreactivateresult)


def renew(domain_name, years, promotion_code=None):
    """
    Try to renew the specified expiring domain name for a specified number of years

    domain_name
        The domain name to be renewed

    years
        Number of years to renew

    Returns the following information:

    - Whether or not the domain was renewed successfully
    - The domain ID
    - The order ID
    - The transaction ID
    - The amount charged for renewal

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_domains.renew my-domain-name 5
    """

    opts = salt.utils.namecheap.get_opts("namecheap.domains.renew")
    opts["DomainName"] = domain_name
    opts["Years"] = years
    if promotion_code is not None:
        opts["PromotionCode"] = promotion_code

    response_xml = salt.utils.namecheap.post_request(opts)

    if response_xml is None:
        return {}

    domainrenewresult = response_xml.getElementsByTagName("DomainRenewResult")[0]
    return salt.utils.namecheap.xml_to_dict(domainrenewresult)


def create(domain_name, years, **kwargs):
    """
    Try to register the specified domain name

    domain_name
        The domain name to be registered

    years
        Number of years to register

    Returns the following information:

    - Whether or not the domain was renewed successfully
    - Whether or not WhoisGuard is enabled
    - Whether or not registration is instant
    - The amount charged for registration
    - The domain ID
    - The order ID
    - The transaction ID

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_domains.create my-domain-name 2
    """
    idn_codes = (
        "afr",
        "alb",
        "ara",
        "arg",
        "arm",
        "asm",
        "ast",
        "ave",
        "awa",
        "aze",
        "bak",
        "bal",
        "ban",
        "baq",
        "bas",
        "bel",
        "ben",
        "bho",
        "bos",
        "bul",
        "bur",
        "car",
        "cat",
        "che",
        "chi",
        "chv",
        "cop",
        "cos",
        "cze",
        "dan",
        "div",
        "doi",
        "dut",
        "eng",
        "est",
        "fao",
        "fij",
        "fin",
        "fre",
        "fry",
        "geo",
        "ger",
        "gla",
        "gle",
        "gon",
        "gre",
        "guj",
        "heb",
        "hin",
        "hun",
        "inc",
        "ind",
        "inh",
        "isl",
        "ita",
        "jav",
        "jpn",
        "kas",
        "kaz",
        "khm",
        "kir",
        "kor",
        "kur",
        "lao",
        "lav",
        "lit",
        "ltz",
        "mal",
        "mkd",
        "mlt",
        "mol",
        "mon",
        "mri",
        "msa",
        "nep",
        "nor",
        "ori",
        "oss",
        "pan",
        "per",
        "pol",
        "por",
        "pus",
        "raj",
        "rum",
        "rus",
        "san",
        "scr",
        "sin",
        "slo",
        "slv",
        "smo",
        "snd",
        "som",
        "spa",
        "srd",
        "srp",
        "swa",
        "swe",
        "syr",
        "tam",
        "tel",
        "tgk",
        "tha",
        "tib",
        "tur",
        "ukr",
        "urd",
        "uzb",
        "vie",
        "wel",
        "yid",
    )

    require_opts = [
        "AdminAddress1",
        "AdminCity",
        "AdminCountry",
        "AdminEmailAddress",
        "AdminFirstName",
        "AdminLastName",
        "AdminPhone",
        "AdminPostalCode",
        "AdminStateProvince",
        "AuxBillingAddress1",
        "AuxBillingCity",
        "AuxBillingCountry",
        "AuxBillingEmailAddress",
        "AuxBillingFirstName",
        "AuxBillingLastName",
        "AuxBillingPhone",
        "AuxBillingPostalCode",
        "AuxBillingStateProvince",
        "RegistrantAddress1",
        "RegistrantCity",
        "RegistrantCountry",
        "RegistrantEmailAddress",
        "RegistrantFirstName",
        "RegistrantLastName",
        "RegistrantPhone",
        "RegistrantPostalCode",
        "RegistrantStateProvince",
        "TechAddress1",
        "TechCity",
        "TechCountry",
        "TechEmailAddress",
        "TechFirstName",
        "TechLastName",
        "TechPhone",
        "TechPostalCode",
        "TechStateProvince",
        "Years",
    ]
    opts = salt.utils.namecheap.get_opts("namecheap.domains.create")
    opts["DomainName"] = domain_name
    opts["Years"] = six.text_type(years)

    def add_to_opts(opts_dict, kwargs, value, suffix, prefices):
        for prefix in prefices:
            nextkey = prefix + suffix
            if nextkey not in kwargs:
                opts_dict[nextkey] = value

    for key, value in six.iteritems(kwargs):
        if key.startswith("Registrant"):
            add_to_opts(
                opts,
                kwargs,
                value,
                key[10:],
                ["Tech", "Admin", "AuxBilling", "Billing"],
            )

        if key.startswith("Tech"):
            add_to_opts(
                opts,
                kwargs,
                value,
                key[4:],
                ["Registrant", "Admin", "AuxBilling", "Billing"],
            )

        if key.startswith("Admin"):
            add_to_opts(
                opts,
                kwargs,
                value,
                key[5:],
                ["Registrant", "Tech", "AuxBilling", "Billing"],
            )

        if key.startswith("AuxBilling"):
            add_to_opts(
                opts,
                kwargs,
                value,
                key[10:],
                ["Registrant", "Tech", "Admin", "Billing"],
            )

        if key.startswith("Billing"):
            add_to_opts(
                opts,
                kwargs,
                value,
                key[7:],
                ["Registrant", "Tech", "Admin", "AuxBilling"],
            )

        if key == "IdnCode" and key not in idn_codes:
            log.error("Invalid IdnCode")
            raise Exception("Invalid IdnCode")

        opts[key] = value

    for requiredkey in require_opts:
        if requiredkey not in opts:
            log.error("Missing required parameter '%s'", requiredkey)
            raise Exception("Missing required parameter '" + requiredkey + "'")

    response_xml = salt.utils.namecheap.post_request(opts)

    if response_xml is None:
        return {}

    domainresult = response_xml.getElementsByTagName("DomainCreateResult")[0]
    return salt.utils.namecheap.atts_to_dict(domainresult)


def check(*domains_to_check):
    """
    Checks the availability of domains

    domains_to_check
        array of strings  List of domains to check

    Returns a dictionary mapping the each domain name to a boolean denoting
    whether or not it is available.

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_domains.check domain-to-check
    """
    opts = salt.utils.namecheap.get_opts("namecheap.domains.check")
    opts["DomainList"] = ",".join(domains_to_check)

    response_xml = salt.utils.namecheap.get_request(opts)

    if response_xml is None:
        return {}

    domains_checked = {}
    for result in response_xml.getElementsByTagName("DomainCheckResult"):
        available = result.getAttribute("Available")
        domains_checked[
            result.getAttribute("Domain").lower()
        ] = salt.utils.namecheap.string_to_value(available)

    return domains_checked


def get_info(domain_name):
    """
    Returns information about the requested domain

    returns a dictionary of information about the domain_name

    domain_name
        string  Domain name to get information about

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_domains.get_info my-domain-name
    """
    opts = salt.utils.namecheap.get_opts("namecheap.domains.getinfo")
    opts["DomainName"] = domain_name

    response_xml = salt.utils.namecheap.get_request(opts)

    if response_xml is None:
        return []

    domaingetinforesult = response_xml.getElementsByTagName("DomainGetInfoResult")[0]

    return salt.utils.namecheap.xml_to_dict(domaingetinforesult)


def get_tld_list():
    """
    Returns a list of TLDs as objects

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_domains.get_tld_list
    """

    response_xml = salt.utils.namecheap.get_request(
        salt.utils.namecheap.get_opts("namecheap.domains.gettldlist")
    )

    if response_xml is None:
        return []

    tldresult = response_xml.getElementsByTagName("Tlds")[0]
    tlds = []

    for e in tldresult.getElementsByTagName("Tld"):
        tld = salt.utils.namecheap.atts_to_dict(e)
        tld["data"] = e.firstChild.data
        categories = []
        subcategories = e.getElementsByTagName("Categories")[0]
        for c in subcategories.getElementsByTagName("TldCategory"):
            categories.append(salt.utils.namecheap.atts_to_dict(c))
        tld["categories"] = categories
        tlds.append(tld)

    return tlds


def get_list(list_type=None, search_term=None, page=None, page_size=None, sort_by=None):
    """
    Returns a list of domains for the particular user as a list of objects
    offset by ``page`` length of ``page_size``

    list_type : ALL
        One of ``ALL``, ``EXPIRING``, ``EXPIRED``

    search_term
        Keyword to look for on the domain list

    page : 1
        Number of result page to return

    page_size : 20
        Number of domains to be listed per page (minimum: ``10``, maximum:
        ``100``)

    sort_by
        One of ``NAME``, ``NAME_DESC``, ``EXPIREDATE``, ``EXPIREDATE_DESC``,
        ``CREATEDATE``, or ``CREATEDATE_DESC``

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_domains.get_list
    """
    opts = salt.utils.namecheap.get_opts("namecheap.domains.getList")

    if list_type is not None:
        if list_type not in ["ALL", "EXPIRING", "EXPIRED"]:
            log.error("Invalid option for list_type")
            raise Exception("Invalid option for list_type")
        opts["ListType"] = list_type

    if search_term is not None:
        if len(search_term) > 70:
            log.warning("search_term trimmed to first 70 characters")
            search_term = search_term[0:70]
        opts["SearchTerm"] = search_term

    if page is not None:
        opts["Page"] = page

    if page_size is not None:
        if page_size > 100 or page_size < 10:
            log.error("Invalid option for page")
            raise Exception("Invalid option for page")
        opts["PageSize"] = page_size

    if sort_by is not None:
        if sort_by not in [
            "NAME",
            "NAME_DESC",
            "EXPIREDATE",
            "EXPIREDATE_DESC",
            "CREATEDATE",
            "CREATEDATE_DESC",
        ]:
            log.error("Invalid option for sort_by")
            raise Exception("Invalid option for sort_by")
        opts["SortBy"] = sort_by

    response_xml = salt.utils.namecheap.get_request(opts)

    if response_xml is None:
        return []

    domainresult = response_xml.getElementsByTagName("DomainGetListResult")[0]

    domains = []
    for d in domainresult.getElementsByTagName("Domain"):
        domains.append(salt.utils.namecheap.atts_to_dict(d))

    return domains
