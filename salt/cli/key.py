'''
The actual saltkey functional code
'''

import os
import sys
import shutil

class Key(object):
    '''
    The object that encapsulates saltkey actions
    '''
    def __init__(self, opts):
        self.opts = opts

    def _list_pre(self):
        '''
        List the unaccepted keys
        '''
        pre_dir = os.path.join(self.opts['pki_dir'], 'minions_pre')
        if not os.path.isdir(pre_dir):
            err = 'The minions_pre directory is not present, ensure that the'\
                + ' master server has been started'
            sys.stderr.write(err + '\n')
            sys.exit(42)
        print 'Unaccepted Keys:'
        for fn_ in os.listdir(pre_dir):
            print fn_

    def _list_accepted(self):
        '''
        List the accepted public keys
        '''
        minions = os.path.join(self.opts['pki_dir'], 'minions')
        if not os.path.isdir(minions):
            err = 'The minions directory is not present, ensure that the'\
                + ' master server has been started'
            sys.stderr.write(err + '\n')
            sys.exit(42)
        print 'Accepted Keys:'
        for fn_ in os.listdir(minions):
            print fn_

    def _list_all(self):
        '''
        List all keys
        '''
        self._list_pre()
        self._list_accepted()

    def _accept(self, key):
        pre_dir = os.path.join(self.opts['pki_dir'], 'minions_pre')
        minions = os.path.join(self.opts['pki_dir'], 'minions')
        if not os.path.isdir(minions):
            err = 'The minions directory is not present, ensure that the'\
                + ' master server has been started'
            sys.stderr.write(err + '\n')
            sys.exit(42)
        if not os.path.isdir(pre_dir):
            err = 'The minions_pre directory is not present, ensure that the'\
                + ' master server has been started'
            sys.stderr.write(err + '\n')
            sys.exit(42)
        pre = os.listdir(pre_dir)
        if not pre.count(key):
            err = 'The named host is unavailable, please accept an available'\
                + ' key'
            sys.stderr.write(err + '\n')
            sys.exit(43)
        shutil.move(os.path.join(pre_dir, key), os.path.join(minions, key))

    def _accept_all(self):
        '''
        Accept all keys in pre
        '''
        pre_dir = os.path.join(self.opts['pki_dir'], 'minions_pre')
        minions = os.path.join(self.opts['pki_dir'], 'minions')
        if not os.path.isdir(minions):
            err = 'The minions directory is not present, ensure that the'\
                + ' master server has been started'
            sys.stderr.write(err + '\n')
            sys.exit(42)
        if not os.path.isdir(pre_dir):
            err = 'The minions_pre directory is not present, ensure that the'\
                + ' master server has been started'
            sys.stderr.write(err + '\n')
            sys.exit(42)
        for key in os.listdir(pre_dir):
            self._accept(key)

    def run(self):
        '''
        Run the logic for saltkey
        '''
        if self.opts['list']:
            self._list_pre()
        elif self.opts['list_all']:
            self._list_all()
        elif self.opts['accept']:
            self._accept(self.opts['accept'])
        elif self.opts['accept_all']:
            self._accept_all()
        else:
            self._list_all()


