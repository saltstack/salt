"""
ACME / Let's Encrypt module
===========================

.. versionadded:: 2016.3.0

This module currently looks for certbot script in the $PATH as
- certbot,
- lestsencrypt,
- certbot-auto,
- letsencrypt-auto
eventually falls back to /opt/letsencrypt/letsencrypt-auto

.. note::

    Installation & configuration of the Let's Encrypt client can for example be done using
    https://github.com/saltstack-formulas/letsencrypt-formula

.. warning::

    Be sure to set at least accept-tos = True in cli.ini!

Most parameters will fall back to cli.ini defaults if None is given.

DNS plugins
-----------

This module currently supports the CloudFlare certbot DNS plugin.  The DNS
plugin credentials file needs to be passed in using the
``dns_plugin_credentials`` argument.

Make sure the appropriate certbot plugin for the wanted DNS provider is
installed before using this module.

"""

import datetime
import logging
import os

import salt.utils.path
from salt.exceptions import SaltInvocationError

log = logging.getLogger(__name__)

LEA = salt.utils.path.which_bin(
    [
        "certbot",
        "letsencrypt",
        "certbot-auto",
        "letsencrypt-auto",
        "/opt/letsencrypt/letsencrypt-auto",
    ]
)
LE_LIVE = "/etc/letsencrypt/live/"

if salt.utils.platform.is_freebsd():
    LE_LIVE = "/usr/local" + LE_LIVE


def __virtual__():
    """
    Only work when letsencrypt-auto is installed
    """
    return (
        LEA is not None,
        "The ACME execution module cannot be loaded: letsencrypt-auto not installed.",
    )


def _cert_file(name, cert_type):
    """
    Return expected path of a Let's Encrypt live cert
    """
    return os.path.join(LE_LIVE, name, f"{cert_type}.pem")


def _expires(name):
    """
    Return the expiry date of a cert

    :rtype: datetime
    :return: Expiry date
    """
    cert_file = _cert_file(name, "cert")
    # Use the salt module if available
    if "tls.cert_info" in __salt__:
        expiry = __salt__["tls.cert_info"](cert_file).get("not_after", 0)
    # Cobble it together using the openssl binary
    else:
        openssl_cmd = f"openssl x509 -in {cert_file} -noout -enddate"
        # No %e format on my Linux'es here
        strptime_sux_cmd = f'date --date="$({openssl_cmd} | cut -d= -f2)" +%s'
        expiry = float(__salt__["cmd.shell"](strptime_sux_cmd, output_loglevel="quiet"))
        # expiry = datetime.datetime.strptime(expiry.split('=', 1)[-1], '%b %e %H:%M:%S %Y %Z')
    return datetime.datetime.fromtimestamp(expiry)


def _renew_by(name, window=None):
    """
    Date before a certificate should be renewed

    :param str name: Name of the certificate
    :param int window: days before expiry date to renew
    :rtype: datetime
    :return: First renewal date
    """
    expiry = _expires(name)
    if window is not None:
        expiry = expiry - datetime.timedelta(days=window)

    return expiry


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
    manual_auth_hook=None,
    manual_cleanup_hook=None,
):
    """
    Obtain/renew a certificate from an ACME CA, probably Let's Encrypt.

    :param name: Common Name of the certificate (DNS name of certificate)
    :param aliases: subjectAltNames (Additional DNS names on certificate)
    :param email: e-mail address for interaction with ACME provider
    :param webroot: True or a full path to use to use webroot. Otherwise use standalone mode
    :param test_cert: Request a certificate from the Happy Hacker Fake CA (mutually
        exclusive with 'server')
    :param renew: True/'force' to force a renewal, or a window of renewal before
        expiry in days
    :param keysize: RSA key bits
    :param server: API endpoint to talk to
    :param owner: owner of the private key file
    :param group: group of the private key file
    :param mode: mode of the private key file
    :param certname: Name of the certificate to save
    :param preferred_challenges: A sorted, comma delimited list of the preferred
        challenge to use during authorization with the most preferred challenge
        listed first.
    :param tls_sni_01_port: Port used during tls-sni-01 challenge. This only affects
        the port Certbot listens on. A conforming ACME server will still attempt
        to connect on port 443.
    :param tls_sni_01_address: The address the server listens to during tls-sni-01
        challenge.
    :param http_01_port: Port used in the http-01 challenge. This only affects
        the port Certbot listens on. A conforming ACME server will still attempt
        to connect on port 80.
    :param https_01_address: The address the server listens to during http-01 challenge.
    :param dns_plugin: Name of a DNS plugin to use (currently only 'cloudflare'
        or 'digitalocean')
    :param dns_plugin_credentials: Path to the credentials file if required by
        the specified DNS plugin
    :param dns_plugin_propagate_seconds: Number of seconds to wait for DNS propogations
        before asking ACME servers to verify the DNS record. (default 10)
    :param manual_auth_hook: Path to the manual authentication hook script.
    :param manual_cleanup_hook: Path to the manual cleanup or post-authentication hook script.
    :rtype: dict
    :return: Dictionary with 'result' True/False/None, 'comment' and certificate's
        expiry date ('not_after')

    CLI Example:

    .. code-block:: bash

        salt 'gitlab.example.com' acme.cert dev.example.com "[gitlab.example.com]" test_cert=True \
        renew=14 webroot=/opt/gitlab/embedded/service/gitlab-rails/public
    """

    cmd = [LEA, "certonly", "--non-interactive", "--agree-tos"]
    if certname is None:
        certname = name

    supported_dns_plugins = ["cloudflare"]

    cert_file = _cert_file(certname, "cert")
    if not __salt__["file.file_exists"](cert_file):
        log.debug("Certificate %s does not exist (yet)", cert_file)
        renew = False
    elif needs_renewal(certname, renew):
        log.debug("Certificate %s will be renewed", cert_file)
        cmd.append("--renew-by-default")
        renew = True
    if server:
        cmd.append(f"--server {server}")

    if certname:
        cmd.append(f"--cert-name {certname}")

    if test_cert:
        if server:
            return {
                "result": False,
                "comment": "Use either server or test_cert, not both",
            }
        cmd.append("--test-cert")

    if webroot:
        cmd.append("--authenticator webroot")
        if webroot is not True:
            cmd.append(f"--webroot-path {webroot}")
    elif dns_plugin in supported_dns_plugins:
        if dns_plugin == "cloudflare":
            cmd.append("--dns-cloudflare")
            cmd.append(f"--dns-cloudflare-credentials {dns_plugin_credentials}")
        else:
            return {
                "result": False,
                "comment": f"DNS plugin '{dns_plugin}' is not supported",
            }
    elif manual_auth_hook:
        cmd.append("--manual")
        cmd.append(f"--manual-auth-hook '{manual_auth_hook}'")
        if manual_cleanup_hook:
            cmd.append(f"--manual-cleanup-hook '{manual_cleanup_hook}'")
    else:
        cmd.append("--authenticator standalone")

    if email:
        cmd.append(f"--email {email}")

    if keysize:
        cmd.append(f"--rsa-key-size {keysize}")

    cmd.append(f"--domains {name}")
    if aliases is not None:
        for dns in aliases:
            cmd.append(f"--domains {dns}")

    if preferred_challenges:
        cmd.append(f"--preferred-challenges {preferred_challenges}")

    if tls_sni_01_port:
        cmd.append(f"--tls-sni-01-port {tls_sni_01_port}")
    if tls_sni_01_address:
        cmd.append(f"--tls-sni-01-address {tls_sni_01_address}")
    if http_01_port:
        cmd.append(f"--http-01-port {http_01_port}")
    if http_01_address:
        cmd.append(f"--http-01-address {http_01_address}")

    res = __salt__["cmd.run_all"](" ".join(cmd))

    if res["retcode"] != 0:
        if "expand" in res["stderr"]:
            cmd.append("--expand")
            res = __salt__["cmd.run_all"](" ".join(cmd))
            if res["retcode"] != 0:
                return {
                    "result": False,
                    "comment": "Certificate {} renewal failed with:\n{}".format(
                        name, res["stderr"]
                    ),
                }
        else:
            return {
                "result": False,
                "comment": "Certificate {} renewal failed with:\n{}".format(
                    name, res["stderr"]
                ),
            }

    if "no action taken" in res["stdout"]:
        comment = f"Certificate {cert_file} unchanged"
        result = None
    elif renew:
        comment = f"Certificate {certname} renewed"
        result = True
    else:
        comment = f"Certificate {certname} obtained"
        result = True

    ret = {
        "comment": comment,
        "not_after": expires(certname),
        "changes": {},
        "result": result,
    }
    ret, _ = __salt__["file.check_perms"](
        _cert_file(certname, "privkey"), ret, owner, group, mode, follow_symlinks=True
    )

    return ret


def certs():
    """
    Return a list of active certificates

    CLI Example:

    .. code-block:: bash

        salt 'vhost.example.com' acme.certs
    """
    return [
        item
        for item in __salt__["file.readdir"](LE_LIVE)[2:]
        if os.path.isdir(os.path.join(LE_LIVE, item))
    ]


def info(name):
    """
    Return information about a certificate

    :param str name: Name of certificate
    :rtype: dict
    :return: Dictionary with information about the certificate.
        If neither the ``tls`` nor the ``x509`` module can be used to determine
        the certificate information, the information will be retrieved as one
        big text block under the key ``text`` using the openssl cli.

    CLI Example:

    .. code-block:: bash

        salt 'gitlab.example.com' acme.info dev.example.com
    """
    if not has(name):
        return {}
    cert_file = _cert_file(name, "cert")
    # Use the tls salt module if available
    if "tls.cert_info" in __salt__:
        cert_info = __salt__["tls.cert_info"](cert_file)
        # Strip out the extensions object contents;
        # these trip over our poor state output
        # and they serve no real purpose here anyway
        cert_info["extensions"] = list(cert_info["extensions"])
    elif "x509.read_certificate" in __salt__:
        cert_info = __salt__["x509.read_certificate"](cert_file)
    else:
        # Cobble it together using the openssl binary
        openssl_cmd = f"openssl x509 -in {cert_file} -noout -text"
        cert_info = {"text": __salt__["cmd.run"](openssl_cmd, output_loglevel="quiet")}
    return cert_info


def expires(name):
    """
    The expiry date of a certificate in ISO format

    :param str name: Name of certificate
    :rtype: str
    :return: Expiry date in ISO format.

    CLI Example:

    .. code-block:: bash

        salt 'gitlab.example.com' acme.expires dev.example.com
    """
    return _expires(name).isoformat()


def has(name):
    """
    Test if a certificate is in the Let's Encrypt Live directory

    :param str name: Name of certificate
    :rtype: bool

    Code example:

    .. code-block:: python

        if __salt__['acme.has']('dev.example.com'):
            log.info('That is one nice certificate you have there!')
    """
    return __salt__["file.file_exists"](_cert_file(name, "cert"))


def renew_by(name, window=None):
    """
    Date in ISO format when a certificate should first be renewed

    :param str name: Name of certificate
    :param int window: number of days before expiry when renewal should take place
    :rtype: str
    :return: Date of certificate renewal in ISO format.
    """
    return _renew_by(name, window).isoformat()


def needs_renewal(name, window=None):
    """
    Check if a certificate needs renewal

    :param str name: Name of certificate
    :param bool/str/int window: Window in days to renew earlier or True/force to just return True
    :rtype: bool
    :return: Whether or not the certificate needs to be renewed.

    Code example:

    .. code-block:: python

        if __salt__['acme.needs_renewal']('dev.example.com'):
            __salt__['acme.cert']('dev.example.com', **kwargs)
        else:
            log.info('Your certificate is still good')
    """
    if window:
        if str(window).lower() in ("force", "true"):
            return True
        if not (
            isinstance(window, int) or (hasattr(window, "isdigit") and window.isdigit())
        ):
            raise SaltInvocationError(
                'The argument "window", if provided, must be one of the following : '
                'True (boolean), "force" or "Force" (str) or a numerical value in days.'
            )
        window = int(window)

    return _renew_by(name, window) <= datetime.datetime.today()
