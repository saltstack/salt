"""
Support for Venafi

:depends: - vcert Python module

:configuration: In order to connect to Venafi services you need to specify it in
    Salt master configuration.
    Example for Venafi Cloud (using env variables):

    .. code-block:: yaml

    venafi:
        api_key: "sdb://osenv/CLOUDAPIKEY"

    Example for Venafi Platform (using env variables):

    .. code-block:: yaml

    venafi:
      base_url: "https://tpp.example.com/"
      tpp_user: admin
      tpp_password: "sdb://osenv/TPP_PASSWORD"
      trust_bundle: "/opt/venafi/bundle.pem"

"""

import logging
import sys
import time

import salt.cache
import salt.syspaths as syspaths
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError

try:
    import vcert
    from vcert.common import CertificateRequest

    HAS_VCERT = True
except ImportError:
    HAS_VCERT = False

CACHE_BANK_NAME = "venafi/domains"
__virtualname__ = "venafi"
log = logging.getLogger(__name__)


def _init_connection():
    log.info("Initializing Venafi Trust Platform or Venafi Cloud connection")
    api_key = __opts__.get("venafi", {}).get("api_key", "")
    base_url = __opts__.get("venafi", {}).get("base_url", "")
    log.info("Using base_url: %s", base_url)
    tpp_user = __opts__.get("venafi", {}).get("tpp_user", "")
    tpp_password = __opts__.get("venafi", {}).get("tpp_password", "")
    trust_bundle = __opts__.get("venafi", {}).get("trust_bundle", "")
    fake = __opts__.get("venafi", {}).get("fake", "")
    log.info("Finished config processing")
    if fake:
        return vcert.Connection(fake=True)
    elif trust_bundle:
        log.info("Will use trust bundle from file %s", trust_bundle)
        return vcert.Connection(
            url=base_url,
            token=api_key,
            user=tpp_user,
            password=tpp_password,
            http_request_kwargs={"verify": trust_bundle},
        )
    else:
        return vcert.Connection(
            url=base_url, token=api_key, user=tpp_user, password=tpp_password
        )


def __virtual__():
    """
    Only load the module if vcert module is installed
    """
    if HAS_VCERT:
        return __virtualname__
    return False


def request(
    minion_id,
    dns_name=None,
    zone=None,
    country=None,
    state=None,
    loc=None,
    org=None,
    org_unit=None,
    key_password=None,
    csr_path=None,
    pkey_path=None,
):
    """
    Request a new certificate

    CLI Example:

    .. code-block:: bash

        salt-run venafi.request <minion_id> <dns_name>
    """

    log.info("Requesting Venafi certificate")
    if zone is None:
        log.error("Missing zone parameter")
        sys.exit(1)

    if key_password is not None:
        if key_password.startswith("sdb://"):
            key_password = __salt__["sdb.get"](key_password)
    conn = _init_connection()

    if csr_path is None:
        request = CertificateRequest(
            common_name=dns_name,
            country=country,
            province=state,
            locality=loc,
            organization=org,
            organizational_unit=org_unit,
            key_password=key_password,
        )
        zone_config = conn.read_zone_conf(zone)
        log.info("Updating request from zone %s", zone_config)
        request.update_from_zone_config(zone_config)
    else:
        log.info("Will use generated CSR from %s", csr_path)
        log.info("Using CN %s", dns_name)
        try:
            with salt.utils.files.fopen(csr_path) as csr_file:
                csr = csr_file.read()
            request = CertificateRequest(csr=csr, common_name=dns_name)
        except Exception as e:
            raise Exception(
                "Unable to open file {file}: {excp}".format(file=csr_path, excp=e)
            )
    conn.request_cert(request, zone)

    # TODO: add timeout parameter here
    timeout_seconds = 300
    timeout = time.time() + timeout_seconds
    cert = None
    while cert is None and time.time() < timeout:
        cert = conn.retrieve_cert(request)
        if cert is None:
            time.sleep(5)

    if csr_path is None:
        private_key = request.private_key_pem
    else:
        if pkey_path:
            try:
                with salt.utils.files.fopen(pkey_path) as pkey_file:
                    private_key = pkey_file.read()
            except Exception as e:
                raise Exception(
                    "Unable to open file {file}: {excp}".format(file=pkey_path, excp=e)
                )
        else:
            private_key = None

    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    data = {
        "minion_id": minion_id,
        "cert": cert.cert,
        "chain": cert.chain,
        "pkey": private_key,
    }
    cache.store(CACHE_BANK_NAME, dns_name, data)
    return cert.cert, private_key


# Request and renew are the same, so far as this module is concerned
renew = request


def _id_map(minion_id, dns_name):
    """
    Maintain a relationship between a minion and a DNS name
    """

    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    dns_names = cache.fetch(CACHE_BANK_NAME, minion_id)
    if not isinstance(dns_names, list):
        dns_names = []
    if dns_name not in dns_names:
        dns_names.append(dns_name)
    cache.store(CACHE_BANK_NAME, minion_id, dns_names)


def show_cert(dns_name):
    """
    Show issued certificate for domain

    CLI Example:

    .. code-block:: bash

        salt-run venafi.show_cert example.com
    """

    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    domain_data = cache.fetch(CACHE_BANK_NAME, dns_name) or {}
    cert = domain_data.get("cert")
    return cert


def list_domain_cache():
    """
    List domains that have been cached

    CLI Example:

    .. code-block:: bash

        salt-run venafi.list_domain_cache
    """
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    return cache.list("venafi/domains")


def del_cached_domain(domains):
    """
    Delete cached domains from the master

    CLI Example:

    .. code-block:: bash

        salt-run venafi.del_cached_domain domain1.example.com,domain2.example.com
    """
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    if isinstance(domains, str):
        domains = domains.split(",")
    if not isinstance(domains, list):
        raise CommandExecutionError(
            "You must pass in either a string containing one or more domains "
            "separated by commas, or a list of single domain strings"
        )
    success = []
    failed = []
    for domain in domains:
        try:
            cache.flush(CACHE_BANK_NAME, domain)
            success.append(domain)
        except CommandExecutionError:
            failed.append(domain)
    return {"Succeeded": success, "Failed": failed}
