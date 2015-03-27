# -*- coding: utf-8 -*-
'''
Module for requesting a CA to sign an x509 certificate.
'''

from __future__ import absolute_import
# Import Python libs
import logging
import salt.client

log = logging.getLogger(__name__)

def request_and_sign(path, ca_server, requestor, signing_policy, signing_policy_def,
        properties, grains=None, pillar=None):
    '''
    Request a certificate to be signed by a particular CA. Ideal for calling from a reactor
    triggered by the x509.request_certificate module.

    An example reactor that can use this runner:

    .. code-block::yaml

        sign_request:
          runner.x509.request_and_sign:
            - requestor: {{ data['id'] }}
            - path: {{ data['data']['path'] }}
            - ca_server: {{ data['data']['ca_server'] }}
            - signing_policy: {{ data['data']['signing_policy'] }}
            - signing_policy_def: /etc/pki/signing_policy.yml
            - properties: {{ data['data']['properties'] }}
            - grains: {{ data['data']['grains'] }}
            - pillar: {{ data['data']['pillar'] }}
    '''
    if grains is None:
        grains = {}
    if pillar is None:
        pillar = {}

    client = salt.client.LocalClient(__opts__['conf_file'])

    # Validate input, we only want a single minion here
    ca_server = ca_server.replace('*', '').replace('?', '')
    requestor = requestor.replace('*', '').replace('?', '')

    print 'text="'+str(True)+'" requestor="'+str(requestor)+'" signing_policy="'+str(signing_policy)+'" signing_policy_def="'+str(signing_policy_def)+'" properties="'+str(properties)+'" grains="'+str(grains)+'" pillar="'+str(pillar)+'"'

    print client.cmd(ca_server, 'x509.sign_request', kwarg={
            'text': True, 'requestor': requestor, 'signing_policy': signing_policy,
            'signing_policy_def': signing_policy_def, 'properties': properties,
            'grains': grains, 'pillar': pillar})

    signed_cert = client.cmd(ca_server, 'x509.sign_request', kwarg={
            'text': True, 'requestor': requestor, 'signing_policy': signing_policy,
            'signing_policy_def': signing_policy_def, 'properties': properties,
            'grains': grains, 'pillar': pillar})[ca_server]

    log.info('Signed cert has been generated:')

    ret = client.cmd(requestor, 'x509.write_pem', kwarg={'path': path,
            'text': signed_cert, 'pem_type': 'CERTIFICATE'})

    log.info('Signed cert has been written to ' + path)

    return ret
