try:
    import M2Crypto

    HAS_M2 = True
except ImportError:
    HAS_M2 = False

try:
    from Cryptodome.PublicKey import RSA

    HAS_PYCRYPTO_RSA = True
except ImportError:
    HAS_PYCRYPTO_RSA = False

if not HAS_PYCRYPTO_RSA:
    try:
        from Crypto.PublicKey import RSA  # nosec

        HAS_PYCRYPTO_RSA = True
    except ImportError:
        HAS_PYCRYPTO_RSA = False
