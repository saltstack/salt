# -*- coding: utf-8 -*-
'''
Support for Venafi

Before using this module you need to register an account with Venafi, and
configure it in your ``master`` configuration file.

First, you need to add a placeholder to the ``master`` file. This is because
the module will not load unless it finds an ``api_key`` setting, valid or not.
Open up ``/etc/salt/master`` and add:

.. code-block:: yaml

    venafi:
      api_key: None

Then register your email address with Venafi using the following command:

.. code-block:: bash

    salt-run venafi.register <youremail@yourdomain.com>

This command will not return an ``api_key`` to you; that will be sent to you
via email from Venafi. Once you have received that key, open up your ``master``
file and set the ``api_key`` to it:

.. code-block:: yaml

    venafi:
      api_key: abcdef01-2345-6789-abcd-ef0123456789
'''
from __future__ import absolute_import, print_function, unicode_literals
import logging
import time
import tempfile

try:
    from M2Crypto import RSA
    HAS_M2 = True
except ImportError:
    HAS_M2 = False
    try:
        from Cryptodome.PublicKey import RSA
    except ImportError:
        from Crypto.PublicKey import RSA

# Import Salt libs
import salt.cache
import salt.syspaths as syspaths
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

# Import 3rd-party libs
from salt.ext import six
import vcert


CACHE_BANK_NAME = 'venafi/domains'
__virtualname__ = 'venafi'
log = logging.getLogger(__name__)


def _init_connection():
    log.info("init venafi connection")
    api_key = __opts__.get('venafi', {}).get('api_key')
    base_url = __opts__.get('venafi', {}).get('base_url')
    tpp_user = __opts__.get('venafi', {}).get('tpp_user')
    tpp_password = __opts__.get('venafi', {}).get('tpp_password')
    return vcert.Connection(url=base_url, token=api_key, user=tpp_user, password=tpp_password)

def __virtual__():
    '''
    Only load the module if venafi is installed
    '''
    return __virtualname__


def request(
        minion_id,
        dns_name=None,
        zone='Default',
        country='US',
        state='California',
        loc='Palo Alto',
        org='Venafi',
        org_unit='Beta Group',
        password=None,
    ):
    '''
    Request a new certificate

    CLI Example:

    .. code-block:: bash

        salt-run venafi.request <minion_id> <dns_name>
    '''
    if password is not None:
        if password.startswith('sdb://'):
            password = __salt__['sdb.get'](password)
    conn = _init_connection()
    request = vcert.common.CertificateRequest(common_name=dns_name, country=country, province=state, locality=loc,
                                              organization=org, organizational_unit=org_unit, key_password=password)
    zone_config = conn.read_zone_conf(zone)
    request.update_from_zone_config(zone_config)
    conn.request_cert(request, zone)
    csr = request.csr
    private_key = request.private_key_pem
    while True:
        time.sleep(5)
        cert = conn.retrieve_cert(request)
        if cert:
            break

    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    data = {
        'minion_id': minion_id,
        'cert': cert.cert,
        'chain': cert.chain
    }
    cache.store(CACHE_BANK_NAME, dns_name, data)
    return cert.cert, private_key


# Request and renew are the same, so far as this module is concerned
renew = request


def _id_map(minion_id, dns_name):
    '''
    Maintain a relationship between a minion and a dns name
    '''

    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    dns_names = cache.fetch(CACHE_BANK_NAME, minion_id)
    if not isinstance(dns_names, list):
        dns_names = []
    if dns_name not in dns_names:
        dns_names.append(dns_name)
    cache.store(CACHE_BANK_NAME, minion_id, dns_names)


def show_cert(dns_name):
    '''
    Show issued certificate for domain

    CLI Example:

    .. code-block:: bash

        salt-run venafi.show_cert example.com
    '''

    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    domain_data = cache.fetch(CACHE_BANK_NAME, dns_name) or {}
    cert = domain_data.get('cert')
    return cert


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
            cache.flush(CACHE_BANK_NAME, domain)
            success.append(domain)
        except CommandExecutionError:
            failed.append(domain)
    return {'Succeeded': success, 'Failed': failed}
