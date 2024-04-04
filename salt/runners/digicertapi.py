"""
Support for Digicert.  Heavily based on the Venafi runner by Joseph Hall (jphall@saltstack.com).

Before using this module you need to register an account with Digicert's CertCentral.

Login to CertCentral, ensure you have a payment method configured and/or there are adequate
funds attached to your account.  Click the ``Account`` item in the left sidebar, and select
``Account Access``.  The right hand pane should show "Account Access" and a link to create
an API key.  Create a new API key and assign it to the user that should be attached to requests
coming from Salt.

NOTE CertCentral will not show the API key again after revealing it the first time.  Make sure
you copy it right away or you will have to revoke it and generate a new one.

Now open ``/etc/salt/master`` and add the API key as shown below.

.. code-block:: yaml

    digicert:
      api_key: ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABC


Restart your Salt Master.

You can also include default values of the following variables to help with creating CSRs:

.. code-block:: yaml

    digicert:
      api_key: ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZABC
      shatype: sha256

This API currently only supports RSA key types.  Support for other key types will be added
if interest warrants.

"""

import logging
import os
import re
import subprocess
import tempfile
from collections.abc import Sequence

import salt.cache
import salt.syspaths as syspaths
import salt.utils.files
import salt.utils.http
import salt.utils.json
from salt.exceptions import CommandExecutionError, SaltRunnerError

try:
    from M2Crypto import RSA

    HAS_M2 = True
except ImportError:
    HAS_M2 = False
    try:
        from Cryptodome.PublicKey import RSA
    except ImportError:
        from Crypto.PublicKey import RSA  # nosec

__virtualname__ = "digicert"
log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load the module if digicert has configuration in place
    """
    if __opts__.get("digicert", {}).get("api_key"):
        return __virtualname__
    return False


def _base_url():
    """
    Return the base_url
    """
    return __opts__.get("digicert", {}).get(
        "base_url", "https://www.digicert.com/services/v2/"
    )


def _api_key():
    """
    Return the API key
    """
    return __opts__.get("digicert", {}).get("api_key", "")


def _paginate(url, topkey, *args, **kwargs):
    """
    Wrapper to assist with paginated responses from Digicert's REST API.
    """

    ret = salt.utils.http.query(url, **kwargs)
    if "errors" in ret["dict"]:
        return ret["dict"]

    lim = int(ret["dict"]["page"]["limit"])
    total = int(ret["dict"]["page"]["total"])

    if total == 0:
        return {}

    numpages = (total / lim) + 1

    # If the count returned is less than the page size, just return the dict
    if numpages == 1:
        return ret["dict"][topkey]

    aggregate_ret = ret["dict"][topkey]
    url = args[0]
    for p in range(2, numpages):
        param_url = url + f"?offset={lim * (p - 1)}"
        next_ret = salt.utils.http.query(param_url, kwargs)
        aggregate_ret[topkey].extend(next_ret["dict"][topkey])

    return aggregate_ret


def list_domains(container_id=None):
    """
    List domains that CertCentral knows about. You can filter by
    container_id (also known as "Division") by passing a container_id.

    CLI Example:

    .. code-block:: bash

        salt-run digicert.list_domains
    """
    if container_id:
        url = f"{_base_url()}/domain?{container_id}"
    else:
        url = f"{_base_url()}/domain"

    orgs = _paginate(
        url,
        "domains",
        method="GET",
        decode=True,
        decode_type="json",
        header_dict={"X-DC-DEVKEY": _api_key(), "Content-Type": "application/json"},
    )

    ret = {"domains": orgs}
    return ret


def list_requests(status=None):
    """
    List certificate requests made to CertCentral. You can filter by
    status: ``pending``, ``approved``, ``rejected``

    CLI Example:

    .. code-block:: bash

        salt-run digicert.list_requests pending
    """
    if status:
        url = f"{_base_url()}/request?status={status}"
    else:
        url = f"{_base_url()}/request"

    reqs = _paginate(
        url,
        "requests",
        method="GET",
        decode=True,
        decode_type="json",
        raise_error=False,
        header_dict={"X-DC-DEVKEY": _api_key(), "Content-Type": "application/json"},
    )

    ret = {"requests": reqs}
    return ret


def list_orders(status=None):
    """
    List certificate orders made to CertCentral.

    CLI Example:

    .. code-block:: bash

        salt-run digicert.list_orders
    """
    url = f"{_base_url()}/order/certificate"

    reqs = _paginate(
        url,
        "orders",
        method="GET",
        decode=True,
        decode_type="json",
        raise_error=False,
        header_dict={"X-DC-DEVKEY": _api_key(), "Content-Type": "application/json"},
    )

    ret = {"orders": reqs}
    return ret


def get_certificate(
    order_id=None,
    certificate_id=None,
    minion_id=None,
    cert_format="pem_all",
    filename=None,
):
    """
    Retrieve a certificate by order_id or certificate_id and write it to stdout or a filename.

    A list of permissible cert_formats is here:
        https://www.digicert.com/services/v2/documentation/appendix-certificate-formats

    CLI Example:

    .. code-block:: bash

        salt-run digicert.get_certificate order_id=48929454 cert_format=apache

    Including a 'filename' will write the certificate to the desired file.
    Note that some cert formats are zipped files, and some are binary.

    If the certificate has not been issued, this function will return the order details
    inside of which will be a status (one of pending, rejected, processing, issued,
    revoked, canceled, needs_csr, and needs_approval)

    If for some reason you want to pipe the output of this command to a file or other
    command you will want to leave off the ``filename`` argument and make sure to include
    ``--no-color`` so there will be no terminal ANSI escape sequences.

    """

    if order_id:
        order_cert = salt.utils.http.query(
            f"{_base_url()}/order/certificate/{order_id}",
            method="GET",
            raise_error=False,
            decode=True,
            decode_type="json",
            header_dict={
                "X-DC-DEVKEY": _api_key(),
                "Content-Type": "application/json",
            },
        )
        if order_cert["dict"].get("status") != "issued":
            return {"certificate": order_cert["dict"]}

        if order_cert["dict"].get("errors", False):
            return {"certificate": order_cert["dict"]}

        certificate_id = order_cert["dict"].get("certificate").get("id", None)
        common_name = order_cert["dict"].get("certificate").get("common_name")

    if not certificate_id:
        return {
            "certificate": {
                "errors": {
                    "code": "unknown",
                    "message": (
                        "Unknown error, no certificate ID passed on command line or in"
                        " body returned from API"
                    ),
                }
            }
        }

    if filename:
        ret_cert = salt.utils.http.query(
            "{}/certificate/{}/download/format/{}".format(
                _base_url(), certificate_id, cert_format
            ),
            method="GET",
            decode=False,
            text=False,
            headers=True,
            text_out=filename,
            raise_error=False,
            header_dict={"X-DC-DEVKEY": _api_key()},
        )
    else:
        ret_cert = salt.utils.http.query(
            "{}/certificate/{}/download/format/{}".format(
                _base_url(), certificate_id, cert_format
            ),
            method="GET",
            text=False,
            decode=False,
            raise_error=False,
            header_dict={"X-DC-DEVKEY": _api_key()},
        )
    if "errors" in ret_cert:
        return {"certificate": ret_cert}

    if "body" not in ret_cert:
        ret = {"certificate": ret_cert}
        cert = ret_cert
    if isinstance(ret_cert, dict):
        ret = ret_cert["body"]
        cert = ret
    else:
        ret = ret_cert
        cert = ret

    tmpfilename = None
    if not filename:
        fd, tmpfilename = tempfile.mkstemp()
        filename = tmpfilename
        os.write(fd, cert)
        os.close(fd)

    cmd = [
        "openssl",
        "x509",
        "-noout",
        "-subject",
        "-nameopt",
        "multiline",
        "-in",
        filename,
    ]
    out = subprocess.check_output(cmd)
    common_name = None
    for l in out.splitlines():
        common_name_match = re.search(" *commonName *= *(.*)", l)
        if common_name_match:
            common_name = common_name_match.group(1)
            break
    if tmpfilename:
        os.unlink(tmpfilename)

    if common_name:
        bank = "digicert/domains"
        cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
        try:
            data = cache.fetch(bank, common_name)
        except TypeError:
            data = {"certificate": cert}
        cache.store(bank, common_name, data)

    if "headers" in ret_cert:
        return {
            "certificate": {
                "filename": filename,
                "original_filename": ret_cert["headers"].get(
                    "Content-Disposition", "Not provided"
                ),
                "Content-Type": ret_cert["headers"].get("Content-Type", "Not provided"),
            }
        }

    return {"certificate": cert}


def list_organizations(container_id=None, include_validation=True):
    """
    List organizations that CertCentral knows about. You can filter by
    container_id (also known as "Division") by passing a container_id.
    This function returns validation information by default; pass
    ``include_validation=False`` to turn it off.

    CLI Example:

    .. code-block:: bash

        salt-run digicert.list_organizations
    """

    orgs = _paginate(
        f"{_base_url()}/organization",
        "organizations",
        method="GET",
        decode=True,
        decode_type="json",
        header_dict={"X-DC-DEVKEY": _api_key(), "Content-Type": "application/json"},
    )

    ret = {"organizations": orgs}
    return ret


def order_certificate(
    minion_id,
    common_name,
    organization_id,
    validity_years,
    cert_key_passphrase=None,
    signature_hash=None,
    key_len=2048,
    dns_names=None,
    organization_units=None,
    server_platform=None,
    custom_expiration_date=None,
    comments=None,
    disable_renewal_notifications=False,
    product_type_hint=None,
    renewal_of_order_id=None,
):
    """
    Order a certificate.  Requires that an Organization has been created inside Digicert's CertCentral.

    See here for API documentation:
    https://www.digicert.com/services/v2/documentation/order/order-ssl-determinator

    CLI Example:

    .. code-block:: bash

        salt-run digicert.order_certificate my_minionid my.domain.com 10 \
            3 signature_hash=sha256 \
            dns_names=['this.domain.com', 'that.domain.com'] \
            organization_units='My Domain Org Unit' \
            comments='Comment goes here for the approver'

    This runner can also be used to renew a certificate by passing `renewal_of_order_id`.
    Previous order details can be retrieved with digicertapi.list_orders.
    """

    if dns_names and isinstance(dns_names, str):
        dns_names = [dns_names]
    if dns_names and not isinstance(dns_names, Sequence):
        raise SaltRunnerError(
            "order_certificate needs a single dns_name, or an array of dns_names."
        )
    certificate = {"common_name": common_name}
    certificate["dns_names"] = dns_names

    if signature_hash:
        certificate["signature_hash"] = signature_hash
    else:
        certificate["signature_hash"] = __opts__.get("digicert", {}).get(
            "shatype", "sha256"
        )

    body = {}

    if organization_units and isinstance(organization_units, str):
        organization_units = [organization_units]
    if organization_units and not isinstance(organization_units, Sequence):
        raise SaltRunnerError("Organization_units is not a valid data type.")
    if organization_units:
        certificate["organization_units"] = organization_units

    if organization_units:
        # Currently the Digicert API requires organization units to be an array
        # but only pays attention to the first one.
        csr = gen_csr(
            minion_id,
            common_name,
            organization_id,
            ou_name=organization_units[0],
            shatype=certificate["signature_hash"],
            key_len=key_len,
            password=cert_key_passphrase,
        )
    else:
        csr = gen_csr(
            minion_id,
            common_name,
            organization_id,
            shatype=certificate["signature_hash"],
            key_len=key_len,
            password=cert_key_passphrase,
        )

    certificate["csr"] = csr

    if server_platform:
        certificate["server_platform"]["id"] = server_platform

    body["organization"] = {"id": organization_id}

    if custom_expiration_date:
        body["custom_expiration_date"] = custom_expiration_date

    if validity_years:
        body["validity_years"] = validity_years

    if comments:
        body["comments"] = comments

    body["disable_renewal_notifications"] = disable_renewal_notifications

    if product_type_hint:
        body["product"] = {"type_hint": product_type_hint}
    if renewal_of_order_id:
        body["renewal_of_order_id"] = renewal_of_order_id

    body["certificate"] = certificate
    encoded_body = salt.utils.json.dumps(body)

    qdata = salt.utils.http.query(
        f"{_base_url()}/order/certificate/ssl",
        method="POST",
        data=encoded_body,
        decode=True,
        decode_type="json",
        header_dict={"X-DC-DEVKEY": _api_key(), "Content-Type": "application/json"},
        raise_error=False,
    )
    if "errors" not in qdata["dict"]:
        bank = "digicert/domains"
        cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
        data = cache.fetch(bank, common_name)
        if data is None:
            data = {}
        data.update(
            {
                "minion_id": minion_id,
                "order_id": qdata["dict"]["requests"][0]["id"],
                "csr": csr,
            }
        )
        cache.store(bank, common_name, data)
        _id_map(minion_id, common_name)

    return {"order": qdata["dict"]}


def gen_key(minion_id, dns_name=None, password=None, key_len=2048):
    """
    Generate and return a private_key. If a ``dns_name`` is passed in, the
    private_key will be cached under that name.

    CLI Example:

    .. code-block:: bash

        salt-run digicert.gen_key <minion_id> [dns_name] [password]
    """
    keygen_type = "RSA"

    if keygen_type == "RSA":
        if HAS_M2:
            gen = RSA.gen_key(key_len, 65537)
            private_key = gen.as_pem(
                cipher="des_ede3_cbc", callback=lambda x: bytes(password)
            )
        else:
            gen = RSA.generate(bits=key_len)
            private_key = gen.exportKey("PEM", password)
        if dns_name is not None:
            bank = "digicert/domains"
            cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
            try:
                data = cache.fetch(bank, dns_name)
                data["private_key"] = private_key
                data["minion_id"] = minion_id
            except TypeError:
                data = {"private_key": private_key, "minion_id": minion_id}
            cache.store(bank, dns_name, data)
    return private_key


def get_org_details(organization_id):
    """
    Return the details for an organization

    CLI Example:

    .. code-block:: bash

        salt-run digicert.get_org_details 34

    Returns a dictionary with the org details, or with 'error' and 'status' keys.
    """

    qdata = salt.utils.http.query(
        f"{_base_url()}/organization/{organization_id}",
        method="GET",
        decode=True,
        decode_type="json",
        header_dict={"X-DC-DEVKEY": _api_key(), "Content-Type": "application/json"},
    )
    return qdata


def gen_csr(
    minion_id,
    dns_name,
    organization_id,
    ou_name=None,
    key_len=2048,
    shatype="sha256",
    password=None,
):
    """

    CLI Example:

    .. code-block:: bash

        salt-run digicert.gen_csr <minion_id> <dns_name>
    """
    org_details = get_org_details(organization_id)

    if "error" in org_details:
        raise SaltRunnerError(
            "Problem getting organization details for organization_id={} ({})".format(
                organization_id, org_details["error"]
            )
        )
    if org_details["dict"].get("status", "active") == "inactive":
        raise SaltRunnerError(
            "Organization with organization_id={} is marked inactive".format(
                organization_id
            )
        )

    tmpdir = tempfile.mkdtemp()
    os.chmod(tmpdir, 0o700)

    bank = "digicert/domains"
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    data = cache.fetch(bank, dns_name)
    if data is None:
        data = {}
    if "private_key" not in data:
        data["private_key"] = gen_key(minion_id, dns_name, password, key_len=key_len)

    tmppriv = f"{tmpdir}/priv"
    tmpcsr = f"{tmpdir}/csr"
    with salt.utils.files.fopen(tmppriv, "w") as if_:
        if_.write(salt.utils.stringutils.to_str(data["private_key"]))

    subject = "/C={}/ST={}/L={}/O={}".format(
        org_details["dict"]["country"],
        org_details["dict"]["state"],
        org_details["dict"]["city"],
        org_details["dict"]["display_name"],
    )

    if ou_name:
        subject = subject + f"/OU={ou_name}"

    subject = subject + f"/CN={dns_name}"

    cmd = "openssl req -new -{} -key {} -out {} -subj '{}'".format(
        shatype, tmppriv, tmpcsr, subject
    )
    output = __salt__["salt.cmd"]("cmd.run", cmd)

    if "problems making Certificate Request" in output:
        raise CommandExecutionError(
            "There was a problem generating the CSR. Please ensure that you "
            "have a valid Organization established inside CertCentral"
        )

    with salt.utils.files.fopen(tmpcsr, "r") as of_:
        csr = salt.utils.stringutils.to_unicode(of_.read())

    data["minion_id"] = minion_id
    data["csr"] = csr
    cache.store(bank, dns_name, data)
    return csr


# Request and renew are the same, so far as this module is concerned
# renew = request


def _id_map(minion_id, dns_name):
    """
    Maintain a relationship between a minion and a dns name
    """
    bank = "digicert/minions"
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    dns_names = cache.fetch(bank, minion_id)
    if not isinstance(dns_names, list):
        dns_names = []
    if dns_name not in dns_names:
        dns_names.append(dns_name)
    cache.store(bank, minion_id, dns_names)


def show_organization(domain):
    """
    Show organization information, especially the company id

    CLI Example:

    .. code-block:: bash

        salt-run digicert.show_company example.com
    """
    data = salt.utils.http.query(
        f"{_base_url()}/companies/domain/{domain}",
        status=True,
        decode=True,
        decode_type="json",
        header_dict={"tppl-api-key": _api_key()},
    )
    status = data["status"]
    if str(status).startswith("4") or str(status).startswith("5"):
        raise CommandExecutionError("There was an API error: {}".format(data["error"]))
    return data.get("dict", {})


def show_csrs():
    """
    Show certificate requests for this API key

    CLI Example:

    .. code-block:: bash

        salt-run digicert.show_csrs
    """
    data = salt.utils.http.query(
        f"{_base_url()}/certificaterequests",
        status=True,
        decode=True,
        decode_type="json",
        header_dict={"tppl-api-key": _api_key()},
    )
    status = data["status"]
    if str(status).startswith("4") or str(status).startswith("5"):
        raise CommandExecutionError("There was an API error: {}".format(data["error"]))
    return data.get("dict", {})


def show_rsa(minion_id, dns_name):
    """
    Show a private RSA key

    CLI Example:

    .. code-block:: bash

        salt-run digicert.show_rsa myminion domain.example.com
    """
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    bank = "digicert/domains"
    data = cache.fetch(bank, dns_name)
    return data["private_key"]


def list_domain_cache():
    """
    List domains that have been cached

    CLI Example:

    .. code-block:: bash

        salt-run digicert.list_domain_cache
    """
    cache = salt.cache.Cache(__opts__, syspaths.CACHE_DIR)
    return cache.list("digicert/domains")


def del_cached_domain(domains):
    """
    Delete cached domains from the master

    CLI Example:

    .. code-block:: bash

        salt-run digicert.del_cached_domain domain1.example.com,domain2.example.com
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
            cache.flush("digicert/domains", domain)
            success.append(domain)
        except CommandExecutionError:
            failed.append(domain)
    return {"Succeeded": success, "Failed": failed}
