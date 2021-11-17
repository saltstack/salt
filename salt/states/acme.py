"""
ACME / Let's Encrypt certificate management state
=================================================

.. versionadded:: 2016.3

See also the module documentation

.. code-block:: yaml

    reload-gitlab:
      cmd.run:
        - name: gitlab-ctl hup

    dev.example.com:
      acme.cert:
        - aliases:
          - gitlab.example.com
        - email: acmemaster@example.com
        - webroot: /opt/gitlab/embedded/service/gitlab-rails/public
        - renew: 14
        - fire_event: acme/dev.example.com
        - onchanges_in:
          - cmd: reload-gitlab

"""

import logging

import salt.utils.dictdiffer

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only work when the ACME module agrees
    """
    if "acme.cert" in __salt__:
        return True
    return (False, "acme module could not be loaded")


def cert(
    name,
    aliases=None,
    email=None,
    webroot=None,
    test_cert=False,
    renew=None,
    keysize=None,
    server=None,
    owner="root",
    group="root",
    mode="0640",
    certname=None,
    preferred_challenges=None,
    tls_sni_01_port=None,
    tls_sni_01_address=None,
    http_01_port=None,
    http_01_address=None,
    dns_plugin=None,
    dns_plugin_credentials=None,
):
    """
    Obtain/renew a certificate from an ACME CA, probably Let's Encrypt.

    :param name: Common Name of the certificate (DNS name of certificate)
    :param aliases: subjectAltNames (Additional DNS names on certificate)
    :param email: e-mail address for interaction with ACME provider
    :param webroot: True or a full path to webroot. Otherwise use standalone mode
    :param test_cert: Request a certificate from the Happy Hacker Fake CA (mutually exclusive with 'server')
    :param renew: True/'force' to force a renewal, or a window of renewal before expiry in days
    :param keysize: RSA key bits
    :param server: API endpoint to talk to
    :param owner: owner of the private key file
    :param group: group of the private key file
    :param mode: mode of the private key file
    :param certname: Name of the certificate to save
    :param preferred_challenges: A sorted, comma delimited list of the preferred
                                 challenge to use during authorization with the
                                 most preferred challenge listed first.
    :param tls_sni_01_port: Port used during tls-sni-01 challenge. This only affects
                            the port Certbot listens on. A conforming ACME server
                            will still attempt to connect on port 443.
    :param tls_sni_01_address: The address the server listens to during tls-sni-01
                               challenge.
    :param http_01_port: Port used in the http-01 challenge. This only affects
                         the port Certbot listens on. A conforming ACME server
                         will still attempt to connect on port 80.
    :param https_01_address: The address the server listens to during http-01 challenge.
    :param dns_plugin: Name of a DNS plugin to use (currently only 'cloudflare')
    :param dns_plugin_credentials: Path to the credentials file if required by the specified DNS plugin
    """

    if certname is None:
        certname = name

    ret = {"name": certname, "result": "changeme", "comment": [], "changes": {}}
    action = None

    current_certificate = {}
    new_certificate = {}
    if not __salt__["acme.has"](certname):
        action = "obtain"
    elif __salt__["acme.needs_renewal"](certname, renew):
        action = "renew"
        current_certificate = __salt__["acme.info"](certname)
    else:
        ret["result"] = True
        ret["comment"].append(
            "Certificate {} exists and does not need renewal.".format(certname)
        )

    if action:
        if __opts__["test"]:
            ret["result"] = None
            ret["comment"].append(
                "Certificate {} would have been {}ed.".format(certname, action)
            )
            ret["changes"] = {"old": "current certificate", "new": "new certificate"}
        else:
            res = __salt__["acme.cert"](
                name,
                aliases=aliases,
                email=email,
                webroot=webroot,
                certname=certname,
                test_cert=test_cert,
                renew=renew,
                keysize=keysize,
                server=server,
                owner=owner,
                group=group,
                mode=mode,
                preferred_challenges=preferred_challenges,
                tls_sni_01_port=tls_sni_01_port,
                tls_sni_01_address=tls_sni_01_address,
                http_01_port=http_01_port,
                http_01_address=http_01_address,
                dns_plugin=dns_plugin,
                dns_plugin_credentials=dns_plugin_credentials,
            )
            ret["result"] = res["result"]
            ret["comment"].append(res["comment"])
            if ret["result"]:
                new_certificate = __salt__["acme.info"](certname)
            ret["changes"] = salt.utils.dictdiffer.deep_diff(
                current_certificate, new_certificate
            )
    return ret
