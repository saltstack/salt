import logging
import os
import glob
import shutil
import salt.utils

log = logging.getLogger(__name__)

def __virtual__():
    # TODO: Check if openssl is installed.
    return 'crt'


def ext_pillar(minion_id, pillar, crtdir=None, cacrtbundle=None, autosign=False, config=None, passfile=None):
    if not crtdir:
        crtdir = '/var/lib/openssl/ca/certs'

    d = crtdir + minion_id

    ret = {'crt': {}}
    if not __salt__['file.directory_exists'](d):
        __salt__['file.mkdir'](d)
        return ret

    if autosign and config:
        csr_dir = os.path.join('/var/cache/salt/master/minions', minion_id, 'files')
        csr = None
        for dirpath, dirnames, files in os.walk(csr_dir, topdown=False):
            for name in files:
                if name.lower().endswith('csr'):
                    csr = os.path.join(dirpath, name)

        if csr:
            crt = os.path.join(d, os.path.splitext(os.path.basename(csr))[0] + '.crt')
            out = __salt__['openssl.sign'](config, csr, crt, passfile)

            if __salt__['file.file_exists'](crt):
                shutil.rmtree(csr_dir)

    cacrt = None
    if cacrtbundle:
        with salt.utils.fopen(cacrtbundle, 'r') as fp_:
            cacrt = fp_.read()

    for f in glob.glob(d + '/*.crt'):
        crt = os.path.splitext(os.path.basename(f))[0]
        with salt.utils.fopen(f, 'r') as fp_:
            ret['crt'][crt] = fp_.read()
        if cacrt:
            ret['crt']['ca_chain'] = {crt: cacrt}

    return ret
