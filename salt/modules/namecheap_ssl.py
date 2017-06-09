# -*- coding: utf-8 -*-
'''
 Namecheap management

 .. versionadded:: Nitrogen

 General Notes
 -------------

 Use this module to manage ssl certificates through the namecheap
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
from __future__ import absolute_import

# Import Salt libs
import salt.utils
try:
    import salt.utils.namecheap
    CAN_USE_NAMECHEAP = True
except ImportError:
    CAN_USE_NAMECHEAP = False

# Import 3rd-party libs
import salt.ext.six as six


def __virtual__():
    '''
    Check to make sure requests and xml are installed and requests
    '''
    if CAN_USE_NAMECHEAP:
        return 'namecheap_ssl'
    return False


def reissue(csr_file,
            certificate_id,
            web_server_type,
            approver_email=None,
            http_dc_validation=False,
            **kwargs):
    '''
    Reissues a purchased SSL certificate

    returns a dictionary of result values

    Required Parameters:
        csr
            string  Certificate Signing Request

        certificate_id
            integer  Unique ID of the SSL certificate you wish to activate

        web_server_type
            string  The type of certificate format to return
                    Possible values: apacheopenssl, apachessl, apacheraven,
                                     apachessleay, c2net, ibmhttp, iplanet,
                                     domino, dominogo4625, dominogo4626,
                                     netscape, zeusv3, apache2,
                                     apacheapachessl, cobaltseries, cpanel,
                                     ensim, hsphere, ipswitch, plesk,
                                     tomcat, weblogic, website, webstar,
                                     iis, other, iis4, iis5

        approver_email
            string  The email ID which is on the approver email list
                    http_dc_validation must be set to False if this parameter
                    is used

        http_dc_validation
            bool  An indicator that shows if certificate should be
                  activated using HTTP-based validation. Please specify
                  True if you wish to use HTTP-based validation.
                  approver_email should be set to None if this parameter
                  is used

    Other required parameters:
        please see https://www.namecheap.com/support/api/methods/ssl/reissue.aspx

    CLI Example:

    .. code-block::

        salt 'my-minion' namecheap_ssl.reissue my-csr-file my-cert-id apachessl
    '''
    return __get_certificates('namecheap.ssl.reissue', "SSLReissueResult", csr_file, certificate_id, web_server_type,
                              approver_email, http_dc_validation, kwargs)


def activate(csr_file,
             certificate_id,
             web_server_type,
             approver_email=None,
             http_dc_validation=False,
             **kwargs):
    '''
    Activates a newly purchased SSL certificate

    returns a dictionary of result values

    Required Parameters:
        csr
            string  Certificate Signing Request

        certificate_id
            integer  Unique ID of the SSL certificate you wish to activate

        web_server_type
            string  The type of certificate format to return
                    Possible values: apacheopenssl, apachessl, apacheraven,
                                     apachessleay, c2net, ibmhttp, iplanet,
                                     domino, dominogo4625, dominogo4626,
                                     netscape, zeusv3, apache2,
                                     apacheapachessl, cobaltseries, cpanel,
                                     ensim, hsphere, ipswitch, plesk,
                                     tomcat, weblogic, website, webstar,
                                     iis, other, iis4, iis5

        approver_email
            string  The email ID which is on the approver email list
                    http_dc_validation must be set to False if this parameter
                    is used

        http_dc_validation
            bool  An indicator that shows if certificate should be
                  activated using HTTP-based validation. Please specify
                  True if you wish to use HTTP-based validation.
                  approver_email should be set to None if this parameter
                  is used

    Other required parameters:
        please see https://www.namecheap.com/support/api/methods/ssl/activate.aspx

    CLI Example:

    .. code-block::

        salt 'my-minion' namecheap_ssl.activate my-csr-file my-cert-id apachessl
    '''
    return __get_certificates('namecheap.ssl.activate', 'SSLActivateResult', csr_file, certificate_id, web_server_type,
                              approver_email, http_dc_validation, kwargs)


def __get_certificates(command,
                       result_tag_name,
                       csr_file,
                       certificate_id,
                       web_server_type,
                       approver_email,
                       http_dc_validation,
                       kwargs):

    web_server_types = set(['apacheopenssl',
                            'apachessl',
                            'apacheraven',
                            'apachessleay',
                            'c2net',
                            'ibmhttp',
                            'iplanet',
                            'domino',
                            'dominogo4625',
                            'dominogo4626',
                            'netscape',
                            'zeusv3',
                            'apache2',
                            'apacheapachessl',
                            'cobaltseries',
                            'cpanel',
                            'ensim',
                            'hsphere',
                            'ipswitch',
                            'plesk',
                            'tomcat',
                            'weblogic',
                            'website',
                            'webstar',
                            'iis',
                            'other',
                            'iis4',
                            'iis5'])

    if web_server_type not in web_server_types:
        salt.utils.namecheap.log.error('Invalid option for web_server_type=' + web_server_type)
        raise Exception('Invalid option for web_server_type=' + web_server_type)

    if approver_email is not None and http_dc_validation:
        salt.utils.namecheap.log.error('approver_email and http_dc_validation cannot both have values')
        raise Exception('approver_email and http_dc_validation cannot both have values')

    if approver_email is None and not http_dc_validation:
        salt.utils.namecheap.log.error('approver_email or http_dc_validation must have a value')
        raise Exception('approver_email or http_dc_validation must have a value')

    opts = salt.utils.namecheap.get_opts(command)

    with salt.utils.fopen(csr_file, 'rb') as csr_handle:
        opts['csr'] = csr_handle.read()

    opts['CertificateID'] = certificate_id
    opts['WebServerType'] = web_server_type
    if approver_email is not None:
        opts['ApproverEmail'] = approver_email

    if http_dc_validation:
        opts['HTTPDCValidation'] = 'True'

    for key, value in six.iteritems(kwargs):
        opts[key] = value

    response_xml = salt.utils.namecheap.post_request(opts)

    if response_xml is None:
        return {}

    sslresult = response_xml.getElementsByTagName(result_tag_name)[0]
    result = salt.utils.namecheap.atts_to_dict(sslresult)

    if http_dc_validation:
        validation_tag = sslresult.getElementsByTagName('HttpDCValidation')
        if validation_tag is not None and len(validation_tag) > 0:
            validation_tag = validation_tag[0]

            if validation_tag.getAttribute('ValueAvailable').lower() == 'true':
                validation_dict = {'filename': validation_tag.getElementsByTagName('FileName')[0].childNodes[0].data,
                                   'filecontent': validation_tag.getElementsByTagName('FileContent')[0].childNodes[
                                       0].data}
                result['httpdcvalidation'] = validation_dict

    return result


def renew(years, certificate_id, certificate_type, promotion_code=None):
    '''
    Renews an SSL certificate if it is ACTIVE and Expires <= 30 days

    returns a dictionary with the following values:
        orderid A unique integer value that represents the order
        transactionid A unique integer value that represents the transaction
        chargedamount The amount charged for the order
        certificateid A unique integer value that represents the SSL

    Required parameters:
        years
            integer  Number of years to register
                     Default: 1

        certificate_id
            integer  Unique identifier for the existing certificate to renew

        certificate_type
            string  Type of SSL Certificate,
                    Possible Values: QuickSSL Premium, RapidSSL, RapidSSL Wildcard,
                                     PremiumSSL, InstantSSL, PositiveSSL, PositiveSSL Wildcard,
                                     True BusinessID with EV, True BusinessID,
                                     True BusinessID Wildcard, True BusinessID Multi Domain,
                                     True BusinessID with EV Multi Domain, Secure Site,
                                     Secure Site Pro, Secure Site with EV,
                                     Secure Site Pro with EV, EssentialSSL, EssentialSSL Wildcard,
                                     InstantSSL Pro, PremiumSSL Wildcard, EV SSL, EV SSL SGC,
                                     SSL123, SSL Web Server, SGC Supercert, SSL Webserver EV,
                                     EV Multi Domain SSL, Multi Domain SSL,
                                     PositiveSSL Multi Domain, Unified Communications

    Optional parameters:
        promotional_code
            string  Promotional (coupon) code for the certificate

    CLI Example:

    .. code-block::

        salt 'my-minion' namecheap_ssl.renew 1 my-cert-id RapidSSL
    '''

    valid_certs = set(['QuickSSL Premium',
                       'RapidSSL',
                       'RapidSSL Wildcard',
                       'PremiumSSL',
                       'InstantSSL',
                       'PositiveSSL',
                       'PositiveSSL Wildcard',
                       'True BusinessID with EV',
                       'True BusinessID',
                       'True BusinessID Wildcard',
                       'True BusinessID Multi Domain',
                       'True BusinessID with EV Multi Domain',
                       'Secure Site',
                       'Secure Site Pro',
                       'Secure Site with EV',
                       'Secure Site Pro with EV',
                       'EssentialSSL',
                       'EssentialSSL Wildcard',
                       'InstantSSL Pro',
                       'PremiumSSL Wildcard',
                       'EV SSL',
                       'EV SSL SGC',
                       'SSL123',
                       'SSL Web Server',
                       'SGC Supercert',
                       'SSL Webserver EV',
                       'EV Multi Domain SSL',
                       'Multi Domain SSL',
                       'PositiveSSL Multi Domain',
                       'Unified Communications'])

    if certificate_type not in valid_certs:
        salt.utils.namecheap.log.error('Invalid option for certificate_type=' + certificate_type)
        raise Exception('Invalid option for certificate_type=' + certificate_type)

    if years < 1 or years > 5:
        salt.utils.namecheap.log.error('Invalid option for years=' + str(years))
        raise Exception('Invalid option for years=' + str(years))

    opts = salt.utils.namecheap.get_opts('namecheap.ssl.renew')
    opts['Years'] = str(years)
    opts['CertificateID'] = str(certificate_id)
    opts['SSLType'] = certificate_type
    if promotion_code is not None:
        opts['PromotionCode'] = promotion_code

    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return {}

    sslrenewresult = response_xml.getElementsByTagName('SSLRenewResult')[0]
    return salt.utils.namecheap.atts_to_dict(sslrenewresult)


def create(years, certificate_type, promotion_code=None, sans_to_add=None):
    '''
    Creates a new SSL certificate

    returns a dictionary with the following values:
        issuccess Indicates whether SSL order was successful
        orderid A unique integer value that represents the order
        transactionid A unique integer value that represents the transaction
        chargedamount The amount charged for the order
        certificateid A unique integer value that represents the SSL
        created The date on which the certificate is created
        expires The date on which the certificate expires
        ssltype Type of SSL cerificate
        years Number of years for which the certificate is purchased
        status The current status of SSL certificate

    Required parameters:
        years
            integer  Number of years to register
                     Default: 1

        certificate_type
            string  Type of SSL Certificate,
                    Possible Values: QuickSSL Premium, RapidSSL, RapidSSL Wildcard,
                                     PremiumSSL, InstantSSL, PositiveSSL, PositiveSSL Wildcard,
                                     True BusinessID with EV, True BusinessID,
                                     True BusinessID Wildcard, True BusinessID Multi Domain,
                                     True BusinessID with EV Multi Domain, Secure Site,
                                     Secure Site Pro, Secure Site with EV,
                                     Secure Site Pro with EV, EssentialSSL, EssentialSSL Wildcard,
                                     InstantSSL Pro, PremiumSSL Wildcard, EV SSL, EV SSL SGC,
                                     SSL123, SSL Web Server, SGC Supercert, SSL Webserver EV,
                                     EV Multi Domain SSL, Multi Domain SSL,
                                     PositiveSSL Multi Domain, Unified Communications

    Optional parameters:
        promotional_code
            string  Promotional (coupon) code for the certificate

        sans_to_add
            integer  This parameter defines the number of add-on domains to be purchased in
                     addition to the default number of domains included with a multi-domain
                     certificate. Each certificate that supports SANs has the default number
                     of domains included. You may check the default number of domains
                     included and the maximum number of domains that can be added to it
                     in the table below.
                     Default: 0
--------------------------------------------------------------------------------
Provider  Product name  Default number of     Maximum number of  Maximum number
                        domains (domain from  total domains      of domains
                        CSR is counted here)                     that can be
                                                                 passed in
                                                                 SANStoADD
                                                                 parameter
--------------------------------------------------------------------------------
Comodo    PositiveSSL                      3                100              97
          Multi-Domain
--------------------------------------------------------------------------------
Comodo    Multi-Domain                     3                100              97
          SSL
--------------------------------------------------------------------------------
Comodo    EV Multi-                        3                100              97
          Domain SSL
--------------------------------------------------------------------------------
Comodo    Unified                          3                100              97
          Communications
--------------------------------------------------------------------------------
GeoTrust  QuickSSL                         1         1 domain +        The only
          Premium                                  4 subdomains       supported
                                                                     value is 4
--------------------------------------------------------------------------------
GeoTrust  True                             5                 25              20
          BusinessID
          with EV
          Multi-Domain
--------------------------------------------------------------------------------
GeoTrust  True Business                    5                 25              20
          ID Multi-
          Domain
--------------------------------------------------------------------------------
Thawte    SSL Web                          1                 25              24
          Server
--------------------------------------------------------------------------------
Thawte    SSL Web                          1                 25              24
          Server with
          EV
--------------------------------------------------------------------------------
Thawte    SGC Supercerts                   1                 25              24
--------------------------------------------------------------------------------
Symantec  Secure Site                      1                 25              24
          Pro with EV
--------------------------------------------------------------------------------
Symantec  Secure Site                      1                 25              24
          with EV
--------------------------------------------------------------------------------
Symantec  Secure Site                      1                 25              24
--------------------------------------------------------------------------------
Symantec  Secure Site                      1                 25              24
          Pro
--------------------------------------------------------------------------------

    CLI Example:

    .. code-block::

        salt 'my-minion' namecheap_ssl.create 2 RapidSSL
    '''
    valid_certs = set(['QuickSSL Premium',
                       'RapidSSL',
                       'RapidSSL Wildcard',
                       'PremiumSSL',
                       'InstantSSL',
                       'PositiveSSL',
                       'PositiveSSL Wildcard',
                       'True BusinessID with EV',
                       'True BusinessID',
                       'True BusinessID Wildcard',
                       'True BusinessID Multi Domain',
                       'True BusinessID with EV Multi Domain',
                       'Secure Site',
                       'Secure Site Pro',
                       'Secure Site with EV',
                       'Secure Site Pro with EV',
                       'EssentialSSL',
                       'EssentialSSL Wildcard',
                       'InstantSSL Pro',
                       'PremiumSSL Wildcard',
                       'EV SSL',
                       'EV SSL SGC',
                       'SSL123',
                       'SSL Web Server',
                       'SGC Supercert',
                       'SSL Webserver EV',
                       'EV Multi Domain SSL',
                       'Multi Domain SSL',
                       'PositiveSSL Multi Domain',
                       'Unified Communications'])

    if certificate_type not in valid_certs:
        salt.utils.namecheap.log.error('Invalid option for certificate_type=' + certificate_type)
        raise Exception('Invalid option for certificate_type=' + certificate_type)

    if years < 1 or years > 5:
        salt.utils.namecheap.log.error('Invalid option for years=' + str(years))
        raise Exception('Invalid option for years=' + str(years))

    opts = salt.utils.namecheap.get_opts('namecheap.ssl.create')

    opts['Years'] = years
    opts['Type'] = certificate_type
    if promotion_code is not None:
        opts['PromotionCode'] = promotion_code
    if sans_to_add is not None:
        opts['SANStoADD'] = sans_to_add

    response_xml = salt.utils.namecheap.post_request(opts)
    if response_xml is None:
        return {}

    sslcreateresult = response_xml.getElementsByTagName('SSLCreateResult')[0]
    sslcertinfo = sslcreateresult.getElementsByTagName('SSLCertificate')[0]

    result = salt.utils.namecheap.atts_to_dict(sslcreateresult)
    result.update(salt.utils.namecheap.atts_to_dict(sslcertinfo))
    return result


def parse_csr(csr_file, certificate_type, http_dc_validation=False):
    '''
    Parses the CSR

    returns a dictionary of result values

    Required parameters:

        csr_file
            string  Certificate Signing Request File

        certificate_type
            string  Type of SSL Certificate,
                    Possible Values: QuickSSL Premium, RapidSSL, RapidSSL Wildcard,
                                     PremiumSSL, InstantSSL, PositiveSSL, PositiveSSL Wildcard,
                                     True BusinessID with EV, True BusinessID,
                                     True BusinessID Wildcard, True BusinessID Multi Domain,
                                     True BusinessID with EV Multi Domain, Secure Site,
                                     Secure Site Pro, Secure Site with EV,
                                     Secure Site Pro with EV, EssentialSSL, EssentialSSL Wildcard,
                                     InstantSSL Pro, PremiumSSL Wildcard, EV SSL, EV SSL SGC,
                                     SSL123, SSL Web Server, SGC Supercert, SSL Webserver EV,
                                     EV Multi Domain SSL, Multi Domain SSL,
                                     PositiveSSL Multi Domain, Unified Communications

    Optional parameter:

        http_dc_validation
            bool  True if a Comodo certificate and validation should be done with files
                  instead of emails and to return the info to do so

    CLI Example:

    .. code-block::

        salt 'my-minion' namecheap_ssl.parse_csr my-csr-file PremiumSSL
    '''
    valid_certs = set(['QuickSSL Premium',
                       'RapidSSL',
                       'RapidSSL Wildcard',
                       'PremiumSSL',
                       'InstantSSL',
                       'PositiveSSL',
                       'PositiveSSL Wildcard',
                       'True BusinessID with EV',
                       'True BusinessID',
                       'True BusinessID Wildcard',
                       'True BusinessID Multi Domain',
                       'True BusinessID with EV Multi Domain', 'Secure Site',
                       'Secure Site Pro',
                       'Secure Site with EV',
                       'Secure Site Pro with EV',
                       'EssentialSSL',
                       'EssentialSSL Wildcard',
                       'InstantSSL Pro',
                       'PremiumSSL Wildcard',
                       'EV SSL',
                       'EV SSL SGC',
                       'SSL123',
                       'SSL Web Server',
                       'SGC Supercert',
                       'SSL Webserver EV',
                       'EV Multi Domain SSL',
                       'Multi Domain SSL',
                       'PositiveSSL Multi Domain',
                       'Unified Communications'])

    if certificate_type not in valid_certs:
        salt.utils.namecheap.log.error('Invalid option for certificate_type=' + certificate_type)
        raise Exception('Invalid option for certificate_type=' + certificate_type)

    opts = salt.utils.namecheap.get_opts('namecheap.ssl.parseCSR')

    with salt.utils.fopen(csr_file, 'rb') as csr_handle:
        opts['csr'] = csr_handle.read()

    opts['CertificateType'] = certificate_type
    if http_dc_validation:
        opts['HTTPDCValidation'] = 'true'

    response_xml = salt.utils.namecheap.post_request(opts)

    sslparseresult = response_xml.getElementsByTagName('SSLParseCSRResult')[0]

    return salt.utils.namecheap.xml_to_dict(sslparseresult)


def get_list(**kwargs):
    '''
    Returns a list of SSL certificates for a particular user

    Optional parameters:

        ListType
            string  Possible values: All,Processing,EmailSent,
                                     TechnicalProblem,InProgress,Completed,
                                     Deactivated,Active,Cancelled,NewPurchase,
                                     NewRenewal
                    Default: All

        SearchTerm
            string  Keyword to look for on the SSL list

        Page
            integer  Page to return
                     Default: 1

        PageSize
            integer  Total number of SSL certificates to display in a page
                     Minimum value is 10 and maximum value is 100
                     Default: 20

        SoryBy
            string  Possible values are PURCHASEDATE,PURCHASEDATE_DESC,
                                        SSLTYPE,SSLTYPE_DESC,
                                        EXPIREDATETIME,EXPIREDATETIME_DESC,
                                        Host_Name,Host_Name_DESC

    CLI Example:

    .. code-block::

        salt 'my-minion' namecheap_ssl.get_list Processing
    '''
    opts = salt.utils.namecheap.get_opts('namecheap.ssl.getList')
    for key, value in six.iteritems(kwargs):
        opts[key] = value

    response_xml = salt.utils.namecheap.get_request(opts)

    if response_xml is None:
        return []

    ssllistresult = response_xml.getElementsByTagName('SSLListResult')[0]

    result = []
    for e in ssllistresult.getElementsByTagName('SSL'):
        ssl = salt.utils.namecheap.atts_to_dict(e)
        result.append(ssl)

    return result


def get_info(certificate_id, returncertificate=False, returntype=None):
    '''
    Retrieves information about the requested SSL certificate

    returns a dictionary of information about the SSL certificate with two keys
            "ssl" contains the metadata information
            "certificate" contains the details for the certificate like
                          the CSR, Approver, and certificate data

    certificate_id
        integer  Unique ID of the SSL certificate

    returncertificate
        bool  True to ask for the certificate in response

    returntype
        string  Type of returned certificate.  Parameter takes "Individual (for X.509 format) or PKCS7"
                Required if returncertificate is True

    CLI Example:

    .. code-block::

        salt 'my-minion' namecheap_ssl.get_info my-cert-id
    '''
    opts = salt.utils.namecheap.get_opts('namecheap.ssl.getinfo')
    opts['certificateID'] = certificate_id

    if returncertificate:
        opts['returncertificate'] = "true"
        if returntype is None:
            salt.utils.namecheap.log.error('returntype must be specified when returncertificate is set to True')
            raise Exception('returntype must be specified when returncertificate is set to True')
        if returntype not in ["Individual", "PKCS7"]:
            salt.utils.namecheap.log.error('returntype must be specified as Individual or PKCS7, not ' + returntype)
            raise Exception('returntype must be specified as Individual or PKCS7, not ' + returntype)
        opts['returntype'] = returntype

    response_xml = salt.utils.namecheap.get_request(opts)

    if response_xml is None:
        return {}

    sslinforesult = response_xml.getElementsByTagName('SSLGetInfoResult')[0]

    return salt.utils.namecheap.xml_to_dict(sslinforesult)
