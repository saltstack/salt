'''
Many aspects of the salt payload need to be managed, from the return of
encrypted keys to general payload dynamics and packaging, these happen in here
'''
import cPickle as pickle

def package(payload, protocol=2):
    '''
    This method for now just wraps pickle.dumps, but it is here so that we can
    make the serialization a custom option in the future with ease.
    '''
    return pickle.dumps(payload, protocol)

def unpackage(package_):
    '''
    Unpackages a payload
    '''
    return pickle.loads(package_)

def format_payload(enc, **kwargs):
    '''
    Pass in the required arguments for a payload, the enc type and the cmd,
    then a list of keyword args to generate the body of the load dict.
    '''
    payload = {'enc': enc}
    load = {}
    for key in kwargs:
        load[key] = kwargs[key]
    payload['load'] = load
    return package(payload)

