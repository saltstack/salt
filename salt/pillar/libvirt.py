# -*- coding: utf-8 -*-
'''
Load up the libvirt keys into Pillar for a given minion if said keys have been generated using the libvirt key runner
'''
from __future__ import absolute_import

# Don't "fix" the above docstring to put it on two lines, as the sphinx
# autosummary pulls only the first line for its description.

# Import python libs
import os
import subprocess

# Import salt libs
import salt.utils


def ext_pillar(minion_id,
               pillar,  # pylint: disable=W0613
               command):  # pylint: disable=W0613
    '''
    Read in the generated libvirt keys
    '''
    key_dir = os.path.join(
            __opts__['pki_dir'],
            'libvirt',
            minion_id)
    cacert = os.path.join(__opts__['pki_dir'],
            'libvirt',
            'cacert.pem')
    if not os.path.isdir(key_dir):
        # No keys have been generated
        gen_hyper_keys(minion_id)
    ret = {}
    for key in os.listdir(key_dir):
        if not key.endswith('.pem'):
            continue
        fn_ = os.path.join(key_dir, key)
        with salt.utils.fopen(fn_, 'r') as fp_:
            ret['libvirt.{0}'.format(key)] = fp_.read()
    with salt.utils.fopen(cacert, 'r') as fp_:
        ret['libvirt.cacert.pem'] = fp_.read()
    return ret


def gen_hyper_keys(minion_id,
        country='US',
        state='Utah',
        locality='Salt Lake City',
        organization='Salted'):
    '''
    Generate the keys to be used by libvirt hypervisors, this routine gens
    the keys and applies them to the pillar for the hypervisor minions
    '''
    key_dir = os.path.join(
            __opts__['pki_dir'],
            'libvirt')
    if not os.path.isdir(key_dir):
        os.makedirs(key_dir)
    cakey = os.path.join(key_dir, 'cakey.pem')
    cacert = os.path.join(key_dir, 'cacert.pem')
    cainfo = os.path.join(key_dir, 'ca.info')
    if not os.path.isfile(cainfo):
        with salt.utils.fopen(cainfo, 'w+') as fp_:
            fp_.write('cn = salted\nca\ncert_signing_key')
    if not os.path.isfile(cakey):
        subprocess.call(
                'certtool --generate-privkey > {0}'.format(cakey),
                shell=True)
    if not os.path.isfile(cacert):
        cmd = ('certtool --generate-self-signed --load-privkey {0} '
               '--template {1} --outfile {2}').format(cakey, cainfo, cacert)
        subprocess.call(cmd, shell=True)
    sub_dir = os.path.join(key_dir, minion_id)
    if not os.path.isdir(sub_dir):
        os.makedirs(sub_dir)
    priv = os.path.join(sub_dir, 'serverkey.pem')
    cert = os.path.join(sub_dir, 'servercert.pem')
    srvinfo = os.path.join(sub_dir, 'server.info')
    cpriv = os.path.join(sub_dir, 'clientkey.pem')
    ccert = os.path.join(sub_dir, 'clientcert.pem')
    clientinfo = os.path.join(sub_dir, 'client.info')
    if not os.path.isfile(srvinfo):
        with salt.utils.fopen(srvinfo, 'w+') as fp_:
            infodat = ('organization = salted\ncn = {0}\ntls_www_server'
                       '\nencryption_key\nsigning_key'
                       '\ndigitalSignature').format(
                               __grains__['fqdn'])
            fp_.write(infodat)
    if not os.path.isfile(priv):
        subprocess.call(
                'certtool --generate-privkey > {0}'.format(priv),
                shell=True)
    if not os.path.isfile(cert):
        cmd = ('certtool --generate-certificate --load-privkey {0} '
               '--load-ca-certificate {1} --load-ca-privkey {2} '
               '--template {3} --outfile {4}'
               ).format(priv, cacert, cakey, srvinfo, cert)
        subprocess.call(cmd, shell=True)
    if not os.path.isfile(clientinfo):
        with salt.utils.fopen(clientinfo, 'w+') as fp_:
            infodat = ('country = {0}\nstate = {1}\nlocality = '
                       '{2}\norganization = {3}\ncn = {4}\n'
                       'tls_www_client\nencryption_key\nsigning_key\n'
                       'digitalSignature'
                       ).format(
                               country,
                               state,
                               locality,
                               organization,
                               __grains__['fqdn'])
            fp_.write(infodat)
    if not os.path.isfile(cpriv):
        subprocess.call(
                'certtool --generate-privkey > {0}'.format(cpriv),
                shell=True)
    if not os.path.isfile(ccert):
        cmd = ('certtool --generate-certificate --load-privkey {0} '
               '--load-ca-certificate {1} --load-ca-privkey {2} '
               '--template {3} --outfile {4}'
               ).format(cpriv, cacert, cakey, clientinfo, ccert)
        subprocess.call(cmd, shell=True)
