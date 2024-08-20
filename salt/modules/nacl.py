"""
This module helps include encrypted passwords in pillars, grains and salt state files.

:depends: PyNaCl, https://github.com/pyca/pynacl

This is often useful if you wish to store your pillars in source control or
share your pillar data with others that you trust. I don't advise making your pillars public
regardless if they are encrypted or not.

When generating keys and encrypting passwords use --local when using salt-call for extra
security. Also consider using just the salt runner nacl when encrypting pillar passwords.

:configuration: The following configuration defaults can be
    define (pillar or config files) Avoid storing private keys in pillars! Ensure master does not have `pillar_opts=True`:

    .. code-block:: python

        # cat /etc/salt/master.d/nacl.conf
        nacl.config:
            # NOTE: `key` and `key_file` have been renamed to `sk`, `sk_file`
            # also `box_type` default changed from secretbox to sealedbox.
            box_type: sealedbox                     (default)
            sk_file: /etc/salt/pki/master/nacl      (default)
            pk_file: /etc/salt/pki/master/nacl.pub  (default)
            sk: None
            pk: None

    Usage can override the config defaults:

    .. code-block:: bash

        salt-call nacl.enc sk_file=/etc/salt/pki/master/nacl pk_file=/etc/salt/pki/master/nacl.pub


The nacl lib uses 32byte keys, these keys are base64 encoded to make your life more simple.
To generate your `sk_file` and `pk_file` use:

.. code-block:: bash

    salt-call --local nacl.keygen sk_file=/etc/salt/pki/master/nacl
    # or if you want to work without files.
    salt-call --local nacl.keygen
    local:
        ----------
        pk:
            /kfGX7PbWeu099702PBbKWLpG/9p06IQRswkdWHCDk0=
        sk:
            SVWut5SqNpuPeNzb1b9y6b2eXg2PLIog43GBzp48Sow=

Now with your keypair, you can encrypt data:

You have two option, `sealedbox` or `secretbox`.

SecretBox is data encrypted using private key `pk`. Sealedbox is encrypted using public key `pk`.

Recommend using Sealedbox because the one way encryption permits developers to encrypt data for source control but not decrypt.
Sealedbox only has one key that is for both encryption and decryption.

.. code-block:: bash

    salt-call --local nacl.enc asecretpass pk=/kfGX7PbWeu099702PBbKWLpG/9p06IQRswkdWHCDk0=
    tqXzeIJnTAM9Xf0mdLcpEdklMbfBGPj2oTKmlgrm3S1DTVVHNnh9h8mU1GKllGq/+cYsk6m5WhGdk58=

To decrypt the data:

.. code-block:: bash

    salt-call --local nacl.dec data='tqXzeIJnTAM9Xf0mdLcpEdklMbfBGPj2oTKmlgrm3S1DTVVHNnh9h8mU1GKllGq/+cYsk6m5WhGdk58=' \
        sk='SVWut5SqNpuPeNzb1b9y6b2eXg2PLIog43GBzp48Sow='

When the keys are defined in the master config you can use them from the nacl runner
without extra parameters:

.. code-block:: python

    # cat /etc/salt/master.d/nacl.conf
    nacl.config:
        sk_file: /etc/salt/pki/master/nacl
        pk: 'cTIqXwnUiD1ulg4kXsbeCE7/NoeKEzd4nLeYcCFpd9k='

.. code-block:: bash

    salt-run nacl.enc 'asecretpass'
    salt-run nacl.dec data='tqXzeIJnTAM9Xf0mdLcpEdklMbfBGPj2oTKmlgrm3S1DTVVHNnh9h8mU1GKllGq/+cYsk6m5WhGdk58='

.. code-block:: yaml

    # a salt developers minion could have pillar data that includes a nacl public key
    nacl.config:
        pk: '/kfGX7PbWeu099702PBbKWLpG/9p06IQRswkdWHCDk0='

The developer can then use a less-secure system to encrypt data.

.. code-block:: bash

    salt-call --local nacl.enc apassword


Pillar files can include protected data that the salt master decrypts:

.. code-block:: jinja

    pillarexample:
        user: root
        password1: {{salt.nacl.dec('DRB7Q6/X5gGSRCTpZyxS6hlbWj0llUA+uaVyvou3vJ4=')|json}}
        cert_key: {{salt.nacl.dec_file('/srv/salt/certs/example.com/key.nacl')|json}}
        cert_key2: {{salt.nacl.dec_file('salt:///certs/example.com/key.nacl')|json}}

Larger files like certificates can be encrypted with:

.. code-block:: bash

    salt-call nacl.enc_file /tmp/cert.crt out=/tmp/cert.nacl
    # or more advanced
    cert=$(cat /tmp/cert.crt)
    salt-call --out=newline_values_only nacl.enc_pub data="$cert" > /tmp/cert.nacl

In pillars rended with jinja be sure to include `|json` so line breaks are encoded:

.. code-block:: jinja

    cert: "{{salt.nacl.dec('S2uogToXkgENz9...085KYt')|json}}"

In states rendered with jinja it is also good pratice to include `|json`:

.. code-block:: jinja

    {{sls}} private key:
        file.managed:
            - name: /etc/ssl/private/cert.key
            - mode: 700
            - contents: "{{pillar['pillarexample']['cert_key']|json}}"


Optional small program to encrypt data without needing salt modules.

.. code-block:: python

    #!/bin/python3
    import sys, base64, nacl.public
    pk = base64.b64decode('YOURPUBKEY')
    b = nacl.public.SealedBox(pk)
    data = sys.stdin.buffer.read()
    print(base64.b64encode(b.encrypt(data)).decode())

.. code-block:: bash

    echo 'apassword' | nacl_enc.py

"""

import salt.utils.nacl

__virtualname__ = "nacl"


def __virtual__():
    if __opts__["fips_mode"] is True:
        return False, "nacl module not available in FIPS mode"
    return salt.utils.nacl.check_requirements()


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
    """
    kwargs["opts"] = __opts__
    return salt.utils.nacl.keygen(sk_file, pk_file, **kwargs)


def enc(data, **kwargs):
    """
    Alias to `{box_type}_encrypt`

    box_type: secretbox, sealedbox(default)
    """
    kwargs["opts"] = __opts__
    return salt.utils.nacl.enc(data, **kwargs)


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
    kwargs["opts"] = __opts__
    return salt.utils.nacl.enc_file(name, out, **kwargs)


def dec(data, **kwargs):
    """
    Alias to `{box_type}_decrypt`

    box_type: secretbox, sealedbox(default)
    """
    kwargs["opts"] = __opts__
    return salt.utils.nacl.dec(data, **kwargs)


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
    kwargs["opts"] = __opts__
    return salt.utils.nacl.dec_file(name, out, **kwargs)


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
    kwargs["opts"] = __opts__
    return salt.utils.nacl.sealedbox_encrypt(data, **kwargs)


def sealedbox_decrypt(data, **kwargs):
    """
    Decrypt data using a secret key that was encrypted using a public key with `nacl.sealedbox_encrypt`.

    CLI Examples:

    .. code-block:: bash

        salt-call nacl.sealedbox_decrypt pEXHQM6cuaF7A=
        salt-call --local nacl.sealedbox_decrypt data='pEXHQM6cuaF7A=' sk_file=/etc/salt/pki/master/nacl
        salt-call --local nacl.sealedbox_decrypt data='pEXHQM6cuaF7A=' sk='YmFkcGFzcwo='
    """
    kwargs["opts"] = __opts__
    return salt.utils.nacl.sealedbox_decrypt(data, **kwargs)


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
    kwargs["opts"] = __opts__
    return salt.utils.nacl.secretbox_encrypt(data, **kwargs)


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
    kwargs["opts"] = __opts__
    return salt.utils.nacl.secretbox_decrypt(data, **kwargs)
