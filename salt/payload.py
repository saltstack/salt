'''
Many aspects of the salt payload need to be managed, from the return of
encrypted keys to general payload dynamics and packaging, these happen in here
'''
import os
import cPickle as pickle

def package(payload, form='pickle', protocol=2):
    '''
    Package up the salt communication payload, pass in the payload and the
    optional form paramater. Form can be either pickle for greater speed,
    flexibility and compression, of json, for more compatability. The default
    is pickle
    '''
    return pickle.dumps(payload, protocol)

def unpackage(package):
    '''
    Unpackages a payload
    '''
    return pickle.loads(package)

def format_payload(enc, cmd, **kwargs):
    '''
    Pass in the required arguments for a payload, the enc type and the cmd,
    then a list of keyword args to generate the body of the load dict.
    '''
    payload = {'enc': enc}
    load = {'cmd': cmd}
    for key in kwargs:
        load[key: kwargs[key]]
    payload['load'] = load
    return payload

