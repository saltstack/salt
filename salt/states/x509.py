# -*- coding: utf-8 -*-
'''
Manage X509 Certificates

.. versionadded:: TBD
'''

import salt.exceptions
import salt.utils
import datetime
import os


def _subject_to_dict(subject):
    '''
    Turn the list of ordereddicts returned by states to a dict suitable
    for the x509 execution module.
    '''
    _dict = {}
    for item in subject:
        for name, val in item.iteritems():
            _dict[name] = val

    return _dict


def _exts_to_list(exts):
    '''
    Turn the list of lists of ordered dicts returned by states into a
    list of dicts suitable for the x509 execution module.
    '''
    _list = []
    for item in exts:
        for name, data in item.iteritems():
            ext = {'name': name}
            for vals in data:
                for val_name, value in vals.iteritems():
                    ext[val_name] = value
        _list.append(ext)
    return _list


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
                public_key,
                subject=None,
                extensions=None,
                version=3,
                backup=False):
    '''
    Manage a Certificate Signing Request

    name:
        Path to the CSR

    public_key:
        The public key to be added to the certificate request.

    subject:
        The subject data to be added to the certificate request.

    extensions:
        The X509v3 Extensions to be added to the certificate request.

    version:
        When replacing an existing file, backup the old file onthe minion.
        Default is False.

    Example:

    .. code-block:: yaml

        /etc/pki/mycert.csr:
          x509.csr_managed:
            - public_key: /etc/pki/mycert.key
            - subject:
              - CN: www.example.com
              - C: US
              - ST: Utah
              - L: Salt Lake City
            - extensions:
              - keyUsage:
                - value: serverAuth
                - critical: True
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if subject is None:
        subject = []

    if extensions is None:
        subject = []

    subject = _subject_to_dict(subject)
    extensions = _exts_to_list(extensions)
    if os.path.isfile(name):
        try:
            current = __salt__['x509.read_csr'](csr=name)
        except salt.exceptions.SaltInvocationError:
            current = '{0} is not a valid CSR.'.format(name)
    else:
        current = '{0} does not exist.'.format(name)

    new_csr = __salt__['x509.create_csr'](text=True, subject=subject,
            public_key=public_key, extensions=extensions, version=version)
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
                        signing_private_key,
                        subject=None,
                        signing_cert=None,
                        public_key=None,
                        csr=None,
                        extensions=None,
                        days_valid=365,
                        days_remaining=90,
                        version=3,
                        serial_number=None,
                        serial_bits=64, algorithm='sha256',
                        backup=False,):
    '''
    Manage a Certificate

    name:
        Path to the certificate

    signing_private_key:
        The private key that will be used to sign this certificate. This is
        usually your CA's private key.

    subject:
        The subject data to be added to the certificate. If both subject
        and a CSR are included, the subject properties override any individual
        properties set in the CSR.

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
        will take precidence over any extensions included in the CSR.

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

    backup:
        When replacing an existing file, backup the old file onthe minion. Default is False.

    Example:

    .. code-block:: yaml

        /etc/pki/mycert.crt:
          x509.certificate_managed:
            - csr: /etc/pki/mycert.csr
            - signing_private_key: /etc/pki/myca.key
            - signing_cert: /etc/pki/myca.crt
            - extensions:
              - basicConstraints:
                - value: CA:FALSE
                - critical: True
              - subjectKeyIdentifier:
                - value: hash
              - authorityKeyIdentifier:
                - value: keyid,issuer:always
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    if subject is None:
        subject = []

    if extensions is None:
        subject = []

    subject = _subject_to_dict(subject)
    extensions = _exts_to_list(extensions)

    current_days_remaining = 0
    current_comp = {}

    if os.path.isfile(name):
        try:
            current = __salt__['x509.read_certificate'](certificate=name)
            current_comp = current.copy()
            if not serial_number:
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

    new_cert = __salt__['x509.create_certificate'](text=True, subject=subject,
            signing_private_key=signing_private_key, signing_cert=signing_cert,
            public_key=public_key, csr=csr, extensions=extensions,
            days_valid=days_valid, version=version,
            serial_number=serial_number, serial_bits=serial_bits,
            algorithm=algorithm)

    new = __salt__['x509.read_certificate'](certificate=new_cert)
    new_comp = new.copy()
    if not serial_number:
        new_comp.pop('Serial Number')
    new_comp.pop('Not Before')
    new_comp.pop('Not After')
    new_comp.pop('MD5 Finger Print')
    new_comp.pop('SHA1 Finger Print')
    new_comp.pop('SHA-256 Finger Print')

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

    ret['comment'] = __salt__['x509.write_pem'](text=new_cert, path=name, pem_type="CERTIFICATE")
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

    algorithm:
        The algorithm to be used to sign the certificate. Default is 'sha256'.

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

def request_certificate_managed(name,
                                ca_server,
                                signing_policy,
                                newer_than='2000-01-01 00:00:00',
                                signing_cert=None,
                                public_key=None,
                                csr=None,
                                with_grains=False,
                                with_pillar=False,
                                days_remaining=90,
                                backup=False,):
    '''
    Manage a remotely signed Certificate

    This requires that the request_certificate reactor be configured on the master to
    pass signing requests to the CA server. See the full example below.

    name:
        Path to the certificate on the minion

    ca_server:
        The CA server (minion_id) that should sign this certificate.

    signing_policy:
        The signing policy the CA should use to sign this certificate. See modules/sign_certificate
        for an example of how to configure CA signing policies.

    newer_than:
        Ensure that the certificate is newer than this date. This is useful if you know the signing
        policy on the CA has changed and you want to force certificates to be renewed with this
        new information.

    signing_cert:
        The certificate corresponding to the private key that will sign this certificate. Typically
        your CA cert.

    public_key:
        The public key that will be in this certificate. This could be the path to an
        existing certificate, private key, or csr. If you include a CSR this property
        is not required. If you include the path to a CSR in this section, only the
        public key will be imported from the CSR, all other data like subject and extensions
        will not be included from the CSR.

    csr:
        A certificate signing request used to generate the certificate.

    with_grains:
        Include grains from the current minion. The signing policy
        on the CA may use grains to populate subject fields. If so, this parameter
        must include the grains that are required by the CA.
        Specify ``True`` to include all grains, or specify a
        list of strings of grain names to include.

    with_pillar:
        Include Pillar values from the current minion.
        The signing policy on the CA may use pillars to populate subject fields.
        If so, this parameter must include the pillars that are required by
        the CA. Specify ``True`` to include all Pillar values, or
        specify a list of strings of Pillar keys to include. It is a
        best-practice to only specify a relevant subset of Pillar data.

    days_remaining:
        The certificate should be automatically recreated if there are less than ``days_remaining``
        days until the crl expires. Set to 0 to disable automatic renewal. Default is 30.

    backup:
        When replacing an existing file, backup the old file on the minion. Default is False.


    Full example of an automatic signing CA:

    /srv/salt/top.sls

    .. code-block:: yaml
        
        base:
          'ca':
            - ca
          'www':
            - www

    /srv/salt/ca.sls

    .. code-block:: yaml

        /etc/pki:
          file.directory:
        
        /etc/pki/ca.key:
          x509.private_key_managed:
            - bits: 4096

        /etc/pki/ca.crt:
          x509.certificate_managed:
            - signing_private_key: /etc/pki/ca.key
            - subject:
              - CN: ca.example.com
              - C: US
              - ST: Utah
              - L: Salt Lake City
            - extensions:
              - basicConstraints: 
                - value: "CA:true"
                - critical: True
              - keyUsage: 
                - value: "cRLSign, keyCertSign"
                - critical: True - subjectKeyIdentifier:
                - value: hash
              - authorityKeyIdentifier:
                - value: keyid,issuer:always
            - days_valid: 3650
            - days_remaining: 0
            - backup: True
            - require:
              - x509: /etc/pki/ca.key

        /etc/pki/signing_policy.yml:
          file.managed:
            - source: salt://signing_policy.yml

        mine.send:
          module.run:
            - func: x509.get_pem_entries
            - kwargs:
                glob_path: /etc/pki/ca.crt
            - onchanges:
              - x509: /etc/pki/ca.crt


    /srv/salt/signing_policy.yml

    .. code-block:: yaml

        'www*':         # The first line of a signing policy is a target of allowed minions
          www:
            signing_private_key: /etc/pki/ca.key
            signing_cert: /etc/pki/ca.crt
            csr: False
            subject:
              CN:
                grain: 'fqdn'
              C: US
              ST: Utah
              L: Salt Lake City
              emailAddress:
                pillar: 'x509:Email'
                default: 'nobody@saltstack.com'
            extensions:
              - basicConstraints: 
                  value: "CA:false"
                  critical: True
              - keyUsage: 
                  value: 'serverAuth'
                  critical: True
              - subjectKeyIdentifier:
                  value: hash
              - authorityKeyIdentifier:
                  value: keyid,issuer:always
            days_valid: 360
            version: 3


    /srv/salt/www.sls

    .. code-block:: yaml

        /etc/ssl:
          file.directory:

        /etc/ssl/ca.crt:
          x509.pem_managed:
            - text: |
                {{ salt['mine.get']('ca', 'x509.get_pem_entries')['/etc/pki/ca.crt'] }}
        
        /etc/ssl/www.key:
          x509.private_key_managed:
            - bits: 4096

        /etc/ssl/www.crt:
          x509.request_certificate_managed:
            - ca_server: ca
            - signing_policy: www
            - signing_cert: /etc/ssl/ca.crt
            - public_key: /etc/ssl/www.key
            - with_grains:
              - fqdn
            - days_remaining: 90


    /etc/salt/master.d/reactor.conf

    .. code-block:: yaml

        reactor:
          - '/salt/x509/request_certificate':
              - /srv/salt/_reactor/sign_x509_request.sls


    /srv/salt/_reactor/sign_x509_request.sls

    .. code-block:: yaml

        sign_request:
          runner.x509.request_and_sign:
            - requestor: {{ data['id'] }}
            - path: {{ data['data']['path'] }}
            - ca_server: {{ data['data']['ca_server'] }}
            - signing_policy: {{ data['data']['signing_policy'] }}
            - signing_policy_def: /etc/pki/signing_policy.yml
            {% if 'public_key' in data['data'] -%}
            - public_key: {{ data['data']['public_key'] }}
            {% endif -%}
            {% if 'csr' in data['data'] -%}
            - csr: {{ data['data']['csr'] }}
            {% endif -%}
            {% if 'grains' in data['data'] -%}
            - grains: {{ data['data']['grains'] }}
            {% endif -%}
            {% if 'pillar' in data['data'] -%}
            - pillar: {{ data['data']['pillar'] }}
            {% endif -%}

    
    With the above configuration, ca will create it's own private key and CA certificate, then publish
    it's CA certificate to the mine. The minion www will generate its own private key, then the
    ``request_certificate_managed`` will fire the ``/salt/x509/request_certificate`` event to the master.
    The reactor on the master will run the ``x509.sign_request`` module on the CA to sign the certificate
    according to the signing policy, then run ``x509.save_pem`` on the minion to save the resulting signed
    certificate.
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    current_days_remaining = 0
    current_notbefore = datetime.datetime.strptime('2000-01-01 00:00:00', '%Y-%m-%d %H:%M:%S')
    newer_than = datetime.datetime.strptime(newer_than, '%Y-%m-%d %H:%M:%S')

    changes_needed = False

    if os.path.isfile(name):
        try:
            current = __salt__['x509.read_certificate'](certificate=name)
            current_notbefore = datetime.datetime.strptime(current['Not Before'],
                    '%Y-%m-%d %H:%M:%S')
            current_notafter = datetime.datetime.strptime(current['Not After'],
                    '%Y-%m-%d %H:%M:%S')
            current_days_remaining = (current_notafter - datetime.datetime.now()).days
            if days_remaining == 0:
                days_remaining = current_days_remaining - 1
            if current_days_remaining < days_remaining:
                changes_needed = True
            if current_notbefore < newer_than:
                changes_needed = True
            if not __salt__['x509.verify_signature'](certificate=name, signing_pub_key=signing_cert):
                changes_needed = True
            if not __salt__['x509.get_public_key'](public_key) == __salt__['x509.get_public_key'](name):
                changes_needed = True
        except salt.exceptions.SaltInvocationError:
            current = '{0} is not a valid Certificate.'.format(name)
            changes_needed = True
    else:
        current = '{0} does not exist.'.format(name)
        changes_needed = True

    if not changes_needed:
        ret['result'] = True
        ret['comment'] = 'The certificate is already in the correct state'
        return ret

    ret['changes'] = {'old': current}

    if __opts__['test'] == True:
        ret['comment'] = 'The certificate {0} will be updated.'.format(name)
        return ret

    if os.path.isfile(name) and backup:
        bkroot = os.path.join(__opts__['cachedir'], 'file_backup')
        salt.utils.backup_minion(name, bkroot)

    __salt__['x509.request_certificate'](path=name, ca_server=ca_server, signing_policy=signing_policy,
            public_key=public_key, csr=csr, with_grains=with_grains, with_pillar=with_pillar)

    ret['comment'] = 'A new certificate request has been submitted to {0}'.format(ca_server)
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
