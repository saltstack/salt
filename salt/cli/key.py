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
import salt.utils
import salt.utils.event

log = logging.getLogger(__name__)


class Key(object):
    '''
    The object that encapsulates saltkey actions
    '''
    def __init__(self, opts):
        self.opts = opts
        self.event = salt.utils.event.SaltEvent(opts['sock_dir'], 'master')
        self.colors = salt.utils.get_colors(
                not bool(self.opts.get('no_color', False))
                )

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
            err = ('The {0} directory is not present, ensure that '
                   'the master server has been started').format(subdir)
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
            print(message)

    def _list_pre(self, header=True, printer=None):
        '''
        List the unaccepted keys
        '''
        if header == True:
            self._log('{0}Unaccepted Keys:{1}'.format(
                self.colors['LIGHT_RED'], self.colors['ENDC']
                ))
        keys = self._keys('pre')
        if printer is None:
            for key in sorted(keys):
                output = '{0}{1}{2}'.format(
                        self.colors['RED'],
                        key,
                        self.colors['ENDC']
                        )
                self._log(output)
        else:
            printer(list(keys))

    def _list_accepted(self, header=True, printer=None):
        '''
        List the accepted public keys
        '''
        if header == True:
            self._log('{0}Accepted Keys:{1}'.format(
                self.colors['LIGHT_GREEN'], self.colors['ENDC']
                ))
        keys = self._keys('acc')
        if printer is None:
            for key in sorted(keys):
                self._log('{0}{1}{2}'.format(
                    self.colors['GREEN'], key, self.colors['ENDC']
                    ))
        else:
            printer(list(keys))

    def _list_rejected(self, header=True, printer=None):
        '''
        List the unaccepted keys
        '''
        if header == True:
            self._log('{0}Rejected:{1}'.format(
                self.colors['LIGHT_BLUE'], self.colors['ENDC']
                ))
        keys = self._keys('rej')
        if printer is None:
            for key in sorted(keys):
                self._log('{0}{1}{2}'.format(
                    self.colors['BLUE'], key, self.colors['ENDC']
                    ))
        else:
            printer(list(keys))

    def _list(self, name):
        '''
        List keys
        '''
        printout = self._get_outputter()
        if 'json_out' in self.opts and self.opts['json_out']:
            printout.indent = 2
        if name in ('pre', 'un', 'unaccept', 'unaccepted'):
            self._list_pre(header=False, printer=printout)
        elif name in ('acc', 'accept', 'accepted'):
            self._list_accepted(header=False, printer=printout)
        elif name in ('rej', 'reject', 'rejected'):
            self._list_rejected(header=False, printer=printout)
        elif name in ('all',):
            if printout is not None:
                keys = {
                    'rejected': list(self._keys('rej')),
                    'accepted': list(self._keys('acc')),
                    'unaccepted': list(self._keys('pre')),
                }
                printout(keys)
            else:
                self._list_pre(printer=printout)
                self._list_accepted(printer=printout)
                self._list_rejected(printer=printout)
        else:
            err = ('Unrecognized key type "{0}".  Run with -h for options.'
                    ).format(name)
            self._log(err, level='error')

    def _get_outputter(self):
        get_outputter = salt.output.get_outputter
        if self.opts['raw_out']:
            printout = get_outputter('raw')
        elif self.opts['json_out']:
            printout = get_outputter('json')
        elif self.opts['yaml_out']:
            printout = get_outputter('yaml')
        else:
            printout = None # use default color output
        return printout

    def _print_key(self, name):
        '''
        Print out the specified public key
        '''
        keys = self._keys('pre', True).union(self._keys('acc', True))
        for key in sorted(keys):
            if key.endswith(name):
                with open(key, 'r') as kfn:
                    self._log(kfn.read())

    def _print_all(self):
        '''
        Print out the public keys, all of em'
        '''
        self._log('{0}Unaccepted keys:{1}'.format(
            self.colors['LIGHT_RED'], self.colors['ENDC']
            ))
        for key in sorted(self._keys('pre', True)):
            self._log('  {0}{1}{2}'.format(
                self.colors['RED'],
                os.path.basename(key),
                self.colors['ENDC']
                ))
            with open(key, 'r') as kfn:
                self._log(kfn.read())
        self._log('{0}Accepted keys:{1}'.format(
            self.colors['LIGHT_GREEN'], self.colors['ENDC']
            ))
        for key in sorted(self._keys('acc', True)):
            self._log('  {0}{1}{2}'.format(
                self.colors['GREEN'],
                os.path.basename(key),
                self.colors['ENDC']
                ))
            with open(key, 'r') as kfn:
                self._log(kfn.read())
        self._log('{0}Rejected keys:{1}'.format(
            self.colors['LIGHT_BLUE'], self.colors['ENDC']
            ))
        for key in sorted(self._keys('pre', True)):
            self._log('  {0}{1}{2}'.format(
                self.colors['BLUE'],
                os.path.basename(key),
                self.colors['ENDC']))
            with open(key, 'r') as kfn:
                self._log(kfn.read())

    def _accept(self, key):
        '''
        Accept a specified host's public key
        '''
        (minions_accepted,
         minions_pre,
         minions_rejected) = self._check_minions_directories()
        pre = os.listdir(minions_pre)
        if key not in pre:
            err = ('The key named {0} does not exist, please accept an '
                   'available key').format(key)
            #log.error(err)
            self._log(err, level='error')
            sys.exit(43)
        shutil.move(os.path.join(minions_pre, key),
                    os.path.join(minions_accepted, key))
        eload = {'result': True,
                 'act': 'accept',
                 'id': key}
        self.event.fire_event(eload, 'key')
        self._log(
                'Key for {0} accepted.'.format(key),
                level='info'
                )

    def _accept_all(self):
        '''
        Accept all keys in pre
        '''
        (minions_accepted,
         minions_pre,
         minions_rejected) = self._check_minions_directories()
        for key in os.listdir(minions_pre):
            self._accept(key)

    def _delete_key(self, delete=None):
        '''
        Delete a key
        '''
        (minions_accepted,
         minions_pre,
         minions_rejected) = self._check_minions_directories()
        if delete is None:
            delete = self.opts['delete']
        pre = os.path.join(minions_pre, delete)
        acc = os.path.join(minions_accepted, delete)
        rej = os.path.join(minions_rejected, delete)
        if os.path.exists(pre):
            os.remove(pre)
            self._log('Removed pending key {0}'.format(delete),
                         level='info')
        if os.path.exists(acc):
            os.remove(acc)
            self._log('Removed accepted key {0}'.format(delete),
                         level='info')
        if os.path.exists(rej):
            os.remove(rej)
            self._log('Removed rejected key {0}'.format(delete),
                         level='info')

    def _delete_all(self):
        '''
        Delete all keys
        '''
        for dir in ("acc", "rej", "pre"):
            for key in self._keys(dir):
                self._delete_key(key)

    def _reject(self, key):
        '''
        Reject a specified host's public key
        '''
        (minions_accepted,
         minions_pre,
         minions_rejected) = self._check_minions_directories()
        pre = os.listdir(minions_pre)
        if key not in pre:
            err = ('The host named {0} is unavailable, please accept an '
                   'available key').format(key)
            self._log(err, level='error')
            sys.exit(43)
        shutil.move(os.path.join(minions_pre, key),
                    os.path.join(minions_rejected, key))
        self._log('{0} key rejected.'.format(key), level='info')

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
        for dir_ in [minions_accepted, minions_pre, minions_rejected]:
            if not os.path.isdir(dir_):
                err = ('The minions directory {0} is not present, ensure '
                       'that the master server has been started'.format(dir_))
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
            self._list(self.opts['list'])
        elif self.opts['list_all']:
            self._list('all')
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
        elif self.opts['delete_all']:
            self._delete_all()
        else:
            self._list('all')
