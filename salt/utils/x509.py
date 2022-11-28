import base64
import copy
import datetime
import ipaddress
import logging
import os.path
import re
from enum import Enum
from urllib.parse import urlparse, urlunparse

import cryptography
from cryptography import x509 as cx509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs7, pkcs12
from cryptography.x509.oid import SubjectInformationAccessOID

import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.utils.odict import OrderedDict

try:
    import idna

    HAS_IDNA = True
except ImportError:
    HAS_IDNA = False

CRYPTOGRAPHY_VERSION = tuple(int(x) for x in cryptography.__version__.split("."))

log = logging.getLogger(__name__)


EXTNAMES = [
    (
        "basicConstraints",
        "X509v3 Basic Constraints",
        cx509.ExtensionOID.BASIC_CONSTRAINTS,
    ),
    ("keyUsage", "X509v3 Key Usage", cx509.ExtensionOID.KEY_USAGE),
    (
        "extendedKeyUsage",
        "X509v3 Extended Key Usage",
        cx509.ExtensionOID.EXTENDED_KEY_USAGE,
    ),
    (
        "subjectKeyIdentifier",
        "X509v3 Subject Key Identifier",
        cx509.ExtensionOID.SUBJECT_KEY_IDENTIFIER,
    ),
    (
        "authorityKeyIdentifier",
        "X509v3 Authority Key Identifier",
        cx509.ExtensionOID.AUTHORITY_KEY_IDENTIFIER,
    ),
    (
        "issuerAltName",
        "X509v3 Issuer Alternative Name",
        cx509.ExtensionOID.ISSUER_ALTERNATIVE_NAME,
    ),
    (
        "authorityInfoAccess",
        "Authority Information Access",
        cx509.ExtensionOID.AUTHORITY_INFORMATION_ACCESS,
    ),
    (
        "subjectAltName",
        "X509v3 Subject Alternative Name",
        cx509.ExtensionOID.SUBJECT_ALTERNATIVE_NAME,
    ),
    (
        "crlDistributionPoints",
        "X509v3 CRL Distribution Points",
        cx509.ExtensionOID.CRL_DISTRIBUTION_POINTS,
    ),
    (
        "issuingDistributionPoint",
        "X509v3 Issuing Distribution Point",
        cx509.ExtensionOID.ISSUING_DISTRIBUTION_POINT,
    ),
    (
        "certificatePolicies",
        "X509v3 Certificate Policies",
        cx509.ExtensionOID.CERTIFICATE_POLICIES,
    ),
    (
        "policyConstraints",
        "X509v3 Policy Constraints",
        cx509.ExtensionOID.POLICY_CONSTRAINTS,
    ),
    (
        "inhibitAnyPolicy",
        "X509v3 Inhibit Any Policy",
        cx509.ExtensionOID.INHIBIT_ANY_POLICY,
    ),
    ("nameConstraints", "X509v3 Name Constraints", cx509.ExtensionOID.NAME_CONSTRAINTS),
    ("noCheck", "OCSP No Check", cx509.ExtensionOID.OCSP_NO_CHECK),
    ("tlsfeature", "TLS Feature", cx509.ExtensionOID.TLS_FEATURE),
    ("nsComment", "Netscape Comment", None),
    ("nsCertType", "Netscape Certificate Type", None),
    ("cRLNumber", "X509v3 CRLNumber", cx509.ExtensionOID.CRL_NUMBER),
    (
        "deltaCRLIndicator",
        "X509v3 Delta CRL Indicator",
        cx509.ExtensionOID.DELTA_CRL_INDICATOR,
    ),
    ("freshestCRL", "x509v3 Freshest CRL", cx509.ExtensionOID.FRESHEST_CRL),
]

EXTNAMES_CRL_ENTRY = [
    (
        "certificateIssuer",
        "x509v3 Certificate Issuer",
        cx509.CRLEntryExtensionOID.CERTIFICATE_ISSUER,
    ),
    ("CRLReason", "X509v3 CRL Reason Code", cx509.CRLEntryExtensionOID.CRL_REASON),
    ("invalidityDate", "Invalidity Date", cx509.CRLEntryExtensionOID.INVALIDITY_DATE),
]


class KEY_TYPE(Enum):
    RSA = 1
    EC = 2
    ED25519 = 3
    ED448 = 4


NAME_OID = OrderedDict(
    [
        ("C", cx509.NameOID.COUNTRY_NAME),
        ("ST", cx509.NameOID.STATE_OR_PROVINCE_NAME),
        ("L", cx509.NameOID.LOCALITY_NAME),
        ("STREET", cx509.NameOID.STREET_ADDRESS),
        ("O", cx509.NameOID.ORGANIZATION_NAME),
        ("OU", cx509.NameOID.ORGANIZATIONAL_UNIT_NAME),
        ("CN", cx509.NameOID.COMMON_NAME),
        ("MAIL", cx509.NameOID.EMAIL_ADDRESS),
        ("SN", cx509.NameOID.SURNAME),
        ("GN", cx509.NameOID.GIVEN_NAME),
        ("UID", cx509.NameOID.USER_ID),
        ("SERIALNUMBER", cx509.NameOID.SERIAL_NUMBER),
    ]
)

EXTENDED_KEY_USAGE_OID = {
    "serverAuth": cx509.ObjectIdentifier("1.3.6.1.5.5.7.3.1"),
    "clientAuth": cx509.ObjectIdentifier("1.3.6.1.5.5.7.3.2"),
    "codeSigning": cx509.ObjectIdentifier("1.3.6.1.5.5.7.3.3"),
    "emailProtection": cx509.ObjectIdentifier("1.3.6.1.5.5.7.3.4"),
    "timeStamping": cx509.ObjectIdentifier("1.3.6.1.5.5.7.3.8"),
    "OCSPSigning": cx509.ObjectIdentifier("1.3.6.1.5.5.7.3.9"),
    "msSmartcardLogin": cx509.ObjectIdentifier("1.3.6.1.4.1.311.20.2.2"),
    "pkInitKDC": cx509.ObjectIdentifier("1.3.6.1.5.2.3.5"),
    "ipsecIKE": cx509.ObjectIdentifier("1.3.6.1.5.5.7.3.17"),
    "msCodeInd": cx509.ObjectIdentifier("1.3.6.1.4.1.311.2.1.21"),
    "msCodeCom": cx509.ObjectIdentifier("1.3.6.1.4.1.311.2.1.22"),
    "msCTLSign": cx509.ObjectIdentifier("1.3.6.1.4.1.311.10.3.1"),
    "msEFS": cx509.ObjectIdentifier("1.3.6.1.4.1.311.10.3.4"),
}

ACCESS_OID = {
    "OCSP": cx509.AuthorityInformationAccessOID.OCSP,
    "caIssuers": cx509.AuthorityInformationAccessOID.CA_ISSUERS,
    "caRepository": SubjectInformationAccessOID.CA_REPOSITORY,
}

CERT_EXTS = (
    "basicConstraints",
    "keyUsage",
    "extendedKeyUsage",
    "subjectKeyIdentifier",
    "authorityKeyIdentifier",
    "issuerAltName",
    "authorityInfoAccess",
    "subjectAltName",
    "crlDistributionPoints",
    "certificatePolicies",
    "policyConstraints",
    "inhibitAnyPolicy",
    "nameConstraints",
    "noCheck",
    "tlsfeature",
    "nsComment",
    "nsCertType",
)

CRL_EXTS = (
    "authorityKeyIdentifier",
    "authorityInfoAccess",
    "cRLNumber",
    "deltaCRLIndicator",
    "freshestCRL",
    "issuerAltName",
    "issuingDistributionPoint",
)

CRL_ENTRY_EXTS = (
    "certificateIssuer",
    "CRLReason",
    "invalidityDate",
)

CSR_FORBIDDEN = (
    "authorityInfoAccess",
    "authorityKeyIdentifier",
    "issuerAltName",
    "crlDistributionPoints",
)


PEM_BEGIN = b"-----BEGIN"
PEM_END = b"-----END"

TIME_FMT = "%Y-%m-%d %H:%M:%S"


def build_crt(
    signing_private_key,
    skip_load_signing_private_key=False,
    signing_private_key_passphrase=None,
    signing_cert=None,
    public_key=None,
    private_key=None,
    private_key_passphrase=None,
    csr=None,
    subject=None,
    serial_number=None,
    not_before=None,
    not_after=None,
    days_valid=30,
    **kwargs,
):
    """
    Parse the input into a CertificateBuilder, which can be used
    to sign the certificate or be inspected for changes.

    Also returns signing private key (if available), associated private key
    and associated signing certificate.
    """
    ca_pub = None
    self_signed = False
    if not skip_load_signing_private_key:
        # skipping this is necessary for the state module to be able to check
        # for changes when issuing certs from remote
        signing_private_key = load_privkey(
            signing_private_key, passphrase=signing_private_key_passphrase
        )
    else:
        signing_private_key = None
    serial_number = _get_serial_number(serial_number)
    # optionally holds cert-associated private key, needed for pkcs12 serialization later
    private_key_loaded = None

    if csr:
        csr = load_csr(csr)
    if signing_cert:
        signing_cert = load_cert(signing_cert)
    else:
        self_signed = True
        public_key = signing_private_key.public_key()
        ca_pub = public_key

    if self_signed:
        pass
    elif private_key:
        private_key_loaded = load_privkey(
            private_key, passphrase=private_key_passphrase
        )
        public_key = private_key_loaded.public_key()
    elif public_key:
        public_key = load_pubkey(public_key)
    elif csr:
        public_key = csr.public_key()
    else:
        raise SaltInvocationError(
            "This certificate is not self-signed (signing_cert is set) and thus "
            "needs public_key, private_key or csr to derive public key to sign"
        )

    if (
        not skip_load_signing_private_key
        and not self_signed
        and not is_pair(signing_cert.public_key(), signing_private_key)
    ):
        raise SaltInvocationError(
            "Signing private key does not match the certificate's public key"
        )

    builder = cx509.CertificateBuilder(
        serial_number=serial_number, public_key=public_key
    )

    subject_name = _get_dn(subject or kwargs)
    builder = builder.subject_name(subject_name).issuer_name(
        signing_cert.subject if not self_signed else subject_name
    )

    not_before = (
        datetime.datetime.strptime(not_before, TIME_FMT)
        if not_before
        else datetime.datetime.utcnow()
    )
    not_after = (
        datetime.datetime.strptime(not_after, TIME_FMT)
        if not_after
        else datetime.datetime.utcnow() + datetime.timedelta(days=days_valid)
    )
    builder = builder.not_valid_before(not_before).not_valid_after(not_after)

    ext_present = []
    for extname, extlongname, _ in EXTNAMES:
        if extname not in CERT_EXTS:
            continue
        if extname in kwargs or extlongname in kwargs:
            try:
                val = kwargs[extname]
            except KeyError:
                val = kwargs[extlongname]
            # signing policies need to be able to force-unset extensions
            if val is None:
                continue
            ext, critical = _create_extension(
                extname,
                val,
                ca_crt=signing_cert,
                subject_pubkey=public_key,
                ca_pub=ca_pub,
            )
            builder = builder.add_extension(
                ext,
                critical=critical,
            )
            ext_present.append(extname)
    if csr:
        for extname, _, oid in EXTNAMES:
            if any(
                (
                    extname in ext_present,
                    extname not in CERT_EXTS,
                    extname in CSR_FORBIDDEN,
                )
            ):
                continue
            try:
                ext = csr.extensions.get_extension_for_oid(oid)
                builder = builder.add_extension(ext.value, ext.critical)
            except cx509.ExtensionNotFound:
                pass
    return builder, signing_private_key, private_key_loaded, signing_cert


def build_csr(private_key, private_key_passphrase=None, subject=None, **kwargs):
    """
    Parse the input into a CertificateSigningRequestBuilder, which can be used
    to sign the CSR or be inspected for changes.

    Also returns associated private key.
    """
    private_key = load_privkey(private_key, passphrase=private_key_passphrase)
    public_key = private_key.public_key()
    builder = cx509.CertificateSigningRequestBuilder()
    subject_name = _get_dn(subject or kwargs)
    builder = builder.subject_name(subject_name)
    for extname, extlongname, oid in EXTNAMES:
        if any(
            (
                extname not in CERT_EXTS,
                extname in CSR_FORBIDDEN,
            )
        ):
            continue
        if extname in kwargs or extlongname in kwargs:
            val = kwargs.get(extname) or kwargs[extlongname]
            ext, critical = _create_extension(extname, val, subject_pubkey=public_key)
            builder = builder.add_extension(
                ext,
                critical=critical,
            )
    return builder, private_key


def build_crl(
    signing_private_key,
    revoked,
    signing_cert=None,
    signing_private_key_passphrase=None,
    include_expired=False,
    days_valid=100,
    extensions=None,
):
    """
    Parse the input into a CertificateRevocationListBuilder, which can be used
    to sign the CRL or be inspected for changes.

    Also returns signing private key.
    """
    extensions = extensions or {}
    if signing_cert:
        signing_cert = load_cert(signing_cert)
    signing_private_key = load_privkey(
        signing_private_key, passphrase=signing_private_key_passphrase
    )
    if signing_cert and not is_pair(signing_cert.public_key(), signing_private_key):
        raise SaltInvocationError(
            "Signing private key does not match the certificate's public key"
        )
    builder = cx509.CertificateRevocationListBuilder()
    if signing_cert:
        builder = builder.issuer_name(signing_cert.subject)
    builder = builder.last_update(datetime.datetime.today())
    builder = builder.next_update(
        datetime.datetime.today() + datetime.timedelta(days=days_valid)
    )
    for rev in revoked:
        serial_number = not_after = revocation_date = None
        if "not_after" in rev:
            not_after = datetime.datetime.strptime(rev["not_after"], TIME_FMT)
        if "serial_number" in rev:
            serial_number = rev["serial_number"]
        if "certificate" in rev:
            rev_cert = load_cert(rev["certificate"])
            serial_number = rev_cert.serial_number
            not_after = rev_cert.not_valid_after
        if not serial_number:
            raise SaltInvocationError("Need serial_number or certificate")
        serial_number = _get_serial_number(serial_number)
        if not_after and not include_expired:
            if datetime.datetime.utcnow() > not_after:
                continue
        if "revocation_date" in rev:
            revocation_date = datetime.datetime.strptime(
                rev["revocation_date"], TIME_FMT
            )
        else:
            revocation_date = datetime.datetime.utcnow()

        revoked_cert = cx509.RevokedCertificateBuilder(
            serial_number=serial_number, revocation_date=revocation_date
        )
        for extname, val in rev.get("extensions", {}).items():
            if extname not in CRL_ENTRY_EXTS:
                continue
            ext, critical = _create_extension(extname, val)
            revoked_cert = revoked_cert.add_extension(ext, critical=critical)
        builder = builder.add_revoked_certificate(revoked_cert.build())
    for extname, _, _ in EXTNAMES:
        if extname not in CRL_EXTS:
            continue
        if extname in extensions:
            val = extensions[extname]
            ext, critical = _create_extension(extname, val, ca_crt=signing_cert)
            builder = builder.add_extension(
                ext,
                critical=critical,
            )
    return builder, signing_private_key


def generate_rsa_privkey(keysize=2048):
    """
    Generate an RSA private key
    """
    if keysize not in [2048, 3072, 4096]:
        raise SaltInvocationError(
            "RSA key size must be either 2048, 3072 or 4096 bits."
        )
    return rsa.generate_private_key(public_exponent=65537, key_size=keysize)


def generate_ec_privkey(keysize=256):
    """
    Generate an elliptic curve private key
    """
    if keysize not in [256, 384, 521]:
        raise SaltInvocationError("EC key size must be either 256, 384, 521 bits.")
    return ec.generate_private_key(getattr(ec, f"SECP{keysize}R1")())


def generate_ed25519_privkey():
    """
    Generate an ed25519 private key
    """
    return ed25519.Ed25519PrivateKey.generate()


def generate_ed448_privkey():
    """
    Generate an ed448 private key
    """
    return ed448.Ed448PrivateKey.generate()


def get_hashing_algorithm(digest):
    """
    Returns an instance of a hashing algorithm, if available
    """
    try:
        return getattr(hashes, digest.upper())()
    except AttributeError as err:
        raise CommandExecutionError(
            "The selected hashing algorithm does not exist in the cryptography "
            "python library"
        ) from err


def get_key_type(key, as_string=False):
    """
    Checks which type of private/public key a class instance is.
    Returns None if it is not a valid key.
    """
    key_type = None
    if isinstance(key, (rsa.RSAPrivateKey, rsa.RSAPublicKey)):
        key_type = "rsa"
    if isinstance(key, (ec.EllipticCurvePrivateKey, ec.EllipticCurvePublicKey)):
        key_type = "ec"
    if isinstance(key, (ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey)):
        key_type = "ed25519"
    if isinstance(key, (ed448.Ed448PrivateKey, ed448.Ed448PublicKey)):
        key_type = "ed448"
    if key_type is None or as_string:
        return key_type
    return getattr(KEY_TYPE, key_type.upper())


def is_pair(pubkey, privkey):
    """
    Checks whether a public key belongs to a private key
    """
    privkey_type = get_key_type(privkey)
    if privkey_type is None:
        raise SaltInvocationError("Did not recognize key type")
    return match_pubkey(pubkey, privkey.public_key())


def match_pubkey(pubkey_a, pubkey_b):
    """
    Checks whether two public keys are the same
    """
    pubkey_a_type = get_key_type(pubkey_a)
    pubkey_b_type = get_key_type(pubkey_b)

    if pubkey_a_type is None or pubkey_b_type is None:
        raise SaltInvocationError("Did not recognize key type")
    if pubkey_a_type != pubkey_b_type:
        return False
    if pubkey_a_type in [KEY_TYPE.RSA, KEY_TYPE.EC]:
        return pubkey_a.public_numbers() == pubkey_b.public_numbers()
    return to_pem(pubkey_a) == to_pem(pubkey_b)


def merge_signing_policy(policy, kwargs):
    """
    Merge a signing policy, taking care that the different methods
    of specifying RDN do not lead to unexpected results.

    This is found in utils since the state module needs
    access as well to check for expected changes.
    """
    if not policy:
        return kwargs
    # ensure we don't modify data that is used elsewhere
    policy = copy.deepcopy(policy)
    if "subject" in kwargs:
        # a) ensure subject in kwargs does not override CN etc from signing policy
        if any(x in policy for x in NAME_OID):
            kwargs.pop("subject")
        # b) subject is not enforced or if it is a string, it cannot be overridden
        elif "subject" not in policy or not isinstance(policy["subject"], (dict, list)):
            pass
        # c) if both subject sources are of the same time, update dicts or merge lists
        else:
            try:
                kwargs["subject"].update(policy["subject"])
                policy.pop("subject")
            except (AttributeError, ValueError):
                try:
                    kwargs["subject"] = policy["subject"] + kwargs["subject"]
                    policy.pop("subject")
                except TypeError:
                    pass
        # d) otherwise enforce subject from signing policy
    kwargs.update(policy)
    return kwargs


def to_pem(pub_or_cert):
    """
    Returns the PEM-encoded serialization of a public key, certificate,
    certificate signing request or certificate revocation list.
    This does not work for private keys.
    """
    try:
        return pub_or_cert.public_bytes(
            serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    except (AttributeError, TypeError):
        pass
    try:
        return pub_or_cert.public_bytes(serialization.Encoding.PEM)
    except (AttributeError, TypeError):
        pass
    raise SaltInvocationError("Could not serialize parameter to PEM")


def to_der(pub_or_cert):
    """
    Returns the DER-encoded serialization of a public key, certificate,
    certificate signing request or certificate revocation list.
    This does not work for private keys.
    """
    try:
        return pub_or_cert.public_bytes(
            serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    except (AttributeError, TypeError):
        pass
    try:
        return pub_or_cert.public_bytes(serialization.Encoding.DER)
    except (AttributeError, TypeError):
        pass
    raise SaltInvocationError("Could not serialize parameter to DER")


def load_privkey(pk, passphrase=None, get_encoding=False):
    """
    Return a private key instance from
    * a class instance
    * a file path on the local system
    * a string (PEM)
    * bytes (hex, base64, raw)

    Valid encodings are PEM, DER and PKCS12.
    """
    if hasattr(pk, "private_bytes"):
        if isinstance(
            pk,
            (
                rsa.RSAPrivateKey,
                ec.EllipticCurvePrivateKey,
                ed25519.Ed25519PrivateKey,
                ed448.Ed448PrivateKey,
            ),
        ):
            if get_encoding:
                return pk, None, None
            return pk
        raise SaltInvocationError(
            f"Passed object is not a known private key, but {pk.__class__.__name__}"
        )
    pk = load_file_or_bytes(pk)
    passphrase = passphrase.encode() if passphrase is not None else None
    # PEM
    if PEM_BEGIN in pk:
        try:
            pk = serialization.load_pem_private_key(pk, password=passphrase)
            if get_encoding:
                return pk, "pem", None
            return pk
        except ValueError as err:
            if "Bad decrypt" in str(err):
                raise SaltInvocationError(
                    "Bad decrypt - is the password correct?"
                ) from err
            raise CommandExecutionError(
                "Could not load PEM-encoded private key"
            ) from err
        except TypeError as err:
            if "private key is encrypted" in str(err):
                raise SaltInvocationError(
                    "Private key is encrypted. Please provide a password."
                ) from err
            if "but private key is not encrypted" in str(err):
                raise SaltInvocationError("Private key is unencrypted") from err
            raise CommandExecutionError(
                "Could not load PEM-encoded private key"
            ) from err
    # DER
    try:
        pk = serialization.load_der_private_key(pk, password=passphrase)
        if get_encoding:
            return pk, "der", None
        return pk
    except ValueError as err:
        if "Bad decrypt" in str(err):
            raise SaltInvocationError("Bad decrypt - is the password correct?") from err
    except TypeError as err:
        if "private key is encrypted" in str(err):
            raise SaltInvocationError(
                "Private key is encrypted. Please provide a password."
            ) from err
    # PKCS12
    try:
        # v36+ - there is pkcs12.load_key_and_certificates in 2.5+ @TODO?
        loaded = pkcs12.load_pkcs12(pk, password=passphrase)
        if not loaded.key:
            raise CommandExecutionError(
                "PKCS12-encoded blob does not contain a private key."
            )
        if get_encoding:
            return loaded.key, "pkcs12", loaded
        return loaded.key
    except ValueError as err:
        if "Bad decrypt" in str(err):
            raise SaltInvocationError("Bad decrypt - is the password correct?") from err
    except TypeError as err:
        if "private key is encrypted" in str(err):
            raise SaltInvocationError(
                "Private key is encrypted. Please provide a password."
            ) from err
    except AttributeError:
        pass
    # nothing worked
    raise SaltInvocationError(
        "Could not deserialize binary data, neither as DER nor PKCS#12."
    )


def load_pubkey(pk, get_encoding=False):
    """
    Return a public key instance from
    * a class instance
    * a file path on the local system
    * a string (PEM)
    * bytes (hex, base64, raw)

    Valid encodings are PEM and DER.
    """
    if hasattr(pk, "public_bytes"):
        if isinstance(
            pk,
            (
                rsa.RSAPublicKey,
                ec.EllipticCurvePublicKey,
                ed25519.Ed25519PublicKey,
                ed448.Ed448PublicKey,
            ),
        ):
            return pk
        raise SaltInvocationError(
            f"Passed object is not a public key, but {pk.__class__.__name__}"
        )
    pk = load_file_or_bytes(pk)
    if PEM_BEGIN in pk:
        try:
            return serialization.load_pem_public_key(pk)
        except ValueError as err:
            raise CommandExecutionError(
                "Could not load PEM-encoded public key."
            ) from err
    try:
        return serialization.load_der_public_key(pk)
    except ValueError as err:
        raise CommandExecutionError("Could not load DER-encoded public key.") from err


def load_cert(cert, passphrase=None, load_chain=False, get_encoding=False):
    """
    Return a certificate instance from
    * a class instance
    * a file path on the local system
    * a string (PEM)
    * bytes (hex, base64, raw)

    Valid encodings are PEM, DER, PKCS7 (as PEM and DER) and PKCS12.
    """
    if isinstance(cert, cx509.Certificate):
        if load_chain:
            return cert, []
        if get_encoding:
            return cert, None, None
        return cert
    cert = load_file_or_bytes(cert)
    # PEM or PKCS7 in PEM
    if PEM_BEGIN in cert:
        pems = split_pems(cert)
        if b"-----BEGIN PKCS7" not in pems[0]:
            try:
                loaded = cx509.load_pem_x509_certificate(pems.pop(0))
                if load_chain or get_encoding:
                    chain = []
                    for pem in pems:
                        try:
                            chain.append(cx509.load_pem_x509_certificate(pem))
                        except ValueError:
                            pass
                if load_chain:
                    return loaded, chain
                if get_encoding:
                    return loaded, "pem", chain, None
                return loaded
            except (ValueError, IndexError) as err:
                raise CommandExecutionError(
                    "Could not load PEM-encoded certificate."
                ) from err
        else:
            try:
                loaded = pkcs7.load_pem_pkcs7_certificates(pems[0])
                if load_chain:
                    return loaded.pop(0), loaded
                if get_encoding:
                    return loaded.pop(0), "pkcs7_pem", loaded, None
                return loaded.pop(0)
            except ValueError as err:
                raise CommandExecutionError(
                    "Could not load PEM-encoded PKCS#7 blob"
                ) from err
    # DER
    try:
        loaded = cx509.load_der_x509_certificate(cert)
        if get_encoding:
            return loaded, "der", None, None
        if load_chain:
            return loaded, []
        return loaded
    except ValueError:
        pass
    # PKCS12
    try:
        if passphrase is not None and not isinstance(passphrase, bytes):
            passphrase = passphrase.encode()
        # v36+
        loaded = pkcs12.load_pkcs12(cert, passphrase)
        if load_chain or get_encoding:
            chain = [x.certificate for x in loaded.additional_certs]
            if load_chain:
                return loaded.cert.certificate, chain
            if get_encoding:
                return loaded.cert.certificate, "pkcs12", chain, loaded
        return loaded.cert.certificate
    except (AttributeError, ValueError):
        pass
    # PKCS7
    try:
        # v37+
        loaded = pkcs7.load_der_pkcs7_certificates(cert)
        if load_chain:
            return loaded.pop(0), loaded
        if get_encoding:
            return loaded.pop(0), "pkcs7_der", loaded, None
        return loaded[0]
    except ValueError:
        pass
    # nothing worked
    raise SaltInvocationError(
        "Could not deserialize binary data, neither as DER nor PKCS#7, PKCS#12."
    )


def load_crl(crl, get_encoding=False):
    """
    Return a CRL instance from
    * a class instance
    * a file path on the local system
    * a string (PEM)
    * bytes (hex, base64, raw)

    Valid encodings are PEM and DER.
    """
    if isinstance(crl, cx509.CertificateRevocationList):
        if get_encoding:
            return crl, None, None
        return crl
    crl = load_file_or_bytes(crl)
    if PEM_BEGIN in crl:
        try:
            loaded = cx509.load_pem_x509_crl(crl)
            if get_encoding:
                return loaded, "pem"
            return loaded
        except ValueError as err:
            raise SaltInvocationError(
                "Could not load PEM-encoded certificate revocation list."
            ) from err
    try:
        loaded = cx509.load_der_x509_crl(crl)
        if get_encoding:
            return loaded, "der"
        return loaded
    except ValueError as err:
        raise SaltInvocationError(
            "Could not load DER-encoded certificate revocation list."
        ) from err


def load_csr(csr, get_encoding=False):
    """
    Return a CSR instance from
    * a class instance
    * a file path on the local system
    * a string (PEM)
    * bytes (hex, base64, raw)

    Valid encodings are PEM and DER.
    """
    if isinstance(csr, cx509.CertificateSigningRequest):
        if get_encoding:
            return csr, None, None
        return csr
    csr = load_file_or_bytes(csr)
    if PEM_BEGIN in csr:
        try:
            loaded = cx509.load_pem_x509_csr(csr)
            if get_encoding:
                return loaded, "pem"
            return loaded
        except ValueError as err:
            raise SaltInvocationError(
                "Could not load PEM-encoded certificate signing request."
            ) from err
    try:
        loaded = cx509.load_der_x509_csr(csr)
        if get_encoding:
            return loaded, "der"
        return loaded
    except ValueError as err:
        raise SaltInvocationError(
            "Could not load DER-encoded certificate signing request."
        ) from err


def verify_signature(cert, pubkey):
    """
    Verifies that the signature on a certificate was made
    by a public key.

    This functionality is currently not exposed by cryptography
    since it does not imply the certificate chain is valid.
    """
    key_type = get_key_type(pubkey)
    if KEY_TYPE.RSA == key_type:
        try:
            # SignatureAlgorithmOID is not present in older versions,
            # otherwise cx509.SignatureAlgorithmOID.RSASSA_PSS could be used
            if "1.2.840.113549.1.1.10" == cert.signature_algorithm_oid.dotted_string:
                pubkey.verify(
                    cert.signature,
                    cert.tbs_certificate_bytes,
                    padding.PSS(
                        padding.MGF1(cert.signature_hash_algorithm), padding.PSS.AUTO
                    ),
                    cert.signature_hash_algorithm,
                )
            else:
                pubkey.verify(
                    cert.signature,
                    cert.tbs_certificate_bytes,
                    padding.PKCS1v15(),
                    cert.signature_hash_algorithm,
                )
            return True
        except InvalidSignature:
            return False
    if KEY_TYPE.EC == key_type:
        try:
            pubkey.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                ec.ECDSA(cert.signature_hash_algorithm),
            )
            return True
        except InvalidSignature:
            return False
    if key_type in [KEY_TYPE.ED25519, KEY_TYPE.ED448]:
        try:
            pubkey.verify(cert.signature, cert.tbs_certificate_bytes)
            return True
        except InvalidSignature:
            return False
    raise SaltInvocationError(
        "Invalid public key type, can only process rsa, ec, ed25519, ed448"
    )


def isfile(path):
    """
    A wrapper around os.path.isfile that ignores ValueError exception,s which
    can be raised if the input to isfile is too long.
    """
    try:
        return os.path.isfile(path)
    except (TypeError, ValueError):
        pass
    return False


def split_pems(pems):
    """
    Returns a list of PEM strings from a possibly concatenated one
    """
    pems = salt.utils.stringutils.to_bytes(pems)
    splits = []
    cur = []

    for line in pems.splitlines(True):
        if not line.strip():
            continue
        if line.startswith(PEM_BEGIN):
            cur = [line]
            continue
        cur.append(line)
        if line.startswith(PEM_END):
            splits.append(b"".join(cur))
            cur = []
    return splits


def load_file_or_bytes(fob):
    """
    Tries to load a reference and return its bytes.
    Can be a file path on the local system, a string and bytes (hex/base64-encoded, raw)
    """
    if isfile(fob):
        with salt.utils.files.fopen(fob, "rb") as f:
            fob = f.read()
    if isinstance(fob, str):
        if PEM_BEGIN.decode() in fob:
            fob = fob.encode()
        else:
            try:
                fob = bytes.fromhex(fob)
            except ValueError:
                try:
                    fob = base64.b64decode(fob)
                except ValueError:
                    pass
    if not isinstance(fob, bytes):
        raise SaltInvocationError(
            "Could not load provided source. You need to pass an existing file, "
            "(PEM|hex|base64)-encoded string or raw bytes."
        )
    return fob


def _create_extension(name, val, subject_pubkey=None, ca_crt=None, ca_pub=None):
    if "basicConstraints" == name:
        try:
            critical = val.get("critical", False)
        except AttributeError:
            critical = False
        if isinstance(val, str):
            try:
                val, critical = _deserialize_openssl_confstring(val.lower())
                val["ca"] = val["ca"] == "true"
                if "pathlen" in val:
                    val["pathlen"] = int(val["pathlen"])
            except (KeyError, ValueError) as err:
                raise SaltInvocationError(
                    f"Invalid configuration for basicContraints: {err}"
                ) from err
        try:
            return (
                cx509.BasicConstraints(val["ca"], val.get("pathlen")),
                critical,
            )
        except KeyError as err:
            raise SaltInvocationError(
                f"Undefined required key for {name}: {err}"
            ) from err
        except (TypeError, ValueError) as err:
            raise SaltInvocationError(err) from err

    if "keyUsage" == name:
        critical = "critical" in val
        args = {
            "digital_signature": "digitalSignature" in val,
            "content_commitment": "nonRepudiation" in val,
            "key_encipherment": "keyEncipherment" in val,
            "data_encipherment": "dataEncipherment" in val,
            "key_agreement": "keyAgreement" in val,
            "key_cert_sign": "keyCertSign" in val,
            "crl_sign": "cRLSign" in val,
            "encipher_only": "encipherOnly" in val,
            "decipher_only": "decipherOnly" in val,
        }
        try:
            return cx509.KeyUsage(**args), critical
        except ValueError as err:
            raise SaltInvocationError(err) from err

    if "extendedKeyUsage" == name:
        critical = "critical" in val
        if isinstance(val, str):
            val, critical = _deserialize_openssl_confstring(val)
            val = list(val)
        if not isinstance(val, list):
            val = [val]
        usages = []
        for usage in val:
            if "critical" == usage:
                continue
            usages.append(EXTENDED_KEY_USAGE_OID.get(usage) or _get_oid(str(usage)))
        return cx509.ExtendedKeyUsage(usages), critical

    if "subjectKeyIdentifier" == name:
        if "critical" in val:
            raise SaltInvocationError(
                "subjectKeyIdentifier must be marked as non-critical"
            )
        if "hash" == val:
            if not subject_pubkey:
                raise RuntimeError(
                    "Cannot calculate digest for subjectKeyIdentifier: missing pubkey"
                )
            try:
                return (
                    cx509.SubjectKeyIdentifier.from_public_key(subject_pubkey),
                    False,
                )
            except AttributeError as err:
                raise RuntimeError(
                    "subjectKeyIdentifier: subject_pubkey was not a pubkey"
                ) from err
        if isinstance(val, str):
            try:
                val = bytes.fromhex(val.replace(":", ""))
            except ValueError as err:
                raise SaltInvocationError("Value must be precomputed hash") from err
        if not isinstance(val, bytes):
            raise SaltInvocationError("Value must be a (hex-)digest or pubkey")
        # this must be marked as non-critical
        return cx509.SubjectKeyIdentifier(val), False

    if "authorityKeyIdentifier" == name:
        if "critical" in val:
            raise SaltInvocationError(
                "authorityKeyIdentifier must be marked as non-critical"
            )
        if not (ca_crt or ca_pub):
            raise RuntimeError(
                "Need CA certificate or CA pubkey to calculate authorityKeyIdentifier"
            )
        if isinstance(val, str):
            val, _ = _deserialize_openssl_confstring(val)
        args = {
            "key_identifier": None,
            "authority_cert_issuer": None,
            "authority_cert_serial_number": None,
        }
        if "keyid" in val:
            if ca_crt:
                try:
                    args["key_identifier"] = ca_crt.extensions.get_extension_for_class(
                        cx509.SubjectKeyIdentifier
                    ).value.digest
                except cx509.ExtensionNotFound:
                    args[
                        "key_identifier"
                    ] = cx509.AuthorityKeyIdentifier.from_issuer_public_key(
                        ca_crt.public_key()
                    ).key_identifier
                except Exception:  # pylint: disable=broad-except
                    pass
            if not args["key_identifier"] and ca_pub:
                # this should happen for self-signed certificates
                try:
                    args[
                        "key_identifier"
                    ] = cx509.AuthorityKeyIdentifier.from_issuer_public_key(
                        ca_pub
                    ).key_identifier
                except Exception:  # pylint: disable=broad-except
                    pass

            if "always" == val["keyid"] and args["key_identifier"] is None:
                raise CommandExecutionError(
                    "Could not retrieve authorityKeyIdentifier keyid, but it was set to always"
                )

        if val.get("issuer") == "always" or (
            "issuer" in val and args["key_identifier"] is None
        ):
            try:
                args["authority_cert_issuer"] = [cx509.DirectoryName(ca_crt.issuer)]
                args["authority_cert_serial_number"] = ca_crt.serial_number
            except (AttributeError, ValueError) as err:
                # this will not work for self-signed certificates currently
                args["authority_cert_issuer"] = args[
                    "authority_cert_serial_number"
                ] = None
                if "always" == val["issuer"]:
                    raise CommandExecutionError(
                        "Could not add authority_cert_issuer and "
                        "authority_cert_serial_number, but was set to always."
                    ) from err

        if not args:
            raise SaltInvocationError("authorityKeyIdentifier cannot be empty.")
        # this must be marked as non-critical
        return cx509.AuthorityKeyIdentifier(**args), False

    if name in ["issuerAltName", "certificateIssuer"]:
        critical = "critical" in val
        if isinstance(val, list):
            list_ = []
            for x in val:
                if isinstance(x, str) and ":" in x:
                    k, v = x.split(":", maxsplit=1)
                    list_.append((k.strip(), v.strip()))
                elif isinstance(x, dict):
                    list_.extend(list(x.items()))
            # since this is accessed twice, the generator needs to be cast to a tuple
            val = tuple(list_)
        elif isinstance(val, str):
            val, critical = _deserialize_openssl_confstring(val, multiple=True)
            val = tuple(val)
        parsed = []
        if any(("issuer", "copy") == x for x in val):
            if not ca_crt:
                raise RuntimeError("Need CA certificate to copy to issuerAltName")
            try:
                # eeh, there's no public API to get the list of general names
                parsed.extend(
                    copy.deepcopy(
                        ca_crt.extensions.get_extension_for_class(
                            cx509.SubjectAlternativeName
                        )._general_names._general_names
                    )
                )
                val = tuple(x for x in val if x[0] != "issuer")
            except cx509.ExtensionNotFound as err:
                raise CommandExecutionError(err) from err
            except AttributeError as err:
                raise CommandExecutionError(
                    "It seems your version of cryptography does not have an "
                    "internal API that the issuer:copy functionality relies on"
                ) from err
        parsed.extend(_parse_general_names(val))
        if "certificateIssuer" == name:
            return cx509.CertificateIssuer(parsed), critical
        return cx509.IssuerAlternativeName(parsed), critical

    if "authorityInfoAccess" == name:
        if isinstance(val, str):
            val = (
                x.strip().split(";") for x in val.split(",") if "critical" != x.strip()
            )
        elif isinstance(val, dict):
            val = ((k, v) for k, v in val.items() if "critical" != k)
        elif isinstance(val, list):
            val = ((k, v) for x in val for k, v in x.items() if x != "critical")

        parsed = []
        for oid, general_name in val:
            try:
                oid = ACCESS_OID.get(oid) or _get_oid(str(oid))
            except CommandExecutionError as err:
                raise CommandExecutionError(f"Unknown access OID: {oid}") from err
            general_name = _get_gn(general_name)
            parsed.append(cx509.AccessDescription(oid, general_name))
        return cx509.AuthorityInformationAccess(parsed), False  # always noncritical

    if "subjectAltName" == name:
        # subjectAltName must be marked as critical if subject is empty
        critical = "critical" in val
        if isinstance(val, list):
            list_ = []
            for x in val:
                if isinstance(x, str) and ":" in x:
                    k, v = x.split(":", maxsplit=1)
                    list_.append((k.strip(), v.strip()))
                elif isinstance(x, dict):
                    list_.extend(list(x.items()))
            val = tuple(list_)
        elif isinstance(val, str):
            val, critical = _deserialize_openssl_confstring(val, multiple=True)
        parsed = _parse_general_names(val)
        return cx509.SubjectAlternativeName(parsed), critical

    if name in ["crlDistributionPoints", "freshestCRL"]:
        critical = "critical" in val
        if isinstance(val, str):
            val, critical = _deserialize_openssl_confstring(val, multiple=True)
        elif isinstance(val, list):
            list_ = []
            for x in val:
                if isinstance(x, str) and ":" in x:
                    k, v = x.split(":", maxsplit=1)
                    list_.append((k.strip(), v.strip()))
                elif x != "critical":
                    list_.append(x)
            val = tuple(list_)
        parsed = []
        for dpoint in val:
            fullname = relativename = crlissuer = reasons = None
            if isinstance(dpoint, dict):
                fullname = dpoint.get("fullname")
                relativename = dpoint.get("relativename")
                crlissuer = dpoint.get("crlissuer")
                reasons = dpoint.get("reasons")
                if fullname:
                    if not isinstance(fullname, list):
                        fullname = [fullname]
                    fullname = (x.split(":", maxsplit=1) for x in fullname)
                if relativename:
                    relativename = _get_rdn(relativename)
                if crlissuer:
                    if not isinstance(crlissuer, list):
                        crlissuer = [crlissuer]
                    crlissuer = _parse_general_names(
                        x.split(":", maxsplit=1) for x in crlissuer
                    )
                if reasons:
                    try:
                        reasons = frozenset(cx509.ReasonFlags(x) for x in reasons)
                    except ValueError as err:
                        raise SaltInvocationError(err) from err
            else:
                fullname = (dpoint,)
            if fullname:
                fullname = _parse_general_names(fullname)
            try:
                parsed.append(
                    cx509.DistributionPoint(
                        full_name=fullname,
                        relative_name=relativename,
                        reasons=reasons,
                        crl_issuer=crlissuer,
                    )
                )
            except (ValueError, TypeError) as err:
                raise SaltInvocationError(err) from err
        if "freshestCRL" == name:
            return cx509.FreshestCRL(parsed), False  # must be non-critical
        return cx509.CRLDistributionPoints(parsed), critical

    if "issuingDistributionPoint" == name:
        if not isinstance(val, dict):
            raise SaltInvocationError("issuingDistributionPoint must be a dictionary")
        critical = val.get("critical", False)
        onlyuser = val.get("onlyuser", False)
        onlyca = val.get("onlyCA", False)
        onlyaa = val.get("onlyAA", False)
        indirectcrl = val.get("indirectCRL", False)
        fullname = val.get("fullname")
        relativename = val.get("relativename")
        onlysomereasons = val.get("onlysomereasons")
        if fullname:
            if not isinstance(fullname, list):
                fullname = [fullname]
            fullname = (x.split(":", maxsplit=1) for x in fullname)
            fullname = _parse_general_names(fullname)
        if relativename:
            relativename = _get_rdn(relativename)
        if onlysomereasons:
            try:
                onlysomereasons = frozenset(
                    cx509.ReasonFlags(x) for x in onlysomereasons
                )
            except ValueError as err:
                raise SaltInvocationError(err) from err
        try:
            return (
                cx509.IssuingDistributionPoint(
                    full_name=fullname,
                    relative_name=relativename,
                    only_contains_user_certs=onlyuser,
                    only_contains_ca_certs=onlyca,
                    only_some_reasons=onlysomereasons,
                    indirect_crl=indirectcrl,
                    only_contains_attribute_certs=onlyaa,
                ),
                critical,
            )
        except (ValueError, TypeError) as err:
            raise SaltInvocationError(err) from err

    if "certificatePolicies" == name:
        if isinstance(val, str):
            try:
                critical = val.startswith("critical")
                policy_identifiers = (
                    _get_oid(x.strip())
                    for x in val.split(",")
                    if "critical" != x.strip()
                )
                policy_information = [
                    cx509.PolicyInformation(policy_identifier=p, policy_qualifiers=None)
                    for p in policy_identifiers
                ]
                return cx509.CertificatePolicies(policy_information), critical
            except CommandExecutionError as err:
                raise SaltInvocationError(
                    "certificatePolicies defined as string must be a "
                    "comma-separated list of OID."
                ) from err
        critical = val.get("critical", False)
        parsed = []
        for polid, qualifiers in val.items():
            if "critical" == polid:
                continue
            parsed_qualifiers = []
            for qual in qualifiers:
                if isinstance(qual, str):
                    # pointer to the practice statement published by the certificate authority
                    parsed_qualifiers.append(qual)
                    continue
                notice = None
                organization = qual.get("organization")
                notice_numbers = qual.get("noticeNumbers")
                text = qual.get("text")
                if notice_numbers:
                    try:
                        notice = cx509.NoticeReference(
                            organization=organization, notice_numbers=notice_numbers
                        )
                    except TypeError as err:
                        raise CommandExecutionError(err) from err
                    parsed_qualifiers.append(
                        cx509.UserNotice(notice_reference=notice, explicit_text=text)
                    )
            parsed.append(
                cx509.PolicyInformation(
                    policy_identifier=_get_oid(polid),
                    policy_qualifiers=parsed_qualifiers,
                )
            )
        return cx509.CertificatePolicies(parsed), critical

    if "policyConstraints" == name:
        critical = "critical" in val
        if isinstance(val, str):
            val, critical = _deserialize_openssl_confstring(val)
        args = {
            "require_explicit_policy": int(val["requireExplicitPolicy"])
            if "requireExplicitPolicy" in val
            else None,
            "inhibit_policy_mapping": int(val["inhibitPolicyMapping"])
            if "inhibitPolicyMapping" in val
            else None,
        }
        try:
            # not sure why pylint complains about this line having kwargs from keyUsage
            # pylint: disable=unexpected-keyword-arg
            return cx509.PolicyConstraints(**args), critical
        except (TypeError, ValueError) as err:
            raise SaltInvocationError(err) from err

    if "inhibitAnyPolicy" == name:
        critical = "critical" in val if not isinstance(val, int) else False
        if isinstance(val, str):
            val, critical = _deserialize_openssl_confstring(val)
            val = int(next(iter(val)))
        try:
            return (
                cx509.InhibitAnyPolicy(val if isinstance(val, int) else val["value"]),
                critical,
            )
        except KeyError as err:
            raise SaltInvocationError(
                f"Undefined required key for {name}: {err}"
            ) from err
        except (TypeError, ValueError) as err:
            raise SaltInvocationError(err) from err

    if "nameConstraints" == name:
        critical = "critical" in val
        if isinstance(val, dict):
            parsed = {}
            for scope, constraints in val.items():
                if scope not in ("permitted", "excluded"):
                    continue
                list_ = []
                for x in constraints:
                    if isinstance(x, str) and ":" in x:
                        k, v = x.split(":", maxsplit=1)
                        list_.append((k.strip(), v.strip()))
                    elif x != "critical":
                        list_.append(x)
                parsed[scope] = tuple(list_)
            val = parsed
        elif isinstance(val, str):
            items = tuple(x.strip().split(";") for x in val.split(","))
            val = {
                "permitted": [
                    x[1].split(":", maxsplit=1) for x in items if "permitted" == x[0]
                ],
                "excluded": [
                    x[1].split(":", maxsplit=1) for x in items if "excluded" == x[0]
                ],
            }
        args = {
            "permitted_subtrees": _parse_general_names(val["permitted"])
            if "permitted" in val
            else None,
            "excluded_subtrees": _parse_general_names(val["excluded"])
            if "excluded" in val
            else None,
        }
        if not any(args.values()):
            raise SaltInvocationError("nameConstraints needs at least one definition")
        return cx509.NameConstraints(**args), critical

    if "noCheck" == name:
        return cx509.OCSPNoCheck(), "critical" in str(val)

    if "tlsfeature" == name:
        if isinstance(val, str):
            val = [x.strip() for x in val.split(",")]
        critical = "critical" in val
        try:
            types = [getattr(cx509.TLSFeatureType, x) for x in val if "critical" != x]
        except ValueError as err:
            raise SaltInvocationError(err) from err
        return cx509.TLSFeature(types), critical

    if "nsComment" == name:
        raise SaltInvocationError("nsComment is currently not implemented.")

    if "nsCertType" == name:
        raise SaltInvocationError("nsCertType is currently not implemented.")

    if "cRLNumber" == name:
        try:
            return cx509.CRLNumber(int(val)), False
        except ValueError as err:
            raise SaltInvocationError(
                "cRLNumber must be an integer and must be marked as non-critical"
            ) from err

    if "deltaCRLIndicator" == name:
        critical = "critical" in str(val)
        val = re.findall(r"[\d]+", str(val))
        if len(val) != 1:
            raise SaltInvocationError(
                "deltaCRLIndicator must contain a single integer pointing to a cRLNumber"
            )
        return cx509.DeltaCRLIndicator(int(val[0])), critical

    if "CRLReason" == name:
        critical = False
        if isinstance(val, str):
            val, critical = _deserialize_openssl_confstring(val)
        else:
            if "critical" in val:
                critical = True
                val = [x for x in val if "critical" != x]

        try:
            return cx509.CRLReason(cx509.ReasonFlags(next(iter(val)))), critical
        except ValueError as err:
            raise SaltInvocationError(str(err)) from err

    if "invalidityDate" == name:
        if not isinstance(val, str):
            raise SaltInvocationError("invalidityDate must be a string")
        critical = val.startswith("critical")
        if critical:
            val = val.split(" ", maxsplit=1)[1]
        try:
            return (
                cx509.InvalidityDate(datetime.datetime.strptime(val, TIME_FMT)),
                critical,
            )
        except ValueError as err:
            raise SaltInvocationError(str(err)) from err

    raise CommandExecutionError(f"Unknown extension {name}")


def _deserialize_openssl_confstring(conf, multiple=False):
    critical = conf.startswith("critical")
    if critical:
        conf = conf[8:].strip(",").strip()
    items = (x.strip() for x in conf.split(","))
    if multiple:
        return (
            (k.strip(), v.strip())
            for k, v in (
                x.split(":", maxsplit=1) if ":" in x else (x, "__present__")
                for x in items
            )
        ), critical
    return {
        k.strip(): v.strip()
        for k, v in (
            x.split(":", maxsplit=1) if ":" in x else (x, "__present__") for x in items
        )
    }, critical


def _parse_general_names(val):
    def idna_encode(val, allow_leading_dot=False):
        if HAS_IDNA:
            # A leading dot is allowed in some values.
            # idna complains about it not being a valid domain name
            has_dot = False
            if allow_leading_dot:
                has_dot = val.startswith(".")
                val = val.lstrip(".")
            ret = idna.encode(val).decode()
            if has_dot:
                return f".{ret}"
            return ret
        else:
            try:
                val.encode(encoding="ascii")
            except UnicodeEncodeError as err:
                raise CommandExecutionError(
                    "Cannot encode non-ASCII strings to internationalized domain "
                    "name format, missing library: idna"
                ) from err

    valid_types = {
        "email": cx509.general_name.RFC822Name,
        "uri": cx509.general_name.UniformResourceIdentifier,
        "dns": cx509.general_name.DNSName,
        "rid": cx509.general_name.RegisteredID,
        "ip": cx509.general_name.IPAddress,
        "dirname": cx509.general_name.DirectoryName,
        # othername currently not implemented
    }

    parsed = []
    for typ, v in val:
        typ = typ.lower()
        if "dirname" == typ:
            v = _get_dn(v)
        elif "rid" == typ:
            v = _get_oid(v)
        elif "ip" == typ:
            try:
                v = ipaddress.ip_address(v)
            except ValueError:
                try:
                    v = ipaddress.ip_network(v)
                except ValueError as err:
                    raise CommandExecutionError(
                        f"Provided value {v} does not seem to be an IP address or network range."
                    ) from err
        elif "email" == typ:
            splits = v.rsplit("@", maxsplit=1)
            if len(splits) > 1:
                user, domain = splits
                domain = idna_encode(domain)
                v = "@".join((user, domain))
            else:
                v = idna_encode(splits[0], allow_leading_dot=True)
        elif "uri" == typ:
            url = urlparse(v)
            if url.netloc:
                domain = idna_encode(url.netloc)
                v = urlunparse(
                    (url.scheme, domain, url.path, url.params, url.query, url.fragment)
                )
        elif "dns" == typ:
            v = idna_encode(v, allow_leading_dot=True)
        elif "othername" == typ:
            raise SaltInvocationError("otherName is currently not implemented")
        if typ in valid_types:
            try:
                parsed.append(valid_types[typ](v))
                continue
            except (ValueError, TypeError) as err:
                raise CommandExecutionError(err) from err
        raise CommandExecutionError(f"GeneralName type {typ} is invalid")
    return parsed


def _get_oid(oid):
    if not str(oid).startswith(("0", "1", "2")) or str(oid).strip("0123456789."):
        raise CommandExecutionError(f"Invalid oid: {oid}")
    return cx509.ObjectIdentifier(oid)


def _get_rdn(rdn):
    try:
        rdns = cx509.Name.from_rfc4514_string(rdn).rdns
        if len(rdns) > 1:
            raise SaltInvocationError(
                "Specified string is not a Relative Distinguished Name, "
                "but a Distinguished Name."
            )
        return rdns[0]
    except ValueError as err:
        raise CommandExecutionError(f"Failed parsing rdn string: {rdn}") from err
    except AttributeError as err:
        raise CommandExecutionError(
            "At least cryptography v37 is required for parsing RFC4514 strings."
        ) from err


def _get_gn(gn):
    return _parse_general_names((gn.split(":", maxsplit=1),))[0]


def _get_serial_number(sn=None):
    if sn is None:
        return cx509.random_serial_number()
    if isinstance(sn, int):
        return sn
    try:
        sn = bytes.fromhex(sn.replace(":", ""))
    except (AttributeError, TypeError, ValueError):
        pass
    if isinstance(sn, bytes):
        return int.from_bytes(sn, "big")
    raise CommandExecutionError(f"Could not parse serial number {sn}")


def _get_dn(dn):
    if isinstance(dn, str):
        try:
            parsed = cx509.Name.from_rfc4514_string(dn)
            if CRYPTOGRAPHY_VERSION[0] == 37:
                return cx509.Name(parsed.rdns[::-1])
            return parsed
        except ValueError as err:
            raise CommandExecutionError(
                "Failed parsing rfc4514 dirName string"
            ) from err
        except AttributeError as err:
            raise CommandExecutionError(
                "At least cryptography v37 is required for parsing RFC4514 strings."
            ) from err
    elif isinstance(dn, list):
        return cx509.Name([_get_rdn(x) for x in dn])
    elif isinstance(dn, dict):
        parsed = []
        for name, oid in NAME_OID.items():
            if name in dn:
                parsed.append(cx509.NameAttribute(oid, dn[name]))
        return cx509.Name(parsed)

    raise SaltInvocationError("Need string, list or dict to parse distinguished names")


def pretty_hex(hex_str):
    """
    Nicely formats hex strings
    """
    if isinstance(hex_str, bytes):
        hex_str = hex_str.hex()
    if len(hex_str) % 2 != 0:
        hex_str = "0" + hex_str
    return ":".join([hex_str[i : i + 2] for i in range(0, len(hex_str), 2)]).upper()


def dec2hex(decval):
    """
    Converts decimal values to nicely formatted hex strings
    """
    return pretty_hex(f"{decval:X}")


def render_gn(gn):
    """
    Returns a valid OpenSSL string for a GeneralName instance
    """
    if isinstance(gn, cx509.DNSName):
        return f"DNS:{gn.value}"
    if isinstance(gn, cx509.DirectoryName):
        return f"dirName:{gn.value.rfc4514_string()}"
    if isinstance(gn, cx509.IPAddress):
        return f"IP:{gn.value.exploded}"
    if isinstance(gn, cx509.RFC822Name):
        return f"mail:{gn.value}"
    if isinstance(gn, cx509.RegisteredID):
        return f"RID:{gn.value.dotted_string}"
    if isinstance(gn, cx509.UniformResourceIdentifier):
        return f"URI:{gn.value}"
    return str(gn)


def render_extension(ext):
    """
    Render an Extension instance to a dict for informational purposes
    """
    ret = {"critical": ext.critical}
    if isinstance(ext.value, cx509.BasicConstraints):
        ret.update({"ca": ext.value.ca, "pathlen": ext.value.path_length})
        return ret

    if isinstance(ext.value, cx509.KeyUsage):
        ret.update(
            {
                "cRLSign": ext.value.crl_sign,
                "dataEncipherment": ext.value.data_encipherment,
                "decipherOnly": ext.value.decipher_only
                if ext.value.key_agreement
                else False,
                "digitalSignature": ext.value.digital_signature,
                "encipherOnly": ext.value.encipher_only
                if ext.value.key_agreement
                else False,
                "keyAgreement": ext.value.key_agreement,
                "keyCertSign": ext.value.key_cert_sign,
                "keyEncipherment": ext.value.key_encipherment,
                "nonRepudiation": ext.value.content_commitment,
            }
        )
        return ret

    if isinstance(ext.value, cx509.ExtendedKeyUsage):
        # this does not account for unnamed OIDs
        try:
            usages = [
                x._name if x._name != "Unknown OID" else x.dotted_string
                for x in ext.value._usages or []
            ]
        except AttributeError:
            # best effort in case x._name becomes undefined at some point
            usages = re.findall(
                r"\<ObjectIdentifier\(oid=[\d\.]+, name=([\w]+)\)\>", str(ext.value)
            )
            usages = [x[1] if "Unknown OID" != x[1] else x[0] for x in usages]
        ret["value"] = usages
        return ret

    if isinstance(ext.value, cx509.SubjectKeyIdentifier):
        ret["value"] = pretty_hex(ext.value.digest)
        return ret

    if isinstance(ext.value, cx509.AuthorityKeyIdentifier):
        ret.update(
            {
                "keyid": pretty_hex(ext.value.key_identifier)
                if ext.value.key_identifier
                else None,
                "issuer": [render_gn(x) for x in ext.value.authority_cert_issuer or []]
                or None,
                "issuer_sn": dec2hex(ext.value.authority_cert_serial_number)
                if ext.value.authority_cert_serial_number
                else None,
            }
        )
        return ret

    if isinstance(
        ext.value,
        (
            cx509.IssuerAlternativeName,
            cx509.CertificateIssuer,
            cx509.SubjectAlternativeName,
        ),
    ):
        try:
            ret["value"] = [
                render_gn(x) for x in ext.value._general_names._general_names or []
            ]
        except AttributeError:
            # best effort in case ext.value._general_names._general_names
            # becomes undefined at some point
            prefixes = {
                "DNSName": "dns",
                "RFC822Name": "email",
                "UniformResourceIdentifier": "url",
                "RegisteredID": "rid",
                "IPAddress": "ip",
                "DirectoryName": "dirName",
            }
            ret["value"] = [
                f"{prefixes[typ]}:{gn}"
                for typ, gn in re.findall(
                    rf"\<({'|'.join(prefixes)})\(value='([^']+)'\)\>",
                    str(ext.value),
                )
            ]
        return ret

    if isinstance(ext.value, cx509.AuthorityInformationAccess):
        try:
            ret["value"] = []
            for description in ext.value._descriptions:
                ret["value"].append(
                    {
                        description.access_method._name
                        if description.access_method._name != "Unknown OID"
                        else description.access_method.dotted_string: render_gn(
                            description.access_location.value
                        )
                    }
                )
        except AttributeError:
            ret["value"] = str(ext.value)
        return ret

    if isinstance(ext.value, (cx509.CRLDistributionPoints, cx509.FreshestCRL)):
        try:
            dpoints = []
            for dpoint in ext.value._distribution_points:
                dpoints.append(
                    {
                        "crlissuer": [render_gn(x) for x in dpoint.crl_issuer or []],
                        "fullname": [render_gn(x) for x in dpoint.full_name or []],
                        "reasons": list(sorted(x.value for x in dpoint.reasons or [])),
                        "relativename": dpoint.relative_name.rfc4514_string()
                        if dpoint.relative_name
                        else None,
                    }
                )
            ret["value"] = dpoints
        except AttributeError:
            ret["value"] = str(ext.value)
        return ret

    if isinstance(ext.value, cx509.IssuingDistributionPoint):
        ret.update(
            {
                "fullname": [render_gn(x) for x in ext.value.full_name or []],
                "onysomereasons": list(
                    sorted(x.value for x in ext.value.only_some_reasons or [])
                ),
                "relativename": ext.value.relative_name.rfc4514_string()
                if ext.value.relative_name
                else None,
                "onlyuser": ext.value.only_contains_user_certs,
                "onlyCA": ext.value.only_contains_ca_certs,
                "onlyAA": ext.value.only_contains_attribute_certs,
                "indirectCRL": ext.value.indirect_crl,
            }
        )
        return ret

    if isinstance(ext.value, cx509.CertificatePolicies):
        try:
            policies = []
            for policy in ext.value._policies:
                polid = policy.policy_identifier._name
                if "Unknown OID" == polid:
                    polid = policy.policy_identifier.dotted_string
                qualifiers = []
                for notice in policy.policy_qualifiers or []:
                    if isinstance(notice, str):
                        qualifiers.append({"practice_statement": notice})
                        continue
                    organization = notice_numbers = None
                    if notice.notice_reference:
                        organization = notice.notice_reference.organization
                        notice_numbers = notice.notice_reference.notice_numbers
                    qualifiers.append(
                        {
                            "organizataion": organization,
                            "notice_numbers": notice_numbers,
                            "explicit_text": notice.explicit_text,
                        }
                    )
                policies.append({polid: qualifiers})
            ret["value"] = policies
        except AttributeError:
            ret["value"] = str(ext.value)
        return ret

    if isinstance(ext.value, cx509.PolicyConstraints):
        ret.update(
            {
                "inhibitPolicyMapping": ext.value.inhibit_policy_mapping,
                "requireExplicitPolicy": ext.value.require_explicit_policy,
            }
        )
        return ret

    if isinstance(ext.value, cx509.InhibitAnyPolicy):
        ret["value"] = ext.value.skip_certs
        return ret

    if isinstance(ext.value, cx509.NameConstraints):
        ret.update(
            {
                "excluded": [render_gn(x) for x in ext.value.excluded_subtrees or []],
                "permitted": [render_gn(x) for x in ext.value.permitted_subtrees or []],
            }
        )
        return ret

    if isinstance(ext.value, cx509.OCSPNoCheck):
        ret["value"] = True
        return ret

    if isinstance(ext.value, cx509.TLSFeature):
        try:
            ret["value"] = [x.name for x in ext.value._features]
        except AttributeError:
            features = []
            if "status_request" in str(ext.value):
                features.append("status_request")
            if "status_request_v2" in str(ext.value):
                features.append("status_request_v2")
            ret["value"] = features
        return ret

    if isinstance(ext.value, cx509.CRLNumber):
        ret["value"] = ext.value.crl_number
        return ret

    if isinstance(ext.value, cx509.DeltaCRLIndicator):
        ret["value"] = ext.value.crl_number
        return ret

    if isinstance(ext.value, cx509.CRLReason):
        ret["value"] = ext.value.reason.value
        return ret

    if isinstance(ext.value, cx509.InvalidityDate):
        ret["value"] = ext.value.invalidity_date.strftime(TIME_FMT)
        return ret

    ret["value"] = str(ext.value)
    return ret
