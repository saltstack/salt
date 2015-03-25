# -*- coding: utf-8 -*-
'''
Module for requesting a CA to sign an x509 certificate.
'''

from __future__ import absolute_import
# Import Python libs
import logging
import salt.client

def request_certificate(data, output=True, display_progress=False):
    # Validate input, we only want a single minion here
    ca_server = data['data']['ca_server']
    ca_server = ca_server.replace('*', '').replace('?', '')

    requestor = data['data']['requestor']
    requestor = requestor.replace('*', '').replace('?', '')

    signing_policy = data['signing_policy']
    signing_policy_def = data['data']['signing_policy_def']
    public_key = data['data']['public_key']
    csr = data['data']['csr']
    path = data['data']['path']

    grains = data['grains']
    pillar = data['pillar']

    signed_cert = client.cmd(ca_server, 'x509.sign_request',
            text=True, requestor=requestor, signing_policy=signing_policy,
            signing_policy_def=signing_policy_def, public_key=public_key,
            csr=csr, grains=grains, pillar=pillar)

    ret = client.cmd(requestor, 'x509.write_pem', path=path,
            text=signed_cert, pem_type='CERTIFICATE')
