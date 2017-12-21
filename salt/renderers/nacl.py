# -*- coding: utf-8 -*-
r'''
Renderer that will decrypt NACL ciphers

Any key in the SLS file can be an NACL cipher, and this renderer will decrypt it
before passing it off to Salt. This allows you to safely store secrets in
source control, in such a way that only your Salt master can decrypt them and
distribute them only to the minions that need them.

The typical use-case would be to use ciphers in your pillar data, and keep a
secret key on your master. You can put the public key in source control so that
developers can add new secrets quickly and easily.

This renderer requires the libsodium library binary and libnacl >= 1.5.1
python package (support for sealed boxes came in 1.5.1 version).


Setup
-----

To set things up, first generate a keypair. On the master, run the following:

.. code-block:: bash

    # salt-call --local nacl.keygen sk_file=/root/.nacl


Using encrypted pillar
---------------------

To encrypt secrets, copy the public key to your local machine and run:

.. code-block:: bash

    $ salt-call --local nacl.enc datatoenc pk_file=/root/.nacl.pub


To apply the renderer on a file-by-file basis add the following line to the
top of any pillar with nacl encrypted data in it:

.. code-block:: yaml

    #!yaml|nacl

Now with your renderer configured, you can include your ciphers in your pillar
data like so:

.. code-block:: yaml

    #!yaml|nacl

    a-secret: "NACL[MRN3cc+fmdxyQbz6WMF+jq1hKdU5X5BBI7OjK+atvHo1ll+w1gZ7XyWtZVfq9gK9rQaMfkDxmidJKwE0Mw==]"
'''


from __future__ import absolute_import, print_function, unicode_literals
import re
import logging

# Import salt libs
import salt.utils.stringio
import salt.syspaths

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)
NACL_REGEX = r'^NACL\[(.*)\]$'


def _decrypt_object(obj, **kwargs):
    '''
    Recursively try to decrypt any object. If the object is a six.string_types
    (string or unicode), and it contains a valid NACLENC pretext, decrypt it,
    otherwise keep going until a string is found.
    '''
    if salt.utils.stringio.is_readable(obj):
        return _decrypt_object(obj.getvalue(), **kwargs)
    if isinstance(obj, six.string_types):
        if re.search(NACL_REGEX, obj) is not None:
            return __salt__['nacl.dec'](re.search(NACL_REGEX, obj).group(1), **kwargs)
        else:
            return obj
    elif isinstance(obj, dict):
        for key, value in six.iteritems(obj):
            obj[key] = _decrypt_object(value, **kwargs)
        return obj
    elif isinstance(obj, list):
        for key, value in enumerate(obj):
            obj[key] = _decrypt_object(value, **kwargs)
        return obj
    else:
        return obj


def render(nacl_data, saltenv='base', sls='', argline='', **kwargs):
    '''
    Decrypt the data to be rendered using the given nacl key or the one given
    in config
    '''
    return _decrypt_object(nacl_data, **kwargs)
