'''
Many aspects of the salt payload need to be managed, from the return of
encrypted keys to general payload dynamics and packaging, these happen in here
'''

import cPickle as pickle

import msgpack


def package(payload):
    '''
    This method for now just wraps msgpack.dumps, but it is here so that we can
    make the serialization a custom option in the future with ease.
    '''
    return msgpack.dumps(payload)


def unpackage(package_):
    '''
    Unpackages a payload
    '''
    return msgpack.loads(package_)


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

class Serial(object):
    '''
    Create a serialization object, this object manages all message
    serialization in Salt
    '''
    def __init__(self, opts):
        self.opts = opts
        self.serial = self.opts.get('serial', 'msgpack')

    def loads(self, msg):
        '''
        Run the correct loads serialization format
        '''
        if self.serial == 'msgpack':
            return msgpack.loads(msg)
        elif self.serial == 'pickle':
            try:
                return pickle.loads(msg)
            except:
                return msgpack.loads(msg)

    def load(self, fn_):
        '''
        Run the correct serialization to load a file
        '''
        data = fn_.read()
        return self.loads(data)

    def dumps(self, msg):
        '''
        Run the correct dumps serialization format
        '''
        if self.serial == 'pickle':
            return pickle.dumps(msg)
        else:
            return msgpack.dumps(msg)

    def dump(self, msg, fn_):
        '''
        Serialize the correct data into the named file object
        '''
        fn_.write(self.dumps(msg))
