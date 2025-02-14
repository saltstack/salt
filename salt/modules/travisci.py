"""
Commands for working with travisci.

:depends: pyOpenSSL >= 16.0.0
"""

import base64
import urllib.parse

import salt.utils.json
from salt.utils.versions import Version

try:
    import OpenSSL
    import OpenSSL.crypto

    HAS_OPENSSL = True
except ImportError:
    HAS_OPENSSL = False


OPENSSL_MIN_VER = "16.0.0"
__virtualname__ = "travisci"


def __virtual__():
    if HAS_OPENSSL is False:
        return (
            False,
            "The travisci module was unable to be loaded: Install pyOpenssl >= {}".format(
                OPENSSL_MIN_VER
            ),
        )
    cur_version = Version(OpenSSL.__version__)
    min_version = Version(OPENSSL_MIN_VER)
    if cur_version < min_version:
        return (
            False,
            "The travisci module was unable to be loaded: Install pyOpenssl >= {}".format(
                OPENSSL_MIN_VER
            ),
        )
    return __virtualname__


def verify_webhook(signature, body):
    """
    Verify the webhook signature from travisci

    signature
        The signature header from the webhook header

    body
        The full payload body from the webhook post

    .. note:: The body needs to be the urlencoded version of the body.

    CLI Example:

    .. code-block:: bash

        salt '*' travisci.verify_webhook 'M6NucCX5722bxisQs7e...' 'payload=%7B%22id%22%3A183791261%2C%22repository...'

    """
    # get public key setup
    public_key = __utils__["http.query"]("https://api.travis-ci.org/config")["config"][
        "notifications"
    ]["webhook"]["public_key"]
    pkey_public_key = OpenSSL.crypto.load_publickey(
        OpenSSL.crypto.FILETYPE_PEM, public_key
    )
    certificate = OpenSSL.crypto.X509()
    certificate.set_pubkey(pkey_public_key)

    # decode signature
    signature = base64.b64decode(signature)

    # parse the urlencoded payload from travis
    payload = salt.utils.json.loads(urllib.parse.parse_qs(body)["payload"][0])

    try:
        OpenSSL.crypto.verify(certificate, signature, payload, "sha1")
    except OpenSSL.crypto.Error:
        return False
    return True
