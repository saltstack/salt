# -*- coding: utf-8 -*-
'''
Manage X509 Certificates

.. versionadded:: 2015.8.0

This module can enable managing a complete PKI infrastructure including creating private keys, CA's,
certificates and CRLs. It includes the ability to generate a private key on a server, and have the
corresponding public key sent to a remote CA to create a CA signed certificate. This can be done in
a secure manner, where private keys are always generated locally and never moved across the network.

Here is a simple example scenario. In this example ``ca`` is the ca server,
and ``www`` is a web server that needs a certificate signed by ``ca``.

For remote signing, peers must be permitted to remotely call the
:mod:`sign_remote_certificate <salt.modules.x509.sign_remote_certificate>` function.


/etc/salt/master.d/peer.sls

.. code-block:: yaml

    peer:
      .*:
        - x509.sign_remote_certificate


/srv/salt/top.sls

.. code-block:: yaml

    base:
      '*':
        - cert
      'ca':
        - ca
      'www':
        - www


This state creates the CA key, certificate and signing policy. It also publishes the certificate to
the mine where it can be easily retrieved by other minions.

/srv/salt/ca.sls

.. code-block:: yaml

    salt-minion:
      service.running:
        - enable: True
        - listen:
          - file: /etc/salt/minion.d/signing_policies.conf

    /etc/salt/minion.d/signing_policies.conf:
      file.managed:
        - source: salt://signing_policies.conf

    /etc/pki:
      file.directory: []

    /etc/pki/issued_certs:
      file.directory: []

    /etc/pki/ca.key:
      x509.private_key_managed:
        - bits: 4096
        - backup: True
        - require:
          - file: /etc/pki

    /etc/pki/ca.crt:
      x509.certificate_managed:
        - signing_private_key: /etc/pki/ca.key
        - CN: ca.example.com
        - C: US
        - ST: Utah
        - L: Salt Lake City
        - basicConstraints: "critical CA:true"
        - keyUsage: "critical cRLSign, keyCertSign"
        - subjectKeyIdentifier: hash
        - authorityKeyIdentifier: keyid,issuer:always
        - days_valid: 3650
        - days_remaining: 0
        - backup: True
        - require:
          - x509: /etc/pki/ca.key

    mine.send:
      module.run:
        - func: x509.get_pem_entries
        - kwargs:
            glob_path: /etc/pki/ca.crt
        - onchanges:
          - x509: /etc/pki/ca.crt


The signing policy defines properties that override any property requested or included in a CRL. It also
can define a restricted list of minons which are allowed to remotely invoke this signing policy.

/srv/salt/signing_policies.conf

.. code-block:: yaml

    x509_signing_policies:
      www:
        - minions: 'www'
        - signing_private_key: /etc/pki/ca.key
        - signing_cert: /etc/pki/ca.crt
        - C: US
        - ST: Utah
        - L: Salt Lake City
        - basicConstraints: "critical CA:false"
        - keyUsage: "critical cRLSign, keyCertSign"
        - subjectKeyIdentifier: hash
        - authorityKeyIdentifier: keyid,issuer:always
        - days_valid: 90
        - copypath: /etc/pki/issued_certs/


This state will instruct all minions to trust certificates signed by our new CA.
Using jinja to strip newlines from the text avoids dealing with newlines in the rendered yaml,
and the  :mod:`sign_remote_certificate <salt.states.x509.sign_remote_certificate>` state will
handle properly formatting the text before writing the output.

/srv/salt/cert.sls

.. code-block:: yaml

    /usr/local/share/ca-certificates:
      file.directory: []

    /usr/local/share/ca-certificates/intca.crt:
      x509.pem_managed:
        - text: {{ salt['mine.get']('ca', 'x509.get_pem_entries')['ca']['/etc/pki/ca.crt']|replace('\\n', '') }}


This state creates a private key then requests a certificate signed by ca according to the www policy.

/srv/salt/www.sls

.. code-block:: yaml

    /etc/pki/www.key:
      x509.private_key_managed:
        - bits: 4096

    /etc/pki/www.crt:
      x509.certificate_managed:
        - ca_server: ca
        - signing_policy: www
        - public_key: /etc/pki/www.key
        - CN: www.example.com
        - days_remaining: 30
        - backup: True

'''

# Import Python Libs
from __future__ import absolute_import
import datetime
import os
import re
import copy

# Import Salt Libs
import salt.exceptions
import salt.utils

# Import 3rd-party libs
import salt.ext.six as six


def __virtual__():
    '''
    only load this module if the corresponding execution module is loaded
    '''
    if 'x509.get_pem_entry' in __salt__:
        return 'x509'
    else:
        return (False, 'Could not load x509 state: m2crypto unavailable')


def _revoked_to_list(revs):
    '''
    Turn the mess of OrderedDicts and Lists into a list of dicts for
    use in the CRL module.
    '''
    list_ = []

    for rev in revs:
        for rev_name, props in six.iteritems(rev):             # pylint: disable=unused-variable
            dict_ = {}
            for prop in props:
                for propname, val in six.iteritems(prop):
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
        Combining new with :mod:`prereq <salt.states.requsities.preqreq>` can allow key rotation
        whenever a new certificiate is generated.

    backup:
        When replacing an existing file, backup the old file onthe minion.
        Default is False.

    Example:

    The jinja templating in this example ensures a private key is generated if the file doesn't exist
    and that a new private key is generated whenever the certificate that uses it is to be renewed.

    .. code-block:: yaml

        /etc/pki/www.key:
          x509.private_key_managed:
            - bits: 4096
            - new: True
            {% if salt['file.file_exists']('/etc/pki/ca.key') -%}
            - prereq:
              - x509: /etc/pki/www.crt
            {%- endif %}
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

    if __opts__['test'] is True:
        ret['result'] = None
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
            'new': new, }

    if __opts__['test'] is True:
        ret['result'] = None
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

    days_remaining:
        The minimum number of days remaining when the certificate should be recreated. Default is 90. A
        value of 0 disables automatic renewal.

    backup:
        When replacing an existing file, backup the old file on the minion. Default is False.

    kwargs:
        Any arguments supported by :mod:`x509.create_certificate <salt.modules.x509.create_certificate>`
        are supported.

    Examples:

    .. code-block:: yaml

        /etc/pki/ca.crt:
          x509.certificate_managed:
            - signing_private_key: /etc/pki/ca.key
            - CN: ca.example.com
            - C: US
            - ST: Utah
            - L: Salt Lake City
            - basicConstraints: "critical CA:true"
            - keyUsage: "critical cRLSign, keyCertSign"
            - subjectKeyIdentifier: hash
            - authorityKeyIdentifier: keyid,issuer:always
            - days_valid: 3650
            - days_remaining: 0
            - backup: True


    .. code-block:: yaml

        /etc/ssl/www.crt:
          x509.certificate_managed:
            - ca_server: pki
            - signing_policy: www
            - public_key: /etc/ssl/www.key
            - CN: www.example.com
            - days_valid: 90
            - days_remaining: 30
            - backup: True

    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    current_days_remaining = 0
    current_comp = {}

    if os.path.isfile(name):
        try:
            current = __salt__['x509.read_certificate'](certificate=name)
            current_comp = copy.deepcopy(current)
            if 'serial_number' not in kwargs:
                current_comp.pop('Serial Number')
                if 'signing_cert' not in kwargs:
                    try:
                        current_comp['X509v3 Extensions']['authorityKeyIdentifier'] = (
                            re.sub(r'serial:([0-9A-F]{2}:)*[0-9A-F]{2}', 'serial:--',
                                current_comp['X509v3 Extensions']['authorityKeyIdentifier']))
                    except KeyError:
                        pass
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

    if 'ca_server' in kwargs and 'signing_policy' not in kwargs:
        raise salt.exceptions.SaltInvocationError('signing_policy must be specified if ca_server is.')

    new = __salt__['x509.create_certificate'](testrun=True, **kwargs)

    if isinstance(new, dict):
        new_comp = copy.deepcopy(new)
        new.pop('Issuer Public Key')
        if 'serial_number' not in kwargs:
            new_comp.pop('Serial Number')
            if 'signing_cert' not in kwargs:
                try:
                    new_comp['X509v3 Extensions']['authorityKeyIdentifier'] = (
                        re.sub(r'serial:([0-9A-F]{2}:)*[0-9A-F]{2}', 'serial:--',
                            new_comp['X509v3 Extensions']['authorityKeyIdentifier']))
                except KeyError:
                    pass
        new_comp.pop('Not Before')
        new_comp.pop('Not After')
        new_comp.pop('MD5 Finger Print')
        new_comp.pop('SHA1 Finger Print')
        new_comp.pop('SHA-256 Finger Print')
        new_issuer_public_key = new_comp.pop('Issuer Public Key')
    else:
        new_comp = new

    if (current_comp == new_comp and
            current_days_remaining > days_remaining and
            __salt__['x509.verify_signature'](name, new_issuer_public_key)):
        ret['result'] = True
        ret['comment'] = 'The certificate is already in the correct state'
        return ret

    ret['changes'] = {
            'old': current,
            'new': new, }

    if __opts__['test'] is True:
        ret['result'] = None
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

    if (current_comp == new_comp and
            current_days_remaining > days_remaining and
            __salt__['x509.verify_crl'](name, signing_cert)):

        ret['result'] = True
        ret['comment'] = 'The crl is already in the correct state'
        return ret

    ret['changes'] = {
            'old': current,
            'new': new, }

    if __opts__['test'] is True:
        ret['result'] = None
        ret['comment'] = 'The crl {0} will be updated.'.format(name)
        return ret

    if os.path.isfile(name) and backup:
        bkroot = os.path.join(__opts__['cachedir'], 'file_backup')
        salt.utils.backup_minion(name, bkroot)

    ret['comment'] = __salt__['x509.write_pem'](text=new_crl, path=name, pem_type='X509 CRL')
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

    ret['changes']['new'] = new
    ret['changes']['old'] = current

    if __opts__['test'] is True:
        ret['result'] = None
        ret['comment'] = 'The file {0} will be updated.'.format(name)
        return ret

    if os.path.isfile(name) and backup:
        bkroot = os.path.join(__opts__['cachedir'], 'file_backup')
        salt.utils.backup_minion(name, bkroot)

    ret['comment'] = __salt__['x509.write_pem'](text=text, path=name)
    ret['result'] = True

    return ret
