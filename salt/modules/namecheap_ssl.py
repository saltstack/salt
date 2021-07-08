"""
Namecheap SSL Certificate Management

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

import logging

import salt.utils.files
import salt.utils.stringutils

try:
    import salt.utils.namecheap

    CAN_USE_NAMECHEAP = True
except ImportError:
    CAN_USE_NAMECHEAP = False


log = logging.getLogger(__name__)


def __virtual__():
    """
    Check to make sure requests and xml are installed and requests
    """
    if CAN_USE_NAMECHEAP:
        return "namecheap_ssl"
    return False


def reissue(
    csr_file,
    certificate_id,
    web_server_type,
    approver_email=None,
    http_dc_validation=False,
    **kwargs
):
    """
    Reissues a purchased SSL certificate. Returns a dictionary of result
    values.

    csr_file
        Path to Certificate Signing Request file

    certificate_id
        Unique ID of the SSL certificate you wish to activate

    web_server_type
        The type of certificate format to return. Possible values include:

        - apache2
        - apacheapachessl
        - apacheopenssl
        - apacheraven
        - apachessl
        - apachessleay
        - c2net
        - cobaltseries
        - cpanel
        - domino
        - dominogo4625
        - dominogo4626
        - ensim
        - hsphere
        - ibmhttp
        - iis
        - iis4
        - iis5
        - iplanet
        - ipswitch
        - netscape
        - other
        - plesk
        - tomcat
        - weblogic
        - website
        - webstar
        - zeusv3

    approver_email
        The email ID which is on the approver email list.

        .. note::
            ``http_dc_validation`` must be set to ``False`` if this option is
            used.

    http_dc_validation : False
        Whether or not to activate using HTTP-based validation.

    .. note::
        For other parameters which may be required, see here__.

        .. __: https://www.namecheap.com/support/api/methods/ssl/reissue.aspx

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_ssl.reissue my-csr-file my-cert-id apachessl
    """
    return __get_certificates(
        "namecheap.ssl.reissue",
        "SSLReissueResult",
        csr_file,
        certificate_id,
        web_server_type,
        approver_email,
        http_dc_validation,
        kwargs,
    )


def activate(
    csr_file,
    certificate_id,
    web_server_type,
    approver_email=None,
    http_dc_validation=False,
    **kwargs
):
    """
    Activates a newly-purchased SSL certificate. Returns a dictionary of result
    values.

    csr_file
        Path to Certificate Signing Request file

    certificate_id
        Unique ID of the SSL certificate you wish to activate

    web_server_type
        The type of certificate format to return. Possible values include:

        - apache2
        - apacheapachessl
        - apacheopenssl
        - apacheraven
        - apachessl
        - apachessleay
        - c2net
        - cobaltseries
        - cpanel
        - domino
        - dominogo4625
        - dominogo4626
        - ensim
        - hsphere
        - ibmhttp
        - iis
        - iis4
        - iis5
        - iplanet
        - ipswitch
        - netscape
        - other
        - plesk
        - tomcat
        - weblogic
        - website
        - webstar
        - zeusv3

    approver_email
        The email ID which is on the approver email list.

        .. note::
            ``http_dc_validation`` must be set to ``False`` if this option is
            used.

    http_dc_validation : False
        Whether or not to activate using HTTP-based validation.

    .. note::
        For other parameters which may be required, see here__.

        .. __: https://www.namecheap.com/support/api/methods/ssl/activate.aspx

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_ssl.activate my-csr-file my-cert-id apachessl
    """
    return __get_certificates(
        "namecheap.ssl.activate",
        "SSLActivateResult",
        csr_file,
        certificate_id,
        web_server_type,
        approver_email,
        http_dc_validation,
        kwargs,
    )


def __get_certificates(
    command,
    result_tag_name,
    csr_file,
    certificate_id,
    web_server_type,
    approver_email,
    http_dc_validation,
    kwargs,
):

    web_server_types = (
        "apacheopenssl",
        "apachessl",
        "apacheraven",
        "apachessleay",
        "c2net",
        "ibmhttp",
        "iplanet",
        "domino",
        "dominogo4625",
        "dominogo4626",
        "netscape",
        "zeusv3",
        "apache2",
        "apacheapachessl",
        "cobaltseries",
        "cpanel",
        "ensim",
        "hsphere",
        "ipswitch",
        "plesk",
        "tomcat",
        "weblogic",
        "website",
        "webstar",
        "iis",
        "other",
        "iis4",
        "iis5",
    )

    if web_server_type not in web_server_types:
        log.error("Invalid option for web_server_type=%s", web_server_type)
        raise Exception("Invalid option for web_server_type=" + web_server_type)

    if approver_email is not None and http_dc_validation:
        log.error("approver_email and http_dc_validation cannot both have values")
        raise Exception("approver_email and http_dc_validation cannot both have values")

    if approver_email is None and not http_dc_validation:
        log.error("approver_email or http_dc_validation must have a value")
        raise Exception("approver_email or http_dc_validation must have a value")

    opts = salt.utils.namecheap.get_opts(command)

    with salt.utils.files.fopen(csr_file, "rb") as csr_handle:
        opts["csr"] = salt.utils.stringutils.to_unicode(csr_handle.read())

    opts["CertificateID"] = certificate_id
    opts["WebServerType"] = web_server_type
    if approver_email is not None:
        opts["ApproverEmail"] = approver_email

    if http_dc_validation:
        opts["HTTPDCValidation"] = "True"

    for key, value in kwargs.items():
        opts[key] = value

    response_xml = salt.utils.namecheap.post_request(opts)

    if response_xml is None:
        return {}

    sslresult = response_xml.getElementsByTagName(result_tag_name)[0]
    result = salt.utils.namecheap.atts_to_dict(sslresult)

    if http_dc_validation:
        validation_tag = sslresult.getElementsByTagName("HttpDCValidation")
        if validation_tag is not None and len(validation_tag) > 0:
            validation_tag = validation_tag[0]

            if validation_tag.getAttribute("ValueAvailable").lower() == "true":
                validation_dict = {
                    "filename": validation_tag.getElementsByTagName("FileName")[0]
                    .childNodes[0]
                    .data,
                    "filecontent": validation_tag.getElementsByTagName("FileContent")[0]
                    .childNodes[0]
                    .data,
                }
                result["httpdcvalidation"] = validation_dict

    return result


def renew(years, certificate_id, certificate_type, promotion_code=None):
    """
    Renews an SSL certificate if it is ACTIVE and Expires <= 30 days. Returns
    the following information:

    - The certificate ID
    - The order ID
    - The transaction ID
    - The amount charged for the order

    years : 1
        Number of years to register

    certificate_id
        Unique ID of the SSL certificate you wish to renew

    certificate_type
        Type of SSL Certificate. Possible values include:

        - EV Multi Domain SSL
        - EV SSL
        - EV SSL SGC
        - EssentialSSL
        - EssentialSSL Wildcard
        - InstantSSL
        - InstantSSL Pro
        - Multi Domain SSL
        - PositiveSSL
        - PositiveSSL Multi Domain
        - PositiveSSL Wildcard
        - PremiumSSL
        - PremiumSSL Wildcard
        - QuickSSL Premium
        - RapidSSL
        - RapidSSL Wildcard
        - SGC Supercert
        - SSL Web Server
        - SSL Webserver EV
        - SSL123
        - Secure Site
        - Secure Site Pro
        - Secure Site Pro with EV
        - Secure Site with EV
        - True BusinessID
        - True BusinessID Multi Domain
        - True BusinessID Wildcard
        - True BusinessID with EV
        - True BusinessID with EV Multi Domain
        - Unified Communications

    promotional_code
        An optional promo code to use when renewing the certificate

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_ssl.renew 1 my-cert-id RapidSSL
    """

    valid_certs = (
        "QuickSSL Premium",
        "RapidSSL",
        "RapidSSL Wildcard",
        "PremiumSSL",
        "InstantSSL",
        "PositiveSSL",
        "PositiveSSL Wildcard",
        "True BusinessID with EV",
        "True BusinessID",
        "True BusinessID Wildcard",
        "True BusinessID Multi Domain",
        "True BusinessID with EV Multi Domain",
        "Secure Site",
        "Secure Site Pro",
        "Secure Site with EV",
        "Secure Site Pro with EV",
        "EssentialSSL",
        "EssentialSSL Wildcard",
        "InstantSSL Pro",
        "PremiumSSL Wildcard",
        "EV SSL",
        "EV SSL SGC",
        "SSL123",
        "SSL Web Server",
        "SGC Supercert",
        "SSL Webserver EV",
        "EV Multi Domain SSL",
        "Multi Domain SSL",
        "PositiveSSL Multi Domain",
        "Unified Communications",
    )

    if certificate_type not in valid_certs:
        log.error("Invalid option for certificate_type=%s", certificate_type)
        raise Exception("Invalid option for certificate_type=" + certificate_type)

    if years < 1 or years > 5:
        log.error("Invalid option for years=%s", str(years))
        raise Exception("Invalid option for years=" + str(years))

    opts = salt.utils.namecheap.get_opts("namecheap.ssl.renew")
    opts["Years"] = str(years)
    opts["CertificateID"] = str(certificate_id)
    opts["SSLType"] = certificate_type
    if promotion_code is not None:
        opts["PromotionCode"] = promotion_code

    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return {}

    sslrenewresult = response_xml.getElementsByTagName("SSLRenewResult")[0]
    return salt.utils.namecheap.atts_to_dict(sslrenewresult)


def create(years, certificate_type, promotion_code=None, sans_to_add=None):
    """
    Creates a new SSL certificate. Returns the following information:

    - Whether or not the SSL order was successful
    - The certificate ID
    - The order ID
    - The transaction ID
    - The amount charged for the order
    - The date on which the certificate was created
    - The date on which the certificate will expire
    - The type of SSL certificate
    - The number of years for which the certificate was purchased
    - The current status of the SSL certificate

    years : 1
        Number of years to register

    certificate_type
        Type of SSL Certificate. Possible values include:

        - EV Multi Domain SSL
        - EV SSL
        - EV SSL SGC
        - EssentialSSL
        - EssentialSSL Wildcard
        - InstantSSL
        - InstantSSL Pro
        - Multi Domain SSL
        - PositiveSSL
        - PositiveSSL Multi Domain
        - PositiveSSL Wildcard
        - PremiumSSL
        - PremiumSSL Wildcard
        - QuickSSL Premium
        - RapidSSL
        - RapidSSL Wildcard
        - SGC Supercert
        - SSL Web Server
        - SSL Webserver EV
        - SSL123
        - Secure Site
        - Secure Site Pro
        - Secure Site Pro with EV
        - Secure Site with EV
        - True BusinessID
        - True BusinessID Multi Domain
        - True BusinessID Wildcard
        - True BusinessID with EV
        - True BusinessID with EV Multi Domain
        - Unified Communications

    promotional_code
        An optional promo code to use when creating the certificate

    sans_to_add : 0
        This parameter defines the number of add-on domains to be purchased in
        addition to the default number of domains included with a multi-domain
        certificate. Each certificate that supports SANs has the default number
        of domains included. You may check the default number of domains
        included and the maximum number of domains that can be added to it in
        the table below.

    +----------+----------------+----------------------+-------------------+----------------+
    | Provider | Product name   | Default number of    | Maximum number of | Maximum number |
    |          |                | domains (domain from | total domains     | of domains     |
    |          |                | CSR is counted here) |                   | that can be    |
    |          |                |                      |                   | passed in      |
    |          |                |                      |                   | sans_to_add    |
    |          |                |                      |                   | parameter      |
    +----------+----------------+----------------------+-------------------+----------------+
    | Comodo   | PositiveSSL    | 3                    | 100               | 97             |
    |          | Multi-Domain   |                      |                   |                |
    +----------+----------------+----------------------+-------------------+----------------+
    | Comodo   | Multi-Domain   | 3                    | 100               | 97             |
    |          | SSL            |                      |                   |                |
    +----------+----------------+----------------------+-------------------+----------------+
    | Comodo   | EV Multi-      | 3                    | 100               | 97             |
    |          | Domain SSL     |                      |                   |                |
    +----------+----------------+----------------------+-------------------+----------------+
    | Comodo   | Unified        | 3                    | 100               | 97             |
    |          | Communications |                      |                   |                |
    +----------+----------------+----------------------+-------------------+----------------+
    | GeoTrust | QuickSSL       | 1                    | 1 domain +        | The only       |
    |          | Premium        |                      | 4 subdomains      | supported      |
    |          |                |                      |                   | value is 4     |
    +----------+----------------+----------------------+-------------------+----------------+
    | GeoTrust | True           | 5                    | 25                | 20             |
    |          | BusinessID     |                      |                   |                |
    |          | with EV        |                      |                   |                |
    |          | Multi-Domain   |                      |                   |                |
    +----------+----------------+----------------------+-------------------+----------------+
    | GeoTrust | True Business  | 5                    | 25                | 20             |
    |          | ID Multi-      |                      |                   |                |
    |          | Domain         |                      |                   |                |
    +----------+----------------+----------------------+-------------------+----------------+
    | Thawte   | SSL Web        | 1                    | 25                | 24             |
    |          | Server         |                      |                   |                |
    +----------+----------------+----------------------+-------------------+----------------+
    | Thawte   | SSL Web        | 1                    | 25                | 24             |
    |          | Server with    |                      |                   |                |
    |          | EV             |                      |                   |                |
    +----------+----------------+----------------------+-------------------+----------------+
    | Thawte   | SGC Supercerts | 1                    | 25                | 24             |
    +----------+----------------+----------------------+-------------------+----------------+
    | Symantec | Secure Site    | 1                    | 25                | 24             |
    |          | Pro with EV    |                      |                   |                |
    +----------+----------------+----------------------+-------------------+----------------+
    | Symantec | Secure Site    | 1                    | 25                | 24             |
    |          | with EV        |                      |                   |                |
    +----------+----------------+----------------------+-------------------+----------------+
    | Symantec | Secure Site    | 1                    | 25                | 24             |
    +----------+----------------+----------------------+-------------------+----------------+
    | Symantec | Secure Site    | 1                    | 25                | 24             |
    |          | Pro            |                      |                   |                |
    +----------+----------------+----------------------+-------------------+----------------+

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_ssl.create 2 RapidSSL
    """
    valid_certs = (
        "QuickSSL Premium",
        "RapidSSL",
        "RapidSSL Wildcard",
        "PremiumSSL",
        "InstantSSL",
        "PositiveSSL",
        "PositiveSSL Wildcard",
        "True BusinessID with EV",
        "True BusinessID",
        "True BusinessID Wildcard",
        "True BusinessID Multi Domain",
        "True BusinessID with EV Multi Domain",
        "Secure Site",
        "Secure Site Pro",
        "Secure Site with EV",
        "Secure Site Pro with EV",
        "EssentialSSL",
        "EssentialSSL Wildcard",
        "InstantSSL Pro",
        "PremiumSSL Wildcard",
        "EV SSL",
        "EV SSL SGC",
        "SSL123",
        "SSL Web Server",
        "SGC Supercert",
        "SSL Webserver EV",
        "EV Multi Domain SSL",
        "Multi Domain SSL",
        "PositiveSSL Multi Domain",
        "Unified Communications",
    )

    if certificate_type not in valid_certs:
        log.error("Invalid option for certificate_type=%s", certificate_type)
        raise Exception("Invalid option for certificate_type=" + certificate_type)

    if years < 1 or years > 5:
        log.error("Invalid option for years=%s", str(years))
        raise Exception("Invalid option for years=" + str(years))

    opts = salt.utils.namecheap.get_opts("namecheap.ssl.create")

    opts["Years"] = years
    opts["Type"] = certificate_type
    if promotion_code is not None:
        opts["PromotionCode"] = promotion_code
    if sans_to_add is not None:
        opts["SANStoADD"] = sans_to_add

    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return {}

    sslcreateresult = response_xml.getElementsByTagName("SSLCreateResult")[0]
    sslcertinfo = sslcreateresult.getElementsByTagName("SSLCertificate")[0]

    result = salt.utils.namecheap.atts_to_dict(sslcreateresult)
    result.update(salt.utils.namecheap.atts_to_dict(sslcertinfo))
    return result


def parse_csr(csr_file, certificate_type, http_dc_validation=False):
    """
    Parses the CSR. Returns a dictionary of result values.

    csr_file
        Path to Certificate Signing Request file

    certificate_type
        Type of SSL Certificate. Possible values include:

        - EV Multi Domain SSL
        - EV SSL
        - EV SSL SGC
        - EssentialSSL
        - EssentialSSL Wildcard
        - InstantSSL
        - InstantSSL Pro
        - Multi Domain SSL
        - PositiveSSL
        - PositiveSSL Multi Domain
        - PositiveSSL Wildcard
        - PremiumSSL
        - PremiumSSL Wildcard
        - QuickSSL Premium
        - RapidSSL
        - RapidSSL Wildcard
        - SGC Supercert
        - SSL Web Server
        - SSL Webserver EV
        - SSL123
        - Secure Site
        - Secure Site Pro
        - Secure Site Pro with EV
        - Secure Site with EV
        - True BusinessID
        - True BusinessID Multi Domain
        - True BusinessID Wildcard
        - True BusinessID with EV
        - True BusinessID with EV Multi Domain
        - Unified Communications

    http_dc_validation : False
        Set to ``True`` if a Comodo certificate and validation should be
        done with files instead of emails and to return the info to do so

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_ssl.parse_csr my-csr-file PremiumSSL
    """
    valid_certs = (
        "QuickSSL Premium",
        "RapidSSL",
        "RapidSSL Wildcard",
        "PremiumSSL",
        "InstantSSL",
        "PositiveSSL",
        "PositiveSSL Wildcard",
        "True BusinessID with EV",
        "True BusinessID",
        "True BusinessID Wildcard",
        "True BusinessID Multi Domain",
        "True BusinessID with EV Multi Domain",
        "Secure Site",
        "Secure Site Pro",
        "Secure Site with EV",
        "Secure Site Pro with EV",
        "EssentialSSL",
        "EssentialSSL Wildcard",
        "InstantSSL Pro",
        "PremiumSSL Wildcard",
        "EV SSL",
        "EV SSL SGC",
        "SSL123",
        "SSL Web Server",
        "SGC Supercert",
        "SSL Webserver EV",
        "EV Multi Domain SSL",
        "Multi Domain SSL",
        "PositiveSSL Multi Domain",
        "Unified Communications",
    )

    if certificate_type not in valid_certs:
        log.error("Invalid option for certificate_type=%s", certificate_type)
        raise Exception("Invalid option for certificate_type=" + certificate_type)

    opts = salt.utils.namecheap.get_opts("namecheap.ssl.parseCSR")

    with salt.utils.files.fopen(csr_file, "rb") as csr_handle:
        opts["csr"] = salt.utils.stringutils.to_unicode(csr_handle.read())

    opts["CertificateType"] = certificate_type
    if http_dc_validation:
        opts["HTTPDCValidation"] = "true"

    response_xml = salt.utils.namecheap.post_request(opts)

    sslparseresult = response_xml.getElementsByTagName("SSLParseCSRResult")[0]

    return salt.utils.namecheap.xml_to_dict(sslparseresult)


def get_list(**kwargs):
    """
    Returns a list of SSL certificates for a particular user

    ListType : All
        Possible values:

        - All
        - Processing
        - EmailSent
        - TechnicalProblem
        - InProgress
        - Completed
        - Deactivated
        - Active
        - Cancelled
        - NewPurchase
        - NewRenewal

        SearchTerm
            Keyword to look for on the SSL list

        Page : 1
            Page number to return

        PageSize : 20
            Total number of SSL certificates to display per page (minimum:
            ``10``, maximum: ``100``)

        SoryBy
            One of ``PURCHASEDATE``, ``PURCHASEDATE_DESC``, ``SSLTYPE``,
            ``SSLTYPE_DESC``, ``EXPIREDATETIME``, ``EXPIREDATETIME_DESC``,
            ``Host_Name``, or ``Host_Name_DESC``

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_ssl.get_list Processing
    """
    opts = salt.utils.namecheap.get_opts("namecheap.ssl.getList")
    for key, value in kwargs.items():
        opts[key] = value

    response_xml = salt.utils.namecheap.get_request(opts)

    if response_xml is None:
        return []

    ssllistresult = response_xml.getElementsByTagName("SSLListResult")[0]

    result = []
    for e in ssllistresult.getElementsByTagName("SSL"):
        ssl = salt.utils.namecheap.atts_to_dict(e)
        result.append(ssl)

    return result


def get_info(certificate_id, returncertificate=False, returntype=None):
    """
    Retrieves information about the requested SSL certificate. Returns a
    dictionary of information about the SSL certificate with two keys:

    - **ssl** - Contains the metadata information
    - **certificate** - Contains the details for the certificate such as the
      CSR, Approver, and certificate data

    certificate_id
        Unique ID of the SSL certificate

    returncertificate : False
        Set to ``True`` to ask for the certificate in response

    returntype
        Optional type for the returned certificate. Can be either "Individual"
        (for X.509 format) or "PKCS7"

        .. note::
            Required if ``returncertificate`` is ``True``

    CLI Example:

    .. code-block:: bash

        salt 'my-minion' namecheap_ssl.get_info my-cert-id
    """
    opts = salt.utils.namecheap.get_opts("namecheap.ssl.getinfo")
    opts["certificateID"] = certificate_id

    if returncertificate:
        opts["returncertificate"] = "true"
        if returntype is None:
            log.error(
                "returntype must be specified when returncertificate is set to True"
            )
            raise Exception(
                "returntype must be specified when returncertificate is set to True"
            )
        if returntype not in ["Individual", "PKCS7"]:
            log.error(
                "returntype must be specified as Individual or PKCS7, not %s",
                returntype,
            )
            raise Exception(
                "returntype must be specified as Individual or PKCS7, not " + returntype
            )
        opts["returntype"] = returntype

    response_xml = salt.utils.namecheap.get_request(opts)

    if response_xml is None:
        return {}

    sslinforesult = response_xml.getElementsByTagName("SSLGetInfoResult")[0]

    return salt.utils.namecheap.xml_to_dict(sslinforesult)
