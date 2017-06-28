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
import base64
import errno
import logging
import os
import re
import sys

# Import salt libs
import salt.client
import salt.utils.gzip_util
import salt.utils.itertools
import salt.utils.minions
from salt.utils import parsers, to_bytes
from salt.utils.verify import verify_log
import salt.output

# Import 3rd party libs
from salt.ext import six

log = logging.getLogger(__name__)


class SaltCPCli(parsers.SaltCPOptionParser):
    '''
    Run the salt-cp command line client
    '''

    def run(self):
        '''
        Execute salt-cp
        '''
        self.parse_args()

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
        self.is_windows = salt.utils.is_windows()

    def _mode(self, path):
        if self.is_windows:
            return None
        try:
            return int(oct(os.stat(path).st_mode)[-4:], 8)
        except (TypeError, IndexError, ValueError):
            return None

    def _recurse(self, path):
        '''
        Get a list of all specified files
        '''
        files = {}
        empty_dirs = []
        try:
            sub_paths = os.listdir(path)
        except OSError as exc:
            if exc.errno == errno.ENOENT:
                # Path does not exist
                sys.stderr.write('{0} does not exist\n'.format(path))
                sys.exit(42)
            elif exc.errno in (errno.EINVAL, errno.ENOTDIR):
                # Path is a file (EINVAL on Windows, ENOTDIR otherwise)
                files[path] = self._mode(path)
        else:
            if not sub_paths:
                empty_dirs.append(path)
            for fn_ in sub_paths:
                files_, empty_dirs_ = self._recurse(os.path.join(path, fn_))
                files.update(files_)
                empty_dirs.extend(empty_dirs_)

        return files, empty_dirs

    def _list_files(self):
        files = {}
        empty_dirs = set()
        for fn_ in self.opts['src']:
            files_, empty_dirs_ = self._recurse(fn_)
            files.update(files_)
            empty_dirs.update(empty_dirs_)
        return files, sorted(empty_dirs)

    def run(self):
        '''
        Make the salt client call
        '''
        files, empty_dirs = self._list_files()
        dest = self.opts['dest']
        gzip = self.opts['gzip']
        tgt = self.opts['tgt']
        timeout = self.opts['timeout']
        selected_target_option = self.opts.get('selected_target_option')

        dest_is_dir = bool(empty_dirs) \
            or len(files) > 1 \
            or bool(re.search(r'[\\/]$', dest))

        reader = salt.utils.gzip_util.compress_file \
            if gzip \
            else salt.utils.itertools.read_file

        minions = salt.utils.minions.CkMinions(self.opts).check_minions(
            tgt,
            tgt_type=selected_target_option or 'glob')

        local = salt.client.get_local_client(self.opts['conf_file'])

        def _get_remote_path(fn_):
            if fn_ in self.opts['src']:
                # This was a filename explicitly passed on the CLI
                return os.path.join(dest, os.path.basename(fn_)) \
                    if dest_is_dir \
                    else dest
            else:
                for path in self.opts['src']:
                    relpath = os.path.relpath(fn_, path + os.sep)
                    if relpath.startswith(parent):
                        # File is not within this dir
                        continue
                    return os.path.join(dest, os.path.basename(path), relpath)
                else:  # pylint: disable=useless-else-on-loop
                    # Should not happen
                    log.error('Failed to find remote path for %s', fn_)
                    return None

        ret = {}
        parent = '..' + os.sep
        for fn_, mode in six.iteritems(files):
            remote_path = _get_remote_path(fn_)

            index = 1
            failed = {}
            for chunk in reader(fn_, chunk_size=self.opts['salt_cp_chunk_size']):
                chunk = base64.b64encode(to_bytes(chunk))
                append = index > 1
                log.debug(
                    'Copying %s to %starget \'%s\' as %s%s',
                    fn_,
                    '{0} '.format(selected_target_option)
                        if selected_target_option
                        else '',
                    tgt,
                    remote_path,
                    ' (chunk #{0})'.format(index) if append else ''
                )
                args = [
                    tgt,
                    'cp.recv',
                    [remote_path, chunk, append, gzip, mode],
                    timeout,
                ]
                if selected_target_option is not None:
                    args.append(selected_target_option)

                result = local.cmd(*args)

                if not result:
                    # Publish failed
                    msg = (
                        'Publish failed.{0} It may be necessary to '
                        'decrease salt_cp_chunk_size (current value: '
                        '{1})'.format(
                            ' File partially transferred.' if index > 1 else '',
                            self.opts['salt_cp_chunk_size'],
                        )
                    )
                    for minion in minions:
                        ret.setdefault(minion, {})[remote_path] = msg
                    break

                for minion_id, minion_ret in six.iteritems(result):
                    ret.setdefault(minion_id, {})[remote_path] = minion_ret
                    # Catch first error message for a given minion, we will
                    # rewrite the results after we're done iterating through
                    # the chunks.
                    if minion_ret is not True and minion_id not in failed:
                        failed[minion_id] = minion_ret

                index += 1

            for minion_id, msg in six.iteritems(failed):
                ret[minion_id][remote_path] = msg

        for dirname in empty_dirs:
            remote_path = _get_remote_path(dirname)
            log.debug(
                'Creating empty dir %s on %starget \'%s\'',
                dirname,
                '{0} '.format(selected_target_option)
                    if selected_target_option
                    else '',
                tgt,
            )
            args = [tgt, 'cp.recv', [remote_path, None], timeout]
            if selected_target_option is not None:
                args.append(selected_target_option)

            for minion_id, minion_ret in six.iteritems(local.cmd(*args)):
                ret.setdefault(minion_id, {})[remote_path] = minion_ret

        salt.output.display_output(
                ret,
                self.opts.get('output', 'nested'),
                self.opts)
