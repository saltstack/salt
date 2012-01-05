'''
The actual saltkey functional code
'''

# Import python modules
import os
import shutil
import sys

# Import salt modules
import salt.crypt
import salt.utils as utils


class Key(object):
    '''
    The object that encapsulates saltkey actions
    '''
    def __init__(self, opts):
        self.opts = opts

    def _keys(self, key_type, full_path=False):
        '''
        Safely return the names of the unaccepted keys, pass True to return
        the full key paths. Returns a set.
        '''
        ret = set()
        subdir = ''
        if key_type == 'pre':
            subdir = 'minions_pre'
        elif key_type == 'acc':
            subdir = 'minions'
        dir_ = os.path.join(self.opts['pki_dir'], subdir)
        if not os.path.isdir(dir_):
            err = ('The ' + subdir + ' directory is not present, ensure that '
                   'the master server has been started')
            sys.stderr.write(err + '\n')
            sys.exit(42)
        keys = os.listdir(dir_)
        if full_path:
            for key in keys:
                ret.add(os.path.join(dir_, key))
        else:
            ret = set(keys)
        return ret

    def _list_pre(self):
        '''
        List the unaccepted keys
        '''
        print utils.LIGHT_RED + 'Unaccepted Keys:' + utils.ENDC
        for key in sorted(self._keys('pre')):
            print utils.RED + key + utils.ENDC

    def _list_accepted(self):
        '''
        List the accepted public keys
        '''
        print utils.LIGHT_GREEN + 'Accepted Keys:' + utils.ENDC
        for key in sorted(self._keys('acc')):
            print utils.GREEN + key + utils.ENDC

    def _list_all(self):
        '''
        List all keys
        '''
        self._list_pre()
        self._list_accepted()

    def _print_key(self, name):
        '''
        Print out the specified public key
        '''
        keys = self._keys('pre', True).union(self._keys('acc', True))
        for key in sorted(keys):
            if key.endswith(name):
                print open(key, 'r').read()

    def _print_all(self):
        '''
        Print out the public keys, all of em'
        '''
        print utils.LIGHT_RED + 'Unaccepted keys:' + utils.ENDC
        for key in sorted(self._keys('pre', True)):
            print '  ' + utils.RED + os.path.basename(key) + utils.ENDC
            print open(key, 'r').read()
        print utils.LIGHT_GREEN + 'Accepted keys:' + utils.ENDC
        for key in sorted(self._keys('acc', True)):
            print '  ' + utils.GREEN + os.path.basename(key) + utils.ENDC
            print open(key, 'r').read()

    def _accept(self, key):
        '''
        Accept a specified host's public key
        '''
        pre_dir = os.path.join(self.opts['pki_dir'], 'minions_pre')
        minions = os.path.join(self.opts['pki_dir'], 'minions')
        if not os.path.isdir(minions):
            err = ('The minions directory is not present, ensure that the '
                   'master server has been started')
            sys.stderr.write(err + '\n')
            sys.exit(42)
        if not os.path.isdir(pre_dir):
            err = ('The minions_pre directory is not present, ensure '
                   'that the master server has been started')
            sys.stderr.write(err + '\n')
            sys.exit(42)
        pre = os.listdir(pre_dir)
        if not pre.count(key):
            err = ('The named host is unavailable, please accept an '
                   'available key')
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
            err = ('The minions directory is not present, ensure that the '
                   'master server has been started')
            sys.stderr.write(err + '\n')
            sys.exit(42)
        if not os.path.isdir(pre_dir):
            err = ('The minions_pre directory is not present, ensure that the '
                   'master server has been started')
            sys.stderr.write(err + '\n')
            sys.exit(42)
        for key in os.listdir(pre_dir):
            self._accept(key)

    def _delete_key(self):
        '''
        Delete a key
        '''
        pre_dir = os.path.join(self.opts['pki_dir'], 'minions_pre')
        minions = os.path.join(self.opts['pki_dir'], 'minions')
        if not os.path.isdir(minions):
            err = ('The minions directory is not present, ensure that the '
                   'master server has been started')
            sys.stderr.write(err + '\n')
            sys.exit(42)
        if not os.path.isdir(pre_dir):
            err = ('The minions_pre directory is not present, ensure that the '
                   'master server has been started')
            sys.stderr.write(err + '\n')
            sys.exit(42)
        pre = os.path.join(pre_dir, self.opts['delete'])
        acc = os.path.join(minions, self.opts['delete'])
        if os.path.exists(pre):
            os.remove(pre)
            print 'Removed pending key %s' % self.opts['delete']
        if os.path.exists(acc):
            os.remove(acc)
            print 'Removed accepted key %s' % self.opts['delete']

    def run(self):
        '''
        Run the logic for saltkey
        '''
        if self.opts['gen_keys']:
            salt.crypt.gen_keys(
                    self.opts['gen_keys_dir'],
                    self.opts['gen_keys'],
                    self.opts['keysize'])
            return
        if self.opts['list']:
            self._list_pre()
        elif self.opts['list_all']:
            self._list_all()
        elif self.opts['print']:
            self._print_key(self.opts['print'])
        elif self.opts['print_all']:
            self._print_all()
        elif self.opts['accept']:
            self._accept(self.opts['accept'])
        elif self.opts['accept_all']:
            self._accept_all()
        elif self.opts['delete']:
            self._delete_key()
        else:
            self._list_all()
