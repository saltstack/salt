# -*- coding: utf-8 -*-
'''
Manage X509 Certificates

.. versionadded:: TBD

Certificate Properties:
    Many of the states below take a properties value. This can contain any number of properties to be
    added to a certificate. Below are values that can be specified. These values should be specified as an
    unordered dictionary, do not include a ``-`` in yaml.

    signing_private_key:
        The private key that will be used to sign this certificate. This is
        usually your CA's private key.

    subject:
        The subject data to be added to the certificate. If both subject
        and a CSR are included, the subject properties override any individual
        properties set in the CSR. The subject is itself an unordered list containing subject entries
        like ``CN``, ``C`` ect...

    signing_cert:
        The certificate of the authority that will be used to sign this certificate.
        This is usually your CA's certificate. Do not include this value when creating
        a self-signed certificate.

    public_key:
        The public key that will be in this certificate. This could be the path to an
        existing certificate, private key, or csr. If you include a CSR this property
        is not required. If you include the path to a CSR in this section, only the
        public key will be imported from the CSR, all other data like subject and extensions
        will not be included from the CSR.

    csr:
        A certificate signing request used to generate the certificate.

    extensions:
        X509v3 Extensions to be added to the certificate request. Extensions specified here
        will take precidence over any extensions included in the CSR. Extensions are and ordered
        list, so include ``-`` in yaml. See examples below.

    days_valid:
        The number of days the certificate should be valid for. Default is 365.

    days_remaining:
        The certificate should be automatically renewed if there are less than ``days_remaining``
        days until the certificate expires. Set to 0 to disable automatic renewal. Default is 90.

    version:
        The X509 certificate version. Defaults to 3.

    serial_number:
        The serial number to assign to the certificate. If omitted, a random serial number
        will be generated for the certificate.

    serial_bits:
        The size of the random serial number to generate, in bits. Default is 64.

    algorithm:
        The algorithm to be used to sign the certificate. Default is 'sha256'.

'''

import salt.exceptions
import salt.utils
import datetime
import os


def _revoked_to_list(revs):
    '''
    Turn the mess of OrderedDicts and Lists into a list of dicts for
    use in the CRL module.
    '''
    list_ = []

    for rev in revs:
        for rev_name, props in rev.iteritems():
            dict_ = {}
            for prop in props:
                for propname, val in prop.iteritems():
                    if isinstance(val, datetime.datetime):
                        val = val.strftime('%Y-%m-%d %H:%M:%S')
                    dict_[propname] = val
            list_.append(dict_)

    return list_


def private_key_managed(name,
                        bits=2048,
                        new=False,
                        backup=False):
    '''
    Manage a private key's existance.

    name:
        Path to the private key

    bits:
        Key length in bits. Default 2048.

    new:
        Always create a new key. Defaults to False.

    backup:
        When replacing an existing file, backup the old file onthe minion.
        Default is False.
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    current_bits = 0
    if os.path.isfile(name):
        try:
            current_bits = __salt__['x509.get_private_key_size'](private_key=name)
            current = "{0} bit private key".format(current_bits)
        except salt.exceptions.SaltInvocationError:
            current = '{0} is not a valid Private Key.'.format(name)
    else:
        current = '{0} does not exist.'.format(name)

    if current_bits == bits and not new:
        ret['result'] = True
        ret['comment'] = 'The Private key is already in the correct state'
        return ret

    ret['changes'] = {
            'old': current,
            'new': "{0} bit private key".format(bits)}

    if __opts__['test'] == True:
        ret['comment'] = 'The Private Key "{0}" will be updated.'.format(name)
        return ret

    if os.path.isfile(name) and backup:
        bkroot = os.path.join(__opts__['cachedir'], 'file_backup')
        salt.utils.backup_minion(name, bkroot)

    ret['comment'] = __salt__['x509.create_private_key'](path=name, bits=bits)
    ret['result'] = True

    return ret


def csr_managed(name,
                backup=False,
                **kwargs):
    '''
    Manage a Certificate Signing Request

    name:
        Path to the CSR

    properties:
        The properties to be added to the certificate request, including items like subject, extensions
        and public key. See above for valid properties.

    Example:

    .. code-block:: yaml

        /etc/pki/mycert.csr:
          x509.csr_managed:
             - public_key: /etc/pki/mycert.key
             - CN: www.example.com
             - C: US
             - ST: Utah
             - L: Salt Lake City
             - keyUsage: 'critical dataEncipherment'
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if os.path.isfile(name):
        try:
            current = __salt__['x509.read_csr'](csr=name)
        except salt.exceptions.SaltInvocationError:
            current = '{0} is not a valid CSR.'.format(name)
    else:
        current = '{0} does not exist.'.format(name)

    new_csr = __salt__['x509.create_csr'](text=True, **kwargs)
    new = __salt__['x509.read_csr'](csr=new_csr)

    if current == new:
        ret['result'] = True
        ret['comment'] = 'The CSR is already in the correct state'
        return ret

    ret['changes'] = {
            'old': current,
            'new': new,}

    if __opts__['test'] == True:
        ret['comment'] = 'The CSR {0} will be updated.'.format(name)

    if os.path.isfile(name) and backup:
        bkroot = os.path.join(__opts__['cachedir'], 'file_backup')
        salt.utils.backup_minion(name, bkroot)

    ret['comment'] = __salt__['x509.write_pem'](text=new_csr, path=name, pem_type="CERTIFICATE REQUEST")
    ret['result'] = True

    return ret


def certificate_managed(name,
                        days_remaining=90,
                        backup=False,
                        **kwargs):
    '''
    Manage a Certificate

    name:
        Path to the certificate

    properties:
        The properties to be added to the certificate request, including items like subject, extensions
        and public key. See above for valid properties.

    days_remaining:
        The minimum number of days remaining when the certificate should be recreted. Default is 90. A
        value of 0 disables automatic renewal.

    backup:
        When replacing an existing file, backup the old file onthe minion. Default is False.

    Example:

    .. code-block:: yaml

        /etc/pki/mycert.crt:
          x509.certificate_managed:
            - properties:
                csr: /etc/pki/mycert.csr
                subject:
                  CN: ca.example.com
                signing_private_key: /etc/pki/myca.key
                signing_cert: /etc/pki/myca.crt
                extensions:
                  - basicConstraints:
                      value: CA:FALSE
                      critical: True
                  - subjectKeyIdentifier:
                      value: hash
                  - authorityKeyIdentifier:
                      value: keyid,issuer:always
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    current_days_remaining = 0
    current_comp = {}

    changes_needed = False
    if os.path.isfile(name):
        try:
            current = __salt__['x509.read_certificate'](certificate=name)
            current_comp = current.copy()
            if 'serial_number' not in kwargs:
                current_comp.pop('Serial Number')
            current_comp.pop('Not Before')
            current_comp.pop('MD5 Finger Print')
            current_comp.pop('SHA1 Finger Print')
            current_comp.pop('SHA-256 Finger Print')
            current_notafter = current_comp.pop('Not After')
            current_days_remaining = (
                    datetime.datetime.strptime(current_notafter, '%Y-%m-%d %H:%M:%S') -
                    datetime.datetime.now()).days
            if days_remaining == 0:
                days_remaining = current_days_remaining - 1
        except salt.exceptions.SaltInvocationError:
            current = '{0} is not a valid Certificate.'.format(name)
    else:
        current = '{0} does not exist.'.format(name)
        changes_needed = True

    if 'ca_server' in kwargs and 'signing_policy' not in kwargs:
        raise salt.exceptions.SaltInvocationError('signing_policy must be specified if ca_server is.')

    new = __salt__['x509.create_certificate'](testrun=True, **kwargs)

    if isinstance(new, dict):
        new_comp = new.copy()
        if 'serial_number' not in kwargs:
            new_comp.pop('Serial Number')
        new_comp.pop('Not Before')
        new_comp.pop('Not After')
        new_comp.pop('MD5 Finger Print')
        new_comp.pop('SHA1 Finger Print')
        new_comp.pop('SHA-256 Finger Print')
    else:
        new_comp = new

    if current_comp == new_comp and current_days_remaining > days_remaining:
        ret['result'] = True
        ret['comment'] = 'The certificate is already in the correct state'
        return ret

    ret['changes'] = {
            'old': current,
            'new': new,}

    if __opts__['test'] == True:
        ret['comment'] = 'The certificate {0} will be updated.'.format(name)
        return ret

    if os.path.isfile(name) and backup:
        bkroot = os.path.join(__opts__['cachedir'], 'file_backup')
        salt.utils.backup_minion(name, bkroot)

    ret['comment'] = __salt__['x509.create_certificate'](path=name, **kwargs)
    ret['result'] = True

    return ret


def crl_managed(name,
                signing_private_key,
                signing_cert=None,
                revoked=None,
                days_valid=100,
                days_remaining=30,
                include_expired=False,
                backup=False,):
    '''
    Manage a Certificate Revocation List

    name:
        Path to the certificate

    signing_private_key:
        The private key that will be used to sign this crl. This is
        usually your CA's private key.

    signing_cert:
        The certificate of the authority that will be used to sign this crl.
        This is usually your CA's certificate.

    revoked:
        A list of certificates to revoke. Must include either a serial number or a
        the certificate itself. Can optionally include the revocation date and
        notAfter date from the certificate. See example below for details.

    days_valid:
        The number of days the certificate should be valid for. Default is 100.

    days_remaining:
        The crl should be automatically recreated if there are less than ``days_remaining``
        days until the crl expires. Set to 0 to disable automatic renewal. Default is 30.

    include_expired:
        Include expired certificates in the CRL. Default is ``False``.

    backup:
        When replacing an existing file, backup the old file onthe minion. Default is False.

    Example:

    .. code-block:: yaml

        /etc/pki/ca.crl:
          x509.crl_managed:
            - signing_private_key: /etc/pki/myca.key
            - signing_cert: /etc/pki/myca.crt
            - revoked:
              - compromized_Web_key:
                - certificate: /etc/pki/certs/badweb.crt
                - revocation_date: 2015-03-01 00:00:00
                - reason: keyCompromise
              - terminated_vpn_user:
                - serial_number: D6:D2:DC:D8:4D:5C:C0:F4
                - not_after: 2016-01-01 00:00:00
                - revocation_date: 2015-02-25 00:00:00
                - reason: cessationOfOperation
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if revoked is None:
        revoked = []

    revoked = _revoked_to_list(revoked)

    current_days_remaining = 0
    current_comp = {}

    if os.path.isfile(name):
        try:
            current = __salt__['x509.read_crl'](crl=name)
            current_comp = current.copy()
            current_comp.pop('Last Update')
            current_notafter = current_comp.pop('Next Update')
            current_days_remaining = (
                    datetime.datetime.strptime(current_notafter, '%Y-%m-%d %H:%M:%S') -
                    datetime.datetime.now()).days
            if days_remaining == 0:
                days_remaining = current_days_remaining - 1
        except salt.exceptions.SaltInvocationError:
            current = '{0} is not a valid CRL.'.format(name)
    else:
        current = '{0} does not exist.'.format(name)

    new_crl = __salt__['x509.create_crl'](text=True, signing_private_key=signing_private_key,
            signing_cert=signing_cert, revoked=revoked, days_valid=days_valid, include_expired=include_expired)

    new = __salt__['x509.read_crl'](crl=new_crl)
    new_comp = new.copy()
    new_comp.pop('Last Update')
    new_comp.pop('Next Update')

    if current_comp == new_comp and current_days_remaining > days_remaining:
        ret['result'] = True
        ret['comment'] = 'The crl is already in the correct state'
        return ret

    ret['changes'] = {
            'old': current,
            'new': new,}

    if __opts__['test'] == True:
        ret['comment'] = 'The crl {0} will be updated.'.format(name)
        return ret

    if os.path.isfile(name) and backup:
        bkroot = os.path.join(__opts__['cachedir'], 'file_backup')
        salt.utils.backup_minion(name, bkroot)

    ret['comment'] = __salt__['x509.write_pem'](text=new_crl, path=name, pem_type="X509 CRL")
    ret['result'] = True

    return ret


def pem_managed(name,
                text,
                backup=False):
    '''
    Manage the contents of a PEM file directly with the content in text, ensuring correct formatting.

    name:
        The path to the file to manage

    text:
        The PEM formatted text to write.

    backup:
        When replacing an existing file, backup the old file on the minion. Default is False.
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    new = __salt__['x509.get_pem_entry'](text=text)

    if os.path.isfile(name):
        current = salt.utils.fopen(name).read()
    else:
        current = '{0} does not exist.'.format(name)

    if new == current:
        ret['result'] = True
        ret['comment'] = 'The file is already in the correct state'
        return ret

    if __opts__['test'] == True:
        ret['comment'] = 'The file {0} will be updated.'.format(name)
        return ret

    if os.path.isfile(name) and backup:
        bkroot = os.path.join(__opts__['cachedir'], 'file_backup')
        salt.utils.backup_minion(name, bkroot)

    ret['comment'] = __salt__['x509.write_pem'](text=text, path=name)
    ret['result'] = True

    return ret
