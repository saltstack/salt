# -*- coding: utf-8 -*-
'''
Two classes for traversing a directory-tree and collecting files and their data
filtered by filename.

The StatWalker is instantiated by an FSWorker, iterates a given directory
and yields all files found in it. No symlinks, sockets, etc are returned, only
regular files.

The FSWorker iterates over the results and filters them by filename. If
a match is found, the file is opened and filename and data are saved in a dict.
Once the directory is successfully traversed, all collected data is returned.
'''
# Import python libs
import multiprocessing
import os
import stat
from re import match as rematch
import time
import sys

# Import salt libs
import salt.utils
import salt.payload

# Import third party libs
try:
    import zmq
except ImportError:
    pass

# try importing psutil to set ionice-ness
try:
    import psutil
except ImportError:
    pass


class Statwalker(object):
    '''
    Iterator class that walks through a directory and
    collects the stat()-data for every file it finds
    '''

    def __init__(self, directory):
        self.stack = [directory]
        self.files = []
        self.index = 0

    def __getitem__(self, index):
        '''
        make it iterable
        '''
        while 1:
            try:
                fn = self.files[self.index]
                self.index = self.index + 1
            except IndexError:
                # pop next directory from stack
                self.directory = self.stack.pop()
                try:
                    self.files = os.listdir(self.directory)
                    self.index = 0
                except OSError as _:
                    print "Folder not found... {0}".format(self.directory)
            else:
                fullname = os.path.join(self.directory, fn)
                st = os.stat(fullname)
                mode = st[stat.ST_MODE]
                # if a dir is found, stash it for iteration
                if stat.S_ISDIR(mode) and not stat.S_ISLNK(mode):
                    self.stack.append(fullname)
                # we only want files to be returned, no smylinks, sockets, etc.
                if stat.S_ISREG(mode):
                    return fullname, st


class FSWorker(multiprocessing.Process):
    '''
    Instantiates a StatWalker to walk a directory and filters the returned files
    by name. On a match the files path and data is saved in a dict which is
    returned to the caller once traversing the directory is finished.
    '''

    def __init__(self, opts, name, **kwargs):
        super(FSWorker, self).__init__()
        self.name = name
        self.path = kwargs.get('path', None)
        self.pattern = kwargs.get('patt', None)
        self.opts = opts
        self.serial = salt.payload.Serial(self.opts.get('serial', ''))
        self.set_nice()

    def set_nice(self):
        '''
        Set the ionice-ness very low to harm the disk as little as possible.
        Not all systems might have a recent enough psutils-package, but we
        try anyway.
        '''
        try:
            self.proc = psutil.Process(os.getpid())
            self.proc.set_ionice(psutil.IOPRIO_CLASS_IDLE)
        except NameError:
            pass

    def verify(self):
        '''
        Runs a few tests before executing the worker
        '''
        if os.path.isdir(self.path):
            return True

    def run(self):
        '''
        Main loop that searches directories and retrieves the data
        '''
        # the socket for outgoing cache-update-requests to FSCache
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 100)
        socket.connect("ipc:///tmp/fsc_upd")
        time.sleep(1)

        data = {}

        # create shortcut to prevent manymany dot-lookups in the loop
        dir_n = os.path.dirname

        if self.verify():
            print "WORKER({0}):  {1} running in dir {2}".format(self.pid,
                                                                self.name,
                                                                self.path)
            for fn, _ in Statwalker(self.path):
                # add a few more checks data:
                # - dont open empty files
                # - what to add to the dict for empty files?
                if rematch(self.pattern, fn):
                    data[fn] = {}
                    #data[fn] = 'test'
                    data[fn] = salt.utils.fopen(fn, 'rb').read()
            # send the data back to the caller
            socket.send(self.serial.dumps(data))
            ack = self.serial.loads(socket.recv())
            if ack == 'OK':
                print "WORKER:  {0} finished".format(self.name)
        else:
            # directory does not exist, return empty result dict
            socket.send(self.serial.dumps({self.path: None}))

# test code for the FSWalker class
if __name__ == '__main__':
    def run_test():
        context = zmq.Context()
        cupd_in = context.socket(zmq.REP)
        cupd_in.setsockopt(zmq.LINGER, 100)
        cupd_in.bind("ipc:///tmp/fsc_upd")

        poller = zmq.Poller()
        poller.register(cupd_in, zmq.POLLIN)
        serial = salt.payload.Serial('msgpack')
        fsw = FSWorker({'serial': 'msgpack'},
                        'test',
                        **{'path': '/tmp', 'patt': '.*'})
        fsw.start()

        while 1:
            socks = dict(poller.poll())
            if socks.get(cupd_in) == zmq.POLLIN:
                reply = serial.loads(cupd_in.recv())
                print reply
                cupd_in.send(serial.dumps('OK'))
            break
        fsw.join()
        sys.exit(0)

    run_test()
