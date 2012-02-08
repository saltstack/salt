'''
The actual saltkey functional code
'''

# Import python modules
import os
import shutil
import sys
import logging
# Import salt modules
import salt.crypt
import salt.utils as utils

log = logging.getLogger(__name__)

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
        elif key_type == 'rej':
            subdir = 'minions_rejected'
        elif key_type == 'acc':
            subdir = 'minions'
        dir_ = os.path.join(self.opts['pki_dir'], subdir)
        if not os.path.isdir(dir_):
            err = ('The ' + subdir + ' directory is not present, ensure that '
                   'the master server has been started')
            self._log(err, level='error')
            sys.exit(42)
        keys = os.listdir(dir_)
        if full_path:
            for key in keys:
                ret.add(os.path.join(dir_, key))
        else:
            ret = set(keys)
        return ret
    
    def _log(self, message, level=''):
        if hasattr(log, level):
            log_msg = getattr(log, level)
            log_msg(message)
        if not self.opts['quiet']:
            print message

    def _list_pre(self):
        '''
        List the unaccepted keys
        '''
        self._log(utils.LIGHT_RED + 'Unaccepted Keys:' + utils.ENDC)
        for key in sorted(self._keys('pre')):
            output = utils.RED + key + utils.ENDC
            self._log(output)

    def _list_accepted(self):
        '''
        List the accepted public keys
        '''
        self._log(utils.LIGHT_GREEN + 'Accepted Keys:' + utils.ENDC)
        for key in sorted(self._keys('acc')):
            self._log(utils.GREEN + key + utils.ENDC)

    def _list_rejected(self):
        '''
        List the unaccepted keys
        '''
        self._log(utils.LIGHT_BLUE + 'Rejected:' + utils.ENDC)
        for key in sorted(self._keys('rej')):
            self._log(utils.BLUE + key + utils.ENDC)

    def _list_all(self):
        '''
        List all keys
        '''
        self._list_pre()
        self._list_accepted()
        self._list_rejected()

    def _print_key(self, name):
        '''
        Print out the specified public key
        '''
        keys = self._keys('pre', True).union(self._keys('acc', True))
        for key in sorted(keys):
            if key.endswith(name):
                self._log(open(key, 'r').read())

    def _print_all(self):
        '''
        Print out the public keys, all of em'
        '''
        self._log(utils.LIGHT_RED + 'Unaccepted keys:' + utils.ENDC)
        for key in sorted(self._keys('pre', True)):
            self._log('  ' + utils.RED + os.path.basename(key) + utils.ENDC)
            self._log(open(key, 'r').read())
        self._log(utils.LIGHT_GREEN + 'Accepted keys:' + utils.ENDC)
        for key in sorted(self._keys('acc', True)):
            self._log('  ' + utils.GREEN + os.path.basename(key) + 
                         utils.ENDC)
            self._log(open(key, 'r').read())
        self._log(utils.LIGHT_BLUE + 'Rejected keys:' + utils.ENDC)
        for key in sorted(self._keys('pre', True)):
            self._log('  ' + utils.BLUE + os.path.basename(key) + 
                         utils.ENDC)
            self._log(open(key, 'r').read())

    def _accept(self, key):
        '''
        Accept a specified host's public key
        '''
        (minions_accepted,
         minions_pre,
         minions_rejected) = self._check_minions_directories()
        pre = os.listdir(minions_pre)
        if not pre.count(key):
            err = ('The key named %s does not exist, please accept an '
                   'available key' %(key))
            #log.error(err)
            self._log(err, level='error')
            sys.exit(43)
        shutil.move(os.path.join(minions_pre, key),
                    os.path.join(minions_accepted, key))
        self._log('Key for %s accepted.' %(key), level='info')

    def _accept_all(self):
        '''
        Accept all keys in pre
        '''
        (minions_accepted,
         minions_pre,
         minions_rejected) = self._check_minions_directories()
        for key in os.listdir(minions_pre):
            self._accept(key)

    def _delete_key(self):
        '''
        Delete a key
        '''
        (minions_accepted,
         minions_pre,
         minions_rejected) = self._check_minions_directories()
        pre = os.path.join(minions_pre, self.opts['delete'])
        acc = os.path.join(minions_accepted, self.opts['delete'])
        rej= os.path.join(minions_rejected, self.opts['delete'])
        if os.path.exists(pre):
            os.remove(pre)
            self._log('Removed pending key %s' % self.opts['delete'], 
                         level='info')
        if os.path.exists(acc):
            os.remove(acc)
            self._log('Removed accepted key %s' % self.opts['delete'], 
                         level='info')
        if os.path.exists(rej):
            os.remove(rej)
            self._log('Removed rejected key %s' % self.opts['delete'], 
                         level='info')

    def _reject(self, key):
        '''
        Reject a specified host's public key
        '''
        (minions_accepted,
         minions_pre,
         minions_rejected) = self._check_minions_directories()
        pre = os.listdir(minions_pre)
        if not pre.count(key):
            err = ('The host named %s is unavailable, please accept an '
                   'available key' %(key))
            self._log(err, level='error')
            sys.exit(43)
        shutil.move(os.path.join(minions_pre, key),
                    os.path.join(minions_rejected, key))
        self._log('%s key rejected.' %(key), level='info')

    def _reject_all(self):
        '''
        Reject all keys in pre
        '''
        (minions_accepted,
         minions_pre,
         minions_rejected) = self._check_minions_directories()
        for key in os.listdir(minions_pre):
            self._reject(key)

    def _check_minions_directories(self):
        minions_accepted = os.path.join(self.opts['pki_dir'], 'minions')
        minions_pre = os.path.join(self.opts['pki_dir'], 'minions_pre')
        minions_rejected = os.path.join(self.opts['pki_dir'], 
                                        'minions_rejected')
        for dir in [minions_accepted, minions_pre, minions_rejected]:
            if not os.path.isdir(dir):
                err = ('The minions directory {0} is not present, ensure '
                       'that the master server has been started'.format(dir))
                self._log(err, level='error')
                sys.exit(42)
        return minions_accepted, minions_pre, minions_rejected

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
        elif self.opts['reject']:
            self._reject(self.opts['reject'])
        elif self.opts['reject_all']:
            self._reject_all()
        elif self.opts['delete']:
            self._delete_key()
        else:
            self._list_all()