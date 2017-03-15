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

    salt-run venefi.register <youremail@yourdomain.com>

This command will not return an ``api_key`` to you; that will be send to you
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
base_url = 'https://api.beta.venafi.com/v1'
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


def gen_rsa(minion_id, dns_name=None, zone='default', password=None):
    '''
    Generate and return an RSA private_key. If a ``dns_name`` is passed in, the
    private_key will be cached under that name. 
    '''
    gen = RSA.generate(bits=2048)
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
    '''
    tmpdir = tempfile.mkdtemp()
    os.chmod(tmpdir, 0700)

    bank = 'venafi/domains'
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    data = cache.fetch(bank, dns_name)
    if data is None:
        data = {}
    if 'private_key' not in data:
        data['private_key'] = gen_rsa(minion_id, dns_name, zone, password)

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
        company_id=None,
        zone_id=None,
    ):
    '''
    Request a new certificate

    Uses the following command:

    .. code-block:: bash

        VCert enroll -z <zone> -k <api key> -cn <domain name>
    '''
    if password is not None:
        if password.startswith('sdb://'):
            password = __salt__['sdb.get'](password)

    if zone_id is None:
        zone_id = __opts__.get('venafi', {}).get('zone_id')

    if company_id is None:
        company_id = __opts__.get('venafi', {}).get('company_id')

    if zone_id is None and zone is not None and company_id is not None:
        zones = show_zones(company_id)
        for zoned in zones['zones']:
            if zoned['tag'] == zone:
                zone_id = zoned['id']

    if zone_id is None and company_id is None:
        raise CommandExecutionError(
            'A company_id and either a zone or a zone_id must be passed in or '
            'configured in the master file. This id can be retreived using '
            'venafi.show_company <domain>'
        )

    private_key = gen_rsa(minion_id, dns_name, zone, password)

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

    pdata=json.dumps({
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


def show_zones(company_id):
    '''
    Show certificate requests for this API key
    '''
    data = salt.utils.http.query(
        '{0}/companies/{1}/zones'.format(base_url, company_id),
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
    '''
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    return cache.list('venafi/domains')


def del_cached_domain(domains):
    '''
    List domains that have been cached
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
