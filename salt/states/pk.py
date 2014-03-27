'''
State for making sure a private key is generated and optionally signed
by a CA specified.
'''

import logging
import os.path
import salt.utils
import time

log = logging.getLogger(__name__)

def __virtual__():
    '''
    Only work on POSIX-like systems
    '''
    if salt.utils.is_windows():
        return False
    return 'pk'

def generated(name, pk_dir, length=4096, algorithm='RSA', **kwargs):
    '''
    Ensures that a private key is generated.
    '''
    ret = {
            'name': name,
            'result': False,
            'comment': '',
            'changes': {}
    }
    pk = os.path.join(pk_dir, name + '.key')

    # TODO: Failure conditions on key size, etc.
    if __salt__['file.file_exists'](pk):
        ret['result'] = True
        ret['comment'] = 'Key {0} is already generated.'.format(pk)
        return ret

    ret['comment'] = 'Generating private key at: %s'.format(pk)
    out = __salt__['openssl.generate'](pk, length=length, algorithm=algorithm, **kwargs)
    if not out:
        ret['comment'] = 'SOMETHING FAILED HORRIBLY!'
        return ret

    ret['changes']['pk'] = {'old': '', 'new': out}
    ret['result'] = True
    return ret


def signed(name, bundle_ca = True, base_dir=None, length=4096, algorithm='RSA', gen_pem=True, **kwargs):
    '''
    Ensures that the certificate is signed by a CA.
    It does however not actually sign the certificate,
    that is a manual step on the CA itself because you
    probably want the CA root certificate encrypted.

    If you don't supply a CN, it will be the same as
    the file name without .pem.
    You can pass in country, city and company for
    inclusion in the certificate in the PK as well.
    '''
    pk_dir = kwargs.pop('pk_dir', base_dir)
    base_dir = base_dir if base_dir else pk_dir
    crt_dir = kwargs.pop('crt_dir', base_dir)
    cacrt_dir = kwargs.pop('cacrt_dir', base_dir)

    if not pk_dir or not crt_dir:
        return {'result': False,
                'comment': 'You need to specify either base_dir or pk_dir AND crt_dir'
                }
    # create file paths
    crt = os.path.join(crt_dir, name + '.crt')
    pk = os.path.join(pk_dir, name + '.key')
    csr = os.path.join(pk_dir, name + '.csr')
    pem = os.path.join(base_dir, name + '.pem')
    cacrt = os.path.join(cacrt_dir, name + '-chain.crt')

    # Check if PK is generated
    ret = generated(name, pk_dir, length=length, algorithm=algorithm, **kwargs)
    if not ret['result']:
        return ret

    crt_file = pem if gen_pem else crt
    if __salt__['file.file_exists'](crt_file):
        # TODO: Verify certificate authenticity
        ret['comment'] = 'Key {0} is already signed.'
        return ret

    # Check if CSR exists
    if not __salt__['file.file_exists'](csr):
        out = __salt__['openssl.gen_req'](pk, csr, name, **kwargs)
        ret['changes']['csr'] = {'old': '', 'new': out}
    # Copy CSR to Master
    out = __salt__['cp.push'](csr)
    if out:
        ret['changes']['csr_push'] = {'old': '', 'new': 'Pushed!'}

    # We'll give the master 5 seconds to generate the certificate.
    # There might be a large problem with the fact that pillars might be read
    # in at script start and not when it is requested, but we will see.
    time.sleep(5)

    # Check if CRT exists
    if 'crt' in __pillar__ and name in __pillar__['crt']:
        ca_chain = __pillar__['crt']['ca_chain'][name]
        if not __salt__['file.file_exists'](cacrt) and not bundle_ca:
            with salt.utils.fopen(cacrt, 'w') as fp_:
                fp_.write(ca_chain)

        if not __salt__['file.file_exists'](crt):
            crt_data = __pillar__['crt'][name]
            if bundle_ca: crt_data += "\n" + ca_chain
            with salt.utils.fopen(crt, 'w') as fp_:
                fp_.write(crt_data)

            ret['changes']['crt'] = {'old': '', 'new': 'CRT Received'}
        # Merge PK + CRT
        if gen_pem:
            __salt__['openssl.gen_pem'](name, pk, crt)

        ret['result'] = True
    else:
        ret['comment'] = 'Did not receive CRT from pillar. It probably is not accepted by master yet.'
        ret['result'] = False

    return ret
