'''
Minion side functions for salt-cp
'''
# Import python libs
import os

# Import salt libs
import salt.crypt

def recv(files, dest):
    '''
    Used with salt-cp, pass the files dict, and the destination.

    This function recieves small fast copy files from the master via salt-cp
    '''
    ret = {}
    for path, data in files.items():
        final = ''
        if os.path.basename(path) == os.path.basename(dest)\
                and not os.path.isdir(dest):
            final = dest
        elif os.path.isdir(dest):
            final = os.path.join(dest, os.path.basename(path))
        elif os.path.isdir(os.path.dirname(dest)):
            final = dest
        else:
            return 'Destination unavailable'

        try:
            open(final, 'w+').write(data)
            ret[final] = True
        except IOError:
            ret[final] = False

    return ret

def get_file(path, dest):
    '''
    Used to get a single file from the salt master
    '''
    auth = salt.crypt.SAuth(__opts__)
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(__opts__['master_uri'])
    payload = {'enc': 'aes'}
    if not os.path.isdir(os.path.dirname(dest)):
        return 'Destination unavailable'
    fn_ = open(dest, 'w+')
    load = {'path': path,
            'cmd': '_serve_file'}
    while True:
        load['loc'] = fn_.tell()
        payload['load'] = self.crypticle.dumps(load)
        socket.send_pyobj(payload)
        data = auth.crypticle.loads(socket.recv())
        if not data:
            break
        fn_.write(data)
    return dest

def cache_files(paths):
    '''
    Used to gather many files from the master, the gathered files will be
    saved in the minion cachedir reflective to the paths retrived from the
    master.
    '''
    auth = salt.crypt.SAuth(__opts__)
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(__opts__['master_uri'])
    payload = {'enc': 'aes'}
    ret = []
    for path in paths:
        dest = os.path.join(__opts__['cachedir'], 'files', path)
        dirname = os.path.dirname(dest)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        fn_ = open(dest, 'w+')
        load = {'path': path,
                'cmd': '_serve_file'}
        while True:
            load['loc'] = fn_.tell()
            payload['load'] = self.crypticle.dumps(load)
            socket.send_pyobj(payload)
            data = auth.crypticle.loads(socket.recv())
            if not data:
                break
            fn_.write(data)
        ret.append(path)
    return ret

def cache_file(path):
    '''
    Used to cache a single file in the local salt-master file cache.
    '''
    auth = salt.crypt.SAuth(__opts__)
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(__opts__['master_uri'])
    payload = {'enc': 'aes'}
    dest = os.path.join(__opts__['cachedir'], 'files', path)
    dirname = os.path.dirname(dest)
    if not os.path.isdir(dirname):
        os.makedirs(dirname)
    fn_ = open(dest, 'w+')
    load = {'path': path,
            'cmd': '_serve_file'}
    while True:
        load['loc'] = fn_.tell()
        payload['load'] = self.crypticle.dumps(load)
        socket.send_pyobj(payload)
        data = auth.crypticle.loads(socket.recv())
        if not data:
            break
        fn_.write(data)
    return path

def hash_file(path):
    '''
    Return the hash of a file on the server
    '''
    auth = salt.crypt.SAuth(__opts__)
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(__opts__['master_uri'])
    payload = {'enc': 'aes'}
    payload['load'] = self.crypticle.dumps({'path': path})
    socket.send_pyobj(payload)
    return auth.crypticle.loads(socket.recv())
