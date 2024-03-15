"""
Common code shared between the nacl module and runner.
"""

import base64
import os

import salt.syspaths
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
import salt.utils.versions
import salt.utils.win_dacl
import salt.utils.win_functions

REQ_ERROR = None
try:
    import nacl.public  # pylint: disable=no-name-in-module
    import nacl.secret  # pylint: disable=no-name-in-module
except ImportError:
    REQ_ERROR = (
        "PyNaCl import error, perhaps missing python PyNaCl package or should update."
    )

__virtualname__ = "nacl"


def __virtual__():
    if __opts__["fips_mode"] is True:
        return False, "nacl utils not available in FIPS mode"
    return check_requirements()


def check_requirements():
    """
    Check required libraries are available
    """
    return (REQ_ERROR is None, REQ_ERROR)


def _get_config(**kwargs):
    """
    Return configuration
    """
    sk_file = kwargs.get("sk_file")
    if not sk_file:
        sk_file = os.path.join(kwargs["opts"].get("pki_dir"), "master/nacl")

    pk_file = kwargs.get("pk_file")
    if not pk_file:
        pk_file = os.path.join(kwargs["opts"].get("pki_dir"), "master/nacl.pub")

    config = {
        "box_type": kwargs.get("box_type", "sealedbox"),
        "sk": None,
        "sk_file": sk_file,
        "pk": None,
        "pk_file": pk_file,
    }

    config_key = f"{__virtualname__}.config"
    try:
        config.update(__salt__["config.get"](config_key, {}))
    except (NameError, KeyError) as e:
        # likely using salt-run so fallback to __opts__
        config.update(kwargs["opts"].get(config_key, {}))
    # pylint: disable=C0201
    for k in set(config.keys()) & set(kwargs.keys()):
        config[k] = kwargs[k]
    return config


def _get_sk(**kwargs):
    """
    Return sk
    """
    config = _get_config(**kwargs)
    key = None
    if config["sk"]:
        key = salt.utils.stringutils.to_str(config["sk"])
    sk_file = config["sk_file"]
    if not key and sk_file:
        try:
            with salt.utils.files.fopen(sk_file, "rb") as keyf:
                key = salt.utils.stringutils.to_unicode(keyf.read()).rstrip("\n")
        except OSError:
            raise Exception("no key or sk_file found")
    return base64.b64decode(key)


def _get_pk(**kwargs):
    """
    Return pk
    """
    config = _get_config(**kwargs)
    pubkey = None
    if config["pk"]:
        pubkey = salt.utils.stringutils.to_str(config["pk"])
    pk_file = config["pk_file"]
    if not pubkey and pk_file:
        try:
            with salt.utils.files.fopen(pk_file, "rb") as keyf:
                pubkey = salt.utils.stringutils.to_unicode(keyf.read()).rstrip("\n")
        except OSError:
            raise Exception("no pubkey or pk_file found")
    pubkey = str(pubkey)
    return base64.b64decode(pubkey)


def keygen(sk_file=None, pk_file=None, **kwargs):
    """
    Use PyNaCl to generate a keypair.

    If no `sk_file` is defined return a keypair.

    If only the `sk_file` is defined `pk_file` will use the same name with a postfix `.pub`.

    When the `sk_file` is already existing, but `pk_file` is not. The `pk_file` will be generated
    using the `sk_file`.

    CLI Examples:

    .. code-block:: bash

        salt-call nacl.keygen
        salt-call nacl.keygen sk_file=/etc/salt/pki/master/nacl
        salt-call nacl.keygen sk_file=/etc/salt/pki/master/nacl pk_file=/etc/salt/pki/master/nacl.pub
        salt-call --local nacl.keygen

    sk_file
      Path to where there secret key exists.
      The argrument ``keyfile`` was deprecated
      in favor of ``sk_file``. ``keyfile`` will
      continue to work to ensure backwards
      compatbility, but please use the preferred
      ``sk_file``.
    """
    if "keyfile" in kwargs:
        sk_file = kwargs["keyfile"]

    if sk_file is None:
        kp = nacl.public.PrivateKey.generate()
        return {
            "sk": base64.b64encode(kp.encode()),
            "pk": base64.b64encode(kp.public_key.encode()),
        }

    if pk_file is None:
        pk_file = f"{sk_file}.pub"

    if sk_file and pk_file is None:
        if not os.path.isfile(sk_file):
            kp = nacl.public.PrivateKey.generate()
            with salt.utils.files.fopen(sk_file, "wb") as keyf:
                keyf.write(base64.b64encode(kp.encode()))
            if salt.utils.platform.is_windows():
                cur_user = salt.utils.win_functions.get_current_user()
                salt.utils.win_dacl.set_owner(sk_file, cur_user)
                salt.utils.win_dacl.set_permissions(
                    sk_file,
                    cur_user,
                    "full_control",
                    "grant",
                    reset_perms=True,
                    protected=True,
                )
            else:
                # chmod 0600 file
                os.chmod(sk_file, 1536)
            return f"saved sk_file: {sk_file}"
        else:
            raise Exception(f"sk_file:{sk_file} already exist.")

    if sk_file is None and pk_file:
        raise Exception("sk_file: Must be set inorder to generate a public key.")

    if os.path.isfile(sk_file) and os.path.isfile(pk_file):
        raise Exception(f"sk_file:{sk_file} and pk_file:{pk_file} already exist.")

    if os.path.isfile(sk_file) and not os.path.isfile(pk_file):
        # generate pk using the sk
        with salt.utils.files.fopen(sk_file, "rb") as keyf:
            sk = salt.utils.stringutils.to_unicode(keyf.read()).rstrip("\n")
            sk = base64.b64decode(sk)
        kp = nacl.public.PublicKey(sk)
        with salt.utils.files.fopen(pk_file, "wb") as keyf:
            keyf.write(base64.b64encode(kp.encode()))
        return f"saved pk_file: {pk_file}"

    kp = nacl.public.PublicKey.generate()
    with salt.utils.files.fopen(sk_file, "wb") as keyf:
        keyf.write(base64.b64encode(kp.encode()))
    if salt.utils.platform.is_windows():
        cur_user = salt.utils.win_functions.get_current_user()
        salt.utils.win_dacl.set_owner(sk_file, cur_user)
        salt.utils.win_dacl.set_permissions(
            sk_file, cur_user, "full_control", "grant", reset_perms=True, protected=True
        )
    else:
        # chmod 0600 file
        os.chmod(sk_file, 1536)
    with salt.utils.files.fopen(pk_file, "wb") as keyf:
        keyf.write(base64.b64encode(kp.encode()))
    return f"saved sk_file:{sk_file}  pk_file: {pk_file}"


def enc(data, **kwargs):
    """
    Alias to `{box_type}_encrypt`

    box_type: secretbox, sealedbox(default)

    sk_file
      Path to where there secret key exists.
      The argrument ``keyfile`` was deprecated
      in favor of ``sk_file``. ``keyfile`` will
      continue to work to ensure backwards
      compatbility, but please use the preferred
      ``sk_file``.
    sk
      Secret key contents. The argument ``key``
      was deprecated in favor of ``sk``. ``key``
      will continue to work to ensure backwards
      compatibility, but please use the preferred
      ``sk``.
    """
    if "keyfile" in kwargs:
        kwargs["sk_file"] = kwargs["keyfile"]

        # set boxtype to `secretbox` to maintain backward compatibility
        kwargs["box_type"] = "secretbox"

    if "key" in kwargs:
        kwargs["sk"] = kwargs["key"]

        # set boxtype to `secretbox` to maintain backward compatibility
        kwargs["box_type"] = "secretbox"

    box_type = _get_config(**kwargs)["box_type"]
    if box_type == "secretbox":
        return secretbox_encrypt(data, **kwargs)
    return sealedbox_encrypt(data, **kwargs)


def enc_file(name, out=None, **kwargs):
    """
    This is a helper function to encrypt a file and return its contents.

    You can provide an optional output file using `out`

    `name` can be a local file or when not using `salt-run` can be a url like `salt://`, `https://` etc.

    CLI Examples:

    .. code-block:: bash

        salt-run nacl.enc_file name=/tmp/id_rsa
        salt-call nacl.enc_file name=salt://crt/mycert out=/tmp/cert
        salt-run nacl.enc_file name=/tmp/id_rsa box_type=secretbox \
            sk_file=/etc/salt/pki/master/nacl.pub
    """
    try:
        data = __salt__["cp.get_file_str"](name)
    except Exception as e:  # pylint: disable=broad-except
        # likly using salt-run so fallback to local filesystem
        with salt.utils.files.fopen(name, "rb") as f:
            data = salt.utils.stringutils.to_unicode(f.read())
    d = enc(data, **kwargs)
    if out:
        if os.path.isfile(out):
            raise Exception(f"file:{out} already exist.")
        with salt.utils.files.fopen(out, "wb") as f:
            f.write(salt.utils.stringutils.to_bytes(d))
        return f"Wrote: {out}"
    return d


def dec(data, **kwargs):
    """
    Alias to `{box_type}_decrypt`

    box_type: secretbox, sealedbox(default)

    sk_file
      Path to where there secret key exists.
      The argrument ``keyfile`` was deprecated
      in favor of ``sk_file``. ``keyfile`` will
      continue to work to ensure backwards
      compatbility, but please use the preferred
      ``sk_file``.
    sk
      Secret key contents. The argument ``key``
      was deprecated in favor of ``sk``. ``key``
      will continue to work to ensure backwards
      compatibility, but please use the preferred
      ``sk``.
    """
    if "keyfile" in kwargs:
        kwargs["sk_file"] = kwargs["keyfile"]

        # set boxtype to `secretbox` to maintain backward compatibility
        kwargs["box_type"] = "secretbox"

    if "key" in kwargs:
        kwargs["sk"] = kwargs["key"]

        # set boxtype to `secretbox` to maintain backward compatibility
        kwargs["box_type"] = "secretbox"

    box_type = _get_config(**kwargs)["box_type"]
    if box_type == "secretbox":
        return secretbox_decrypt(data, **kwargs)

    return sealedbox_decrypt(data, **kwargs)


def dec_file(name, out=None, **kwargs):
    """
    This is a helper function to decrypt a file and return its contents.

    You can provide an optional output file using `out`

    `name` can be a local file or when not using `salt-run` can be a url like `salt://`, `https://` etc.

    CLI Examples:

    .. code-block:: bash

        salt-run nacl.dec_file name=/tmp/id_rsa.nacl
        salt-call nacl.dec_file name=salt://crt/mycert.nacl out=/tmp/id_rsa
        salt-run nacl.dec_file name=/tmp/id_rsa.nacl box_type=secretbox \
            sk_file=/etc/salt/pki/master/nacl.pub
    """
    try:
        data = __salt__["cp.get_file_str"](name)
    except Exception as e:  # pylint: disable=broad-except
        # likly using salt-run so fallback to local filesystem
        with salt.utils.files.fopen(name, "rb") as f:
            data = salt.utils.stringutils.to_unicode(f.read())
    d = dec(data, **kwargs)
    if out:
        if os.path.isfile(out):
            raise Exception(f"file:{out} already exist.")
        with salt.utils.files.fopen(out, "wb") as f:
            f.write(salt.utils.stringutils.to_bytes(d))
        return f"Wrote: {out}"
    return d


def sealedbox_encrypt(data, **kwargs):
    """
    Encrypt data using a public key generated from `nacl.keygen`.
    The encryptd data can be decrypted using `nacl.sealedbox_decrypt` only with the secret key.

    CLI Examples:

    .. code-block:: bash

        salt-run nacl.sealedbox_encrypt datatoenc
        salt-call --local nacl.sealedbox_encrypt datatoenc pk_file=/etc/salt/pki/master/nacl.pub
        salt-call --local nacl.sealedbox_encrypt datatoenc pk='vrwQF7cNiNAVQVAiS3bvcbJUnF0cN6fU9YTZD9mBfzQ='
    """
    # ensure data is in bytes
    data = salt.utils.stringutils.to_bytes(data)

    pk = _get_pk(**kwargs)
    keypair = nacl.public.PublicKey(pk)
    b = nacl.public.SealedBox(keypair)
    return base64.b64encode(b.encrypt(data))


def sealedbox_decrypt(data, **kwargs):
    """
    Decrypt data using a secret key that was encrypted using a public key with `nacl.sealedbox_encrypt`.

    CLI Examples:

    .. code-block:: bash

        salt-call nacl.sealedbox_decrypt pEXHQM6cuaF7A=
        salt-call --local nacl.sealedbox_decrypt data='pEXHQM6cuaF7A=' sk_file=/etc/salt/pki/master/nacl
        salt-call --local nacl.sealedbox_decrypt data='pEXHQM6cuaF7A=' sk='YmFkcGFzcwo='
    """
    if data is None:
        return None

    # ensure data is in bytes
    data = salt.utils.stringutils.to_bytes(data)

    sk = _get_sk(**kwargs)
    keypair = nacl.public.PrivateKey(sk)
    b = nacl.public.SealedBox(keypair)
    return b.decrypt(base64.b64decode(data))


def secretbox_encrypt(data, **kwargs):
    """
    Encrypt data using a secret key generated from `nacl.keygen`.
    The same secret key can be used to decrypt the data using `nacl.secretbox_decrypt`.

    CLI Examples:

    .. code-block:: bash

        salt-run nacl.secretbox_encrypt datatoenc
        salt-call --local nacl.secretbox_encrypt datatoenc sk_file=/etc/salt/pki/master/nacl
        salt-call --local nacl.secretbox_encrypt datatoenc sk='YmFkcGFzcwo='
    """
    # ensure data is in bytes
    data = salt.utils.stringutils.to_bytes(data)

    sk = _get_sk(**kwargs)
    b = nacl.secret.SecretBox(sk)
    return base64.b64encode(b.encrypt(data))


def secretbox_decrypt(data, **kwargs):
    """
    Decrypt data that was encrypted using `nacl.secretbox_encrypt` using the secret key
    that was generated from `nacl.keygen`.

    CLI Examples:

    .. code-block:: bash

        salt-call nacl.secretbox_decrypt pEXHQM6cuaF7A=
        salt-call --local nacl.secretbox_decrypt data='pEXHQM6cuaF7A=' sk_file=/etc/salt/pki/master/nacl
        salt-call --local nacl.secretbox_decrypt data='pEXHQM6cuaF7A=' sk='YmFkcGFzcwo='
    """
    if data is None:
        return None

    # ensure data is in bytes
    data = salt.utils.stringutils.to_bytes(data)

    key = _get_sk(**kwargs)
    b = nacl.secret.SecretBox(key=key)
    return b.decrypt(base64.b64decode(data))
