'''
Many aspects of the salt payload need to be managed, from the return of
encrypted keys to general payload dynamics and packaging, these happen in here
'''
import os
import cPickle as pickle
import json

def package(payload, form='pickle', protocol=2):
    '''
    Package up the salt communication payload, pass in the payload and the
    optional form paramater. Form can be either pickle for greater speed,
    flexibility and compression, of json, for more compatability. The default
    is pickle
    '''
    package = ''
    if form == 'json':
        package = json.dumps(payload)
    else:
        package = pickle.dumps(payload, protocol)
    return package

def aes(payload, key):
    '''
    Encrypt the payload with AES encryption.
    '''
    pass

def rsa_pub(payload, key):
    '''
    Encrypt the payload with an rsa public key
    '''
    pass

def rsa_priv(payload, key):
    '''
    Encrypt the payload with an rsa private key
    '''
    pass
