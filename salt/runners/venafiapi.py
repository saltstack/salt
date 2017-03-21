# -*- coding: utf-8 -*-
'''
Support for Venafi

Before using this module you need to register an account with Venafi, and
configure it in your ``master`` configuration file.

First, you need to add a placeholder to the ``master`` file. This is because
the module will not load unless it finds an ``api_key`` setting, valid or not.
Open up ``/etc/salt/master`` and add:

.. code-block:: yaml

    api_key: None

Then register your email address with Venagi using the following command:

.. code-block:: bash

    salt-run venafi.register <youremail@yourdomain.com>

This command will not return an ``api_key`` to you; that will be sent to you
via email from Venafi. Once you have received that key, open up your ``master``
file and set the ``api_key`` to it:

.. code-block:: yaml

    api_key: abcdef01-2345-6789-abcd-ef0123456789
'''
from __future__ import absolute_import
import os
import logging
import tempfile
from Crypto.PublicKey import RSA
import json
import salt.syspaths as syspaths
import salt.cache
import salt.utils
import salt.utils.http
import salt.ext.six as six
from salt.exceptions import CommandExecutionError

__virtualname__ = 'venafi'
base_url = 'http://vpc-51255c36.qa.projectc.venafi.com/v1'
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load the module if venafi is installed
    '''
    if __opts__.get('venafi', {}).get('api_key'):
        return __virtualname__
    return False


def _api_key():
    '''
    Return the API key
    '''
    return __opts__.get('venafi', {}).get('api_key', '')


def gen_key(minion_id, dns_name=None, zone='default', password=None):
    '''
    Generate and return an private_key. If a ``dns_name`` is passed in, the
    private_key will be cached under that name. The type of key and the
    parameters used to generate the key are based on the default certificate
    use policy associated with the specified zone.

    CLI Example:

    .. code-block:: bash

        salt-run venafi.gen_key <minion_id> [dns_name] [zone] [password]
    '''
    # Get the default certificate use policy associated with the zone
    # so we can generate keys that conform with policy

    # The /v1/zones/tag/{name} API call is a shortcut to get the zoneID
    # directly from the name

    qdata = salt.utils.http.query(
        '{0}/zones/tag/{1}'.format(base_url,zone),
        method='GET',
        decode=True,
        decode_type='json',
        header_dict={
            'tppl-api-key': _api_key(),
            'Content-Type': 'application/json',
        },
    )

    zone_id = qdata['dict']['id']

    # the /v1/certificatepolicies?zoneId API call returns the default
    # certificate use and certificate identity policies

    qdata = salt.utils.http.query(
        '{0}/certificatepolicies?zoneId={1}'.format(base_url,zone_id),
        method='GET',
        decode=True,
        decode_type='json',
        header_dict={
            'tppl-api-key': _api_key(),
            'Content-Type': 'application/json',
        },
    )

    policies = qdata['dict']['certificatePolicies']

    # Extract the key length and key type from the certificate use policy
    # and generate the private key accordingly

    for policy in policies:
        if policy['certificatePolicyType'] == "CERTIFICATE_USE":
            keyTypes = policy['keyTypes']
            # in case multiple keytypes and key lengths are supported
            # always use the first key type and key length
            keygen_type =  keyTypes[0]['keyType']
            key_len = keyTypes[0]['keyLengths'][0] 

    if keygen_type == "RSA":
        gen = RSA.generate(bits=key_len)
        private_key = gen.exportKey('PEM', password)
        if dns_name is not None:
            bank = 'venafi/domains'
            cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
            try:
                data = cache.fetch(bank, dns_name)
                data['private_key'] = private_key
                data['minion_id'] = minion_id
            except TypeError:
                data = {'private_key': private_key,
                        'minion_id': minion_id}
            cache.store(bank, dns_name, data)
    return private_key


def gen_csr(
        minion_id,
        dns_name,
        zone='default',
        country=None,
        state=None,
        loc=None,
        org=None,
        org_unit=None,
        password=None,
    ):
    '''
    Generate a csr using the host's private_key.
    Analogous to:

    .. code-block:: bash

        VCert gencsr -cn [CN Value] -o "Beta Organization" -ou "Beta Group" \
            -l "Palo Alto" -st "California" -c US

    CLI Example:

    .. code-block:: bash

        salt-run venafi.gen_csr <minion_id> <dns_name>
    '''
    tmpdir = tempfile.mkdtemp()
    os.chmod(tmpdir, 0o700)

    bank = 'venafi/domains'
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    data = cache.fetch(bank, dns_name)
    if data is None:
        data = {}
    if 'private_key' not in data:
        data['private_key'] = gen_key(minion_id, dns_name, zone, password)

    tmppriv = '{0}/priv'.format(tmpdir)
    tmpcsr = '{0}/csr'.format(tmpdir)
    with salt.utils.fopen(tmppriv, 'w') as if_:
        if_.write(data['private_key'])

    if country is None:
        country = __opts__.get('venafi', {}).get('country')

    if state is None:
        state = __opts__.get('venafi', {}).get('state')

    if loc is None:
        loc = __opts__.get('venafi', {}).get('loc')

    if org is None:
        org = __opts__.get('venafi', {}).get('org')

    if org_unit is None:
        org_unit = __opts__.get('venafi', {}).get('org_unit')

    subject = '/C={0}/ST={1}/L={2}/O={3}/OU={4}/CN={5}'.format(
        country,
        state,
        loc,
        org,
        org_unit,
        dns_name,
    )

    cmd = "openssl req -new -sha256 -key {0} -out {1} -subj '{2}'".format(
        tmppriv,
        tmpcsr,
        subject
    )
    output = __salt__['salt.cmd']('cmd.run', cmd)

    if 'problems making Certificate Request' in output:
        raise CommandExecutionError(
            'There was a problem generating the CSR. Please ensure that you '
            'have the following variables set either on the command line, or '
            'in the venafi section of your master configuration file: '
            'country, state, loc, org, org_unit'
        )

    with salt.utils.fopen(tmpcsr, 'r') as of_:
        csr = of_.read()

    data['minion_id'] = minion_id
    data['csr'] = csr
    cache.store(bank, dns_name, data)
    return csr


def request(
        minion_id,
        dns_name=None,
        zone='default',
        request_id=None,
        country='US',
        state='California',
        loc='Palo Alto',
        org='Beta Organization',
        org_unit='Beta Group',
        password=None,
        zone_id=None,
    ):
    '''
    Request a new certificate

    Uses the following command:

    .. code-block:: bash

        VCert enroll -z <zone> -k <api key> -cn <domain name>

    CLI Example:

    .. code-block:: bash

        salt-run venafi.request <minion_id> <dns_name>
    '''
    if password is not None:
        if password.startswith('sdb://'):
            password = __salt__['sdb.get'](password)

    if zone_id is None:
        zone_id = __opts__.get('venafi', {}).get('zone_id')

    if zone_id is None and zone is not None:
        zone_id = get_zone_id(zone)
    
    if zone_id is None:
        raise CommandExecutionError(
            'Either a zone or a zone_id must be passed in or '
            'configured in the master file. This id can be retreived using '
            'venafi.show_company <domain>'
        )

    private_key = gen_key(minion_id, dns_name, zone, password)

    csr = gen_csr(
        minion_id,
        dns_name,
        zone=zone,
        country=country,
        state=state,
        loc=loc,
        org=org,
        org_unit=org_unit,
    )

    pdata = json.dumps({
        'zoneId': zone_id,
        'certificateSigningRequest': csr,
    })

    qdata = salt.utils.http.query(
        '{0}/certificaterequests'.format(base_url),
        method='POST',
        data=pdata,
        decode=True,
        decode_type='json',
        header_dict={
            'tppl-api-key': _api_key(),
            'Content-Type': 'application/json',
        },
    )

    request_id = qdata['dict']['certificateRequests'][0]['id']
    ret = {
        'request_id': request_id,
        'private_key': private_key,
        'csr': csr,
        'zone': zone,
    }

    bank = 'venafi/domains'
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    data = cache.fetch(bank, dns_name)
    if data is None:
        data = {}
    data.update({
        'minion_id': minion_id,
        'request_id': request_id,
        'private_key': private_key,
        'zone': zone,
        'csr': csr,
    })
    cache.store(bank, dns_name, data)
    _id_map(minion_id, dns_name)

    return ret


# Request and renew are the same, so far as this module is concerned
renew = request


def _id_map(minion_id, dns_name):
    '''
    Maintain a relationship between a minion and a dns name
    '''
    bank = 'venafi/minions'
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    dns_names = cache.fetch(bank, minion_id)
    if dns_names is None:
        dns_names = []
    if dns_name not in dns_names:
        dns_names.append(dns_name)
    cache.store(bank, minion_id, dns_names)


def register(email):
    '''
    Register a new user account

    CLI Example:

    .. code-block:: bash

        salt-run venafi.register email@example.com
    '''
    data = salt.utils.http.query(
        '{0}/useraccounts'.format(base_url),
        method='POST',
        data=json.dumps({
            'username': email,
            'userAccountType': 'API',
        }),
        status=True,
        decode=True,
        decode_type='json',
        header_dict={
            'Content-Type': 'application/json',
        },
    )
    status = data['status']
    if str(status).startswith('4') or str(status).startswith('5'):
        raise CommandExecutionError(
            'There was an API error: {0}'.format(data['error'])
        )
    return data.get('dict', {})


def show_company(domain):
    '''
    Show company information, especially the company id

    CLI Example:

    .. code-block:: bash

        salt-run venafi.show_company example.com
    '''
    data = salt.utils.http.query(
        '{0}/companies/domain/{1}'.format(base_url, domain),
        status=True,
        decode=True,
        decode_type='json',
        header_dict={
            'tppl-api-key': _api_key(),
        },
    )
    status = data['status']
    if str(status).startswith('4') or str(status).startswith('5'):
        raise CommandExecutionError(
            'There was an API error: {0}'.format(data['error'])
        )
    return data.get('dict', {})


def show_csrs():
    '''
    Show certificate requests for this API key

    CLI Example:

    .. code-block:: bash

        salt-run venafi.show_csrs
    '''
    data = salt.utils.http.query(
        '{0}/certificaterequests'.format(base_url),
        status=True,
        decode=True,
        decode_type='json',
        header_dict={
            'tppl-api-key': _api_key(),
        },
    )
    status = data['status']
    if str(status).startswith('4') or str(status).startswith('5'):
        raise CommandExecutionError(
            'There was an API error: {0}'.format(data['error'])
        )
    return data.get('dict', {})

def get_zone_id(zone_name):
    '''
    Get the zone ID for the given zone name

    CLI Example:

    .. code-block:: bash

        salt-run venafi.get_zone_id default
    '''
    data = salt.utils.http.query(
        '{0}/zones/tag/{1}'.format(base_url,zone_name),
        status=True,
        decode=True,
        decode_type='json',
        header_dict={
            'tppl-api-key': _api_key(),
        },
    )

    status = data['status']
    if str(status).startswith('4') or str(status).startswith('5'):
        raise CommandExecutionError(
            'There was an API error: {0}'.format(data['error'])
        )
    return data['dict']['id']


def show_zones():
    '''
    Show zone details for the API key owner's company

    CLI Example:

    .. code-block:: bash

        salt-run venafi.show_zones
    '''
    data = salt.utils.http.query(
        '{0}/zones'.format(base_url),
        status=True,
        decode=True,
        decode_type='json',
        header_dict={
            'tppl-api-key': _api_key(),
        },
    )
    status = data['status']
    if str(status).startswith('4') or str(status).startswith('5'):
        raise CommandExecutionError(
            'There was an API error: {0}'.format(data['error'])
        )
    return data['dict']


def show_cert(id_):
    '''
    Show certificate requests for this API key

    CLI Example:

    .. code-block:: bash

        salt-run venafi.show_cert 01234567-89ab-cdef-0123-456789abcdef
    '''
    data = salt.utils.http.query(
        '{0}/certificaterequests/{1}/certificate'.format(base_url, id_),
        params={
            'format': 'PEM',
            'chainOrder': 'ROOT_FIRST'
        },
        status=True,
        text=True,
        header_dict={'tppl-api-key': _api_key()},
    )
    status = data['status']
    if str(status).startswith('4') or str(status).startswith('5'):
        raise CommandExecutionError(
            'There was an API error: {0}'.format(data['error'])
        )
    data = data.get('body', '')
    csr_data = salt.utils.http.query(
        '{0}/certificaterequests/{1}'.format(base_url, id_),
        status=True,
        decode=True,
        decode_type='json',
        header_dict={'tppl-api-key': _api_key()},
    )
    status = csr_data['status']
    if str(status).startswith('4') or str(status).startswith('5'):
        raise CommandExecutionError(
            'There was an API error: {0}'.format(csr_data['error'])
        )
    csr_data = csr_data.get('dict', {})
    certs = _parse_certs(data)
    dns_name = ''
    for item in csr_data['certificateName'].split(','):
        if item.startswith('cn='):
            dns_name = item.split('=')[1]
    #certs['CSR Data'] = csr_data

    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    domain_data = cache.fetch('venafi/domains', dns_name)
    if domain_data is None:
        domain_data = {}
    certs['private_key'] = domain_data.get('private_key')
    domain_data.update(certs)
    cache.store('venafi/domains', dns_name, domain_data)

    certs['request_id'] = id_
    return certs


pickup = show_cert


def show_rsa(minion_id, dns_name):
    '''
    Show a private RSA key

    CLI Example:

    .. code-block:: bash

        salt-run venafi.show_rsa myminion domain.example.com
    '''
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    bank = 'venafi/domains'
    data = cache.fetch(
        bank, dns_name
    )
    return data['private_key']


def list_domain_cache():
    '''
    List domains that have been cached

    CLI Example:

    .. code-block:: bash

        salt-run venafi.list_domain_cache
    '''
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    return cache.list('venafi/domains')


def del_cached_domain(domains):
    '''
    Delete cached domains from the master

    CLI Example:

    .. code-block:: bash

        salt-run venafi.del_cached_domain domain1.example.com,domain2.example.com
    '''
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    if isinstance(domains, six.string_types):
        domains = domains.split(',')
    if not isinstance(domains, list):
        raise CommandExecutionError(
            'You must pass in either a string containing one or more domains '
            'separated by commas, or a list of single domain strings'
        )
    success = []
    failed = []
    for domain in domains:
        try:
            cache.flush('venafi/domains', domain)
            success.append(domain)
        except CommandExecutionError:
            failed.append(domain)
    return {'Succeeded': success, 'Failed': failed}


def _parse_certs(data):
    cert_mode = False
    cert = ''
    certs = []
    rsa_key = ''
    for line in data.splitlines():
        if not line.strip():
            continue
        if 'Successfully posted request' in line:
            comps = line.split(' for ')
            request_id = comps[-1].strip()
            continue
        if 'END CERTIFICATE' in line or 'END RSA private_key' in line:
            if 'RSA' in line:
                rsa_key = rsa_key + line
            else:
                cert = cert + line
            certs.append(cert)
            cert_mode = False
            continue
        if 'BEGIN CERTIFICATE' in line or 'BEGIN RSA private_key' in line:
            if 'RSA' in line:
                rsa_key = line + '\n'
            else:
                cert = line + '\n'
            cert_mode = True
            continue
        if cert_mode is True:
            cert = cert + line + '\n'
            continue

    rcert = certs.pop(0)
    eecert = certs.pop(-1)
    ret = {
        'end_entity_certificate': eecert,
        'private_key': rsa_key,
        'root_certificate': rcert,
        'intermediate_certificates': certs
    }

    return ret
