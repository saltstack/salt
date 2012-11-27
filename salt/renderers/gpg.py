from __future__ import absolute_import
from StringIO import StringIO

from salt.exceptions import SaltRenderError
import gnupg

import logging
log = logging.getLogger(__name__)

def render(gpg_data, env='', sls='', context=None, **kws):
    '''
    Decrypt gpg_data using gpg. For non-standard GnuPG Home use config
    option `gnupg.home`.

    This renderer needs module pyhton-gnupg.

    Example Usage:

    #!gpg|jinja|yaml
    -----BEGIN PGP MESSAGE-----
    Version: GnuPG v1.4.11 (GNU/Linux)

    hQIMA0M4uNG6doA0ARAAsdp7+5NsPLJZ5p0Orfh0bummP9sEmTZG7jq8m9cAy06Z
    RwEamLxoyc6QLCjgdtSD8bNRt9NY5L5GAuck4JOeUwxo6IZy9DdErThky6WduK/f
    0wiHfeaSLUnyU/bx4q7LAOQC5OVAI+l5
    =rMuf
    -----END PGP MESSAGE-----

    '''

    home=__salt__['config.option']('gnupg.home')
    gpg = gnupg.GPG() if home == None else gnupg.GPG(gnupghome=home)
    res = gpg.decrypt_file(gpg_data)
    if not res.ok:
        err = 'GPG Decryption Error '+res.stderr
        log.critical(err)
        return False

    return StringIO(str(res))
