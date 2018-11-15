# -*- coding: utf-8 -*-
'''
Execute batch runs
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import math
import time
import copy
from datetime import datetime, timedelta

# Import salt libs
import salt.utils.stringutils
import salt.client
import salt.output
import salt.exceptions

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext import six
from salt.ext.six.moves import range
# pylint: enable=import-error,no-name-in-module,redefined-builtin
import logging

log = logging.getLogger(__name__)


def _get_bnum(opts, minions, quiet):
    '''
    Return the active number of minions to maintain
    '''
    partition = lambda x: float(x) / 100.0 * len(minions)
    try:
        if '%' in opts['batch']:
            res = partition(float(opts['batch'].strip('%')))
            if res < 1:
                return int(math.ceil(res))
            else:
                return int(res)
        else:
            return int(opts['batch'])
    except ValueError:
        if not quiet:
            salt.utils.stringutils.print_cli('Invalid batch data sent: {0}\nData must be in the '
                      'form of %10, 10% or 3'.format(opts['batch']))


def _batch_get_opts(
        tgt,
        fun,
        batch,
        parent_opts,
        arg=(),
        tgt_type='glob',
        ret='',
        kwarg=None,
        **kwargs):
    # We need to re-import salt.utils.args here
    # even though it has already been imported.
    # when cmd_batch is called via the NetAPI
    # the module is unavailable.
    import salt.utils.args

    arg = salt.utils.args.condition_input(arg, kwarg)
    opts = {'tgt': tgt,
            'fun': fun,
            'arg': arg,
            'tgt_type': tgt_type,
            'ret': ret,
            'batch': batch,
            'failhard': kwargs.get('failhard', False),
            'raw': kwargs.get('raw', False)}

    if 'timeout' in kwargs:
        opts['timeout'] = kwargs['timeout']
    if 'gather_job_timeout' in kwargs:
        opts['gather_job_timeout'] = kwargs['gather_job_timeout']
    if 'batch_wait' in kwargs:
        opts['batch_wait'] = int(kwargs['batch_wait'])

    for key, val in six.iteritems(parent_opts):
        if key not in opts:
            opts[key] = val

    return opts


def _batch_get_eauth(kwargs):
    eauth = {}
    if 'eauth' in kwargs:
        eauth['eauth'] = kwargs.pop('eauth')
    if 'username' in kwargs:
        eauth['username'] = kwargs.pop('username')
    if 'password' in kwargs:
        eauth['password'] = kwargs.pop('password')
    if 'token' in kwargs:
        eauth['token'] = kwargs.pop('token')
    return eauth


class Batch(object):
    '''
    Manage the execution of batch runs
    '''
    def __init__(self, opts, eauth=None, quiet=False, parser=None):
        self.opts = opts
        self.eauth = eauth if eauth else {}
        self.pub_kwargs = eauth if eauth else {}
        self.quiet = quiet
        self.local = salt.client.get_local_client(opts['conf_file'])
        self.minions, self.ping_gen, self.down_minions = self.__gather_minions()
        self.options = parser

    def __gather_minions(self):
        '''
        Return a list of minions to use for the batch run
        '''
        args = [self.opts['tgt'],
                'test.ping',
                [],
                self.opts['timeout'],
                ]

        selected_target_option = self.opts.get('selected_target_option', None)
        if selected_target_option is not None:
            args.append(selected_target_option)
        else:
            args.append(self.opts.get('tgt_type', 'glob'))

        self.pub_kwargs['yield_pub_data'] = True
        ping_gen = self.local.cmd_iter(*args,
                                       gather_job_timeout=self.opts['gather_job_timeout'],
                                       **self.pub_kwargs)

        # Broadcast to targets
        fret = set()
        nret = set()
        for ret in ping_gen:
            if ('minions' and 'jid') in ret:
                for minion in ret['minions']:
                    nret.add(minion)
                continue
            else:
                try:
                    m = next(six.iterkeys(ret))
                except StopIteration:
                    if not self.quiet:
                        salt.utils.stringutils.print_cli('No minions matched the target.')
                    break
                if m is not None:
                    fret.add(m)
        return (list(fret), ping_gen, nret.difference(fret))

    def get_bnum(self):
        return _get_bnum(self.opts, self.minions, self.quiet)

    def __update_wait(self, wait):
        now = datetime.now()
        i = 0
        while i < len(wait) and wait[i] <= now:
            i += 1
        if i:
            del wait[:i]

    def _get_next(self, bnum, active, wait, to_run):
        next_ = []
        if len(to_run) <= bnum - len(wait) and not active:
            # last bit of them, add them all to next iterator
            while to_run:
                next_.append(to_run.pop())
        else:
            for i in range(bnum - len(active) - len(wait)):
                if to_run:
                    minion_id = to_run.pop()
                    if isinstance(minion_id, dict):
                        next_.append(minion_id.keys()[0])
                    else:
                        next_.append(minion_id)
        return next_

    def _generate_iter(self, next_, iters, minion_tracker):
        show_jid, show_verbose = self._get_show_options()
        args = [
            self.opts['fun'],
            self.opts['arg'],
            self.opts['timeout'],
            'list',
        ]
        if not self.quiet:
            salt.utils.stringutils.print_cli('\nExecuting run on {0}\n'.format(sorted(next_)))
        # create a new iterator for this batch of minions
        return self.local.cmd_iter_no_block(
                        next_,
                        *args,
                        raw=self.opts.get('raw', False),
                        ret=self.opts.get('return', ''),
                        show_jid=show_jid,
                        verbose=show_verbose,
                        gather_job_timeout=self.opts['gather_job_timeout'],
                        **self.eauth)

    def _find_new_minions(self):
        new_minions = []
        # see if we found more minions
        for ping_ret in self.ping_gen:
            if ping_ret is None:
                break
            m = next(six.iterkeys(ping_ret))
            if m not in self.minions:
                new_minions.append(m)
        return new_minions

    def _remove_minion_from_iterator(self, minions, iterator, minion_tracker):
        for minionid in minions:
            if minionid in minion_tracker[iterator]['minions']:
                minion_tracker[iterator]['minions'].remove(minionid)
            else:
                salt.utils.stringutils.print_cli(
                    'minion {0} was already deleted from tracker, probably a duplicate key'.format(minionid))

    def _process_iterator(self, iterator):
        minion_returns = {}
        completed = False
        # Gather returns until we get to the bottom
        ncnt = 0
        for ret in iterator:
            if ret is None:
                time.sleep(0.01)
                ncnt += 1
                if ncnt > 5:
                    break
                continue
            if self.opts.get('raw'):
                ret = {ret['data']['id']: ret}
            minion_returns.update(ret)
        else:
            # if a iterator is done:
            # - set it to inactive
            # - add minions that have not responded to minion_returns{}
            completed = True
        return minion_returns, completed

    def _process_iterators(self, iters, minion_tracker):
        minion_returns = {}
        done_iters = []
        for it in iters:
            it_minion_returns, completed = self._process_iterator(it)
            minion_returns.update(it_minion_returns)
            done_minions = it_minion_returns.keys()
            if completed:
                done_iters.append(it)
                # remove completed iterators from the iters list
                iters.remove(it)

            minion_tracker[it]['active'] = False

            # add all minions that belong to this iterator and
            # that have not responded to minion_returns{} with an empty response
            for minion in minion_tracker[it]['minions']:
                if minion not in done_minions:
                    it_minion_returns[minion] = {'ret': {}}

            self._remove_minion_from_iterator(done_minions, it, minion_tracker)

        return minion_returns, done_iters

    def _remove_minion_from_active(self, minion, active, wait, bwait):
        if minion in active:
            active.remove(minion)
            if bwait:
                wait.append(datetime.now() + timedelta(seconds=bwait))

    def _update_ret(self, minion_returns, ret):
        for minion, data in six.iteritems(minion_returns):
            # Munge retcode into return data
            failhard = False
            if 'retcode' in data and isinstance(data['ret'], dict) and 'retcode' not in data['ret']:
                data['ret']['retcode'] = data['retcode']
                if self.opts.get('failhard') and data['ret']['retcode'] > 0:
                    failhard = True

            if self.opts.get('raw'):
                ret[minion] = data
                yield data
            else:
                ret[minion] = data['ret']
                yield {minion: data['ret']}
            if not self.quiet:
                ret[minion] = data['ret']
                data[minion] = data.pop('ret')
                if 'out' in data:
                    out = data.pop('out')
                else:
                    out = None
                salt.output.display_output(
                        data,
                        out,
                        self.opts)
            if failhard:
                log.error(
                    'Minion %s returned with non-zero exit code. '
                    'Batch run stopped due to failhard', minion
                )
                raise StopIteration

    def _get_show_options(self):
        ret = [False, False]
        if self.options:
            ret = [self.options.show_jid, self.options.verbose]
        return ret

    def _add_to_trackers(self, bnum, iters, active, wait, to_run, minion_tracker):
        next_ = self._get_next(bnum, active, wait, to_run)
        if next_:
            active += next_
            new_iter = self._generate_iter(next_, iters, minion_tracker)
            # add it to our iterators and to the minion_tracker
            iters.append(new_iter)
            # every iterator added is 'active' and has its set of minions
            minion_tracker[new_iter] = {
                'minions': next_,
                'active': True
            }
        return next_

    def run(self):
        '''
        Execute the batch run
        '''
        bnum = self.get_bnum()
        # No targets to run
        if not self.minions:
            return
        to_run = copy.deepcopy(self.minions)
        active = []
        ret = {}
        iters = []
        # wait the specified time before decide a job is actually done
        bwait = self.opts.get('batch_wait', 0)
        wait = []

        # the minion tracker keeps track of responses and iterators
        # - it removes finished iterators from iters[]
        # - if a previously detected minion does not respond, its
        #   added with an empty answer to ret{} once the timeout is reached
        # - unresponsive minions are removed from active[] to make
        #   sure that the main while loop finishes even with unresp minions
        minion_tracker = {}

        if not self.quiet:
            # We already know some minions didn't respond to the ping, so inform
            # the user we won't be attempting to run a job on them
            for down_minion in self.down_minions:
                salt.utils.stringutils.print_cli('Minion {0} did not respond. No job will be sent.'.format(down_minion))

        # Iterate while we still have things to execute
        while len(ret) < len(self.minions):

            if bwait and wait:
                self.__update_wait(wait)

            next_ = self._add_to_trackers(bnum, iters, active, wait, to_run, minion_tracker)

            if not next_:
                time.sleep(0.02)

            new_minions = self._find_new_minions()
            self.minions += new_minions
            to_run += new_minions

            minion_returns, done_iterators = self._process_iterators(iters, minion_tracker)

            for minion in minion_returns:
                self._remove_minion_from_active(minion, active, wait, bwait)

            for i in self._update_ret(minion_returns, ret):
                yield i

