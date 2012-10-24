'''
The actual saltkey functional code
'''

# Import python modules
import os
import shutil
import sys
import logging
import glob
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
        self.event = salt.utils.event.MasterEvent(opts['sock_dir'])
        self.colors = salt.utils.get_colors(
                not bool(self.opts.get('no_color', False))
                )
        if not opts.get('gen_keys', None):
            # Only check for a master running IF we need it.
            # While generating keys we don't
            self._check_master()

    def _check_master(self):
        '''
        Log if the master is not running
        '''
        if not os.path.exists(
                os.path.join(
                    self.opts['sock_dir'],
                    'publish_pull.ipc'
                    )
                ):
            self._log('Master is not running', level='error')


    def _cli_opts(self, **kwargs):
        '''
        Set the default cli opts to use when calling salt-key as an api. All
        options can be passed in a kwargs to override defaults.
        '''
        opts = {
                'list': '',
                'list_all': False,
                'accept': '',
                'accept_all': False,
                'reject': '',
                'reject_all': False,
                'print': '',
                'print_all': False,
                'delete': '',
                'delete_all': False,
                'finger': '',
                'quiet': False,
                'yes': True,
                'gen_keys': '',
                'gen_keys_dir': '.',
                'keysize': 2048,
                'conf_file': '/etc/salt/master',
                'raw_out': False,
                'yaml_out': False,
                'json_out': False,
                'no_color': False,
                }
        opts.update(kwargs)
        self.opts.update(opts)

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
        if not self.opts.get('quiet', False):
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
        selected_output = self.opts.get('selected_output_option', None)
        printout = salt.output.get_printout(
            {}, selected_output, self.opts, indent=2
        )

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
        Delete a key or keys by glob
        '''
        # Don't ask for verification if yes is not set
        del_ = []
        yes = self.opts.get('yes', True)
        (minions_accepted,
         minions_pre,
         minions_rejected) = self._check_minions_directories()
        if delete is None:
            delete = self.opts['delete']
        else:
            # If a key is explicitly passed then don't ask for verification
            yes = True
        del_.extend(glob.glob(os.path.join(minions_pre, delete)))
        del_.extend(glob.glob(os.path.join(minions_accepted, delete)))
        del_.extend(glob.glob(os.path.join(minions_rejected, delete)))
        if del_:
            rm_ = True
            if not yes:
                msg = 'The following keys are going to be deleted:\n'
                #for key in sorted(del_):
                for key in sorted(set(del_)):
                    msg += '{0}\n'.format(key)
                veri = raw_input('{0}[n/Y]'.format(msg))
                if veri.lower().startswith('n'):
                    rm_ = False
            if rm_:
                for key in del_:
                    os.remove(key)
                    filepath, filename = os.path.split(key)
                    self._log('Removed pending key {0}'.format(filename),
                            level='info')

    def _delete_all(self):
        '''
        Delete all keys
        '''
        # Don't ask for verification if yes is not set
        del_ = set()
        for dir in ("acc", "rej", "pre"):
            for key in self._keys(dir):
                del_.add(key)
        msg = 'The following keys are going to be deleted:\n'
        for key in sorted(del_):
            msg += '{0}\n'.format(key)
        veri = raw_input('{0}[n/Y]'.format(msg))
        if veri.lower().startswith('n'):
            return
        for key in del_:
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
        '''
        Return the minion keys directory paths
        '''
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

    def finger(self):
        '''
        Return the fingerprint for a specified key
        '''
        fkey = self.opts.get('finger', 'master')
        dirs = list(self._check_minions_directories())
        dirs.append(self.opts['pki_dir'])
        sigs = {}
        for dir_ in dirs:
            pub = os.path.join(dir_, '{0}.pub'.format(fkey))
            fin = salt.utils.pem_finger(pub)
            if fin:
                self._log('Signature for {0} public key: {1}'.format(fkey, fin))
                sigs['{0}.pub'.format(fkey)] = fin
            pub = os.path.join(dir_, '{0}'.format(fkey))
            fin = salt.utils.pem_finger(pub)
            if fin:
                self._log('Signature for {0} public key: {1}'.format(fkey, fin))
                sigs['{0}.pub'.format(fkey)] = fin
            pri = os.path.join(dir_, '{0}.pem'.format(fkey))
            fin = salt.utils.pem_finger(pri)
            if fin:
                self._log('Signature for {0} private key: {1}'.format(fkey, fin))
                sigs['{0}.pem'.format(fkey)] = fin
        return sigs

    def run(self):
        '''
        Run the logic for saltkey
        '''
        if self.opts['gen_keys']:
            salt.crypt.gen_keys(
                    self.opts['gen_keys_dir'],
                    self.opts['gen_keys'],
                    self.opts['keysize'])
            self._log('Keys generation complete', level='info')
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
        elif self.opts['finger']:
            self.finger()
        else:
            self._list('all')
