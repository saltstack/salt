# -*- coding: utf-8 -*-
'''
The cp module is used to execute the logic used by the salt-cp command
line application, salt-cp is NOT intended to broadcast large files, it is
intended to handle text files.
Salt-cp can be used to distribute configuration files
'''

# Import python libs
from __future__ import print_function
from __future__ import absolute_import
import os
import sys
import pprint

# Import salt libs
import salt.client
from salt.utils import parsers, print_cli
from salt.utils.verify import verify_files, verify_log


class SaltCPCli(parsers.SaltCPOptionParser):
    '''
    Run the salt-cp command line client
    '''

    def run(self):
        '''
        Execute salt-cp
        '''
        self.parse_args()

        if self.config['verify_env']:
            if not self.config['log_file'].startswith(('tcp://',
                                                       'udp://',
                                                       'file://')):
                # Logfile is not using Syslog, verify
                verify_files(
                    [self.config['log_file']],
                    self.config['user']
                )

        # Setup file logging!
        self.setup_logfile_logger()
        verify_log(self.config)

        cp_ = SaltCP(self.config)
        cp_.run()


class SaltCP(object):
    '''
    Create a salt cp object, used to distribute simple files with salt
    '''
    def __init__(self, opts):
        self.opts = opts

    def _file_dict(self, fn_):
        '''
        Take a path and return the contents of the file as a string
        '''
        if not os.path.isfile(fn_):
            err = 'The referenced file, {0} is not available.'.format(fn_)
            sys.stderr.write(err + '\n')
            sys.exit(42)
        with salt.utils.fopen(fn_, 'r') as fp_:
            data = fp_.read()
        return {fn_: data}

    def _recurse_dir(self, fn_, files=None):
        '''
        Recursively pull files from a directory
        '''
        if files is None:
            files = {}

        for base in os.listdir(fn_):
            path = os.path.join(fn_, base)
            if os.path.isdir(path):
                files.update(self._recurse_dir(path))
            else:
                files.update(self._file_dict(path))
        return files

    def _load_files(self):
        '''
        Parse the files indicated in opts['src'] and load them into a python
        object for transport
        '''
        files = {}
        for fn_ in self.opts['src']:
            if os.path.isfile(fn_):
                files.update(self._file_dict(fn_))
            elif os.path.isdir(fn_):
                print_cli(fn_ + ' is a directory, only files are supported.')
                #files.update(self._recurse_dir(fn_))
        return files

    def run(self):
        '''
        Make the salt client call
        '''
        arg = [self._load_files(), self.opts['dest']]
        local = salt.client.get_local_client(self.opts['conf_file'])
        args = [self.opts['tgt'],
                'cp.recv',
                arg,
                self.opts['timeout'],
                ]

        selected_target_option = self.opts.get('selected_target_option', None)
        if selected_target_option is not None:
            args.append(selected_target_option)

        ret = local.cmd(*args)

        pprint.pprint(ret)
