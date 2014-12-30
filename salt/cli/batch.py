# -*- coding: utf-8 -*-
'''
Execute batch runs
'''

# Import python libs
from __future__ import print_function
import math
import time
import copy

# Import salt libs
import salt.client
import salt.output
import salt.utils.minions
from salt.utils import print_cli


class Batch(object):
    '''
    Manage the execution of batch runs
    '''
    def __init__(self, opts, eauth=None, quiet=False):
        self.opts = opts
        self.eauth = eauth if eauth else {}
        self.quiet = quiet
        self.local = salt.client.get_local_client(opts['conf_file'])
        self.minions = self.__gather_minions()

    def __gather_minions(self):
        '''
        Return a list of minions to use for the batch run
        '''
        ckminions = salt.utils.minions.CkMinions(self.opts)
        selected_target_option = self.opts.get('selected_target_option', None)
        if selected_target_option is not None:
            expr_form = selected_target_option
        else:
            expr_form = self.opts.get('expr_form', 'glob')
        return ckminions.check_minions(self.opts['tgt'], expr_form=expr_form)

    def get_bnum(self):
        '''
        Return the active number of minions to maintain
        '''
        partition = lambda x: float(x) / 100.0 * len(self.minions)
        try:
            if '%' in self.opts['batch']:
                res = partition(float(self.opts['batch'].strip('%')))
                if res < 1:
                    return int(math.ceil(res))
                else:
                    return int(res)
            else:
                return int(self.opts['batch'])
        except ValueError:
            if not self.quiet:
                print_cli('Invalid batch data sent: {0}\nData must be in the '
                          'form of %10, 10% or 3'.format(self.opts['batch']))

    def run(self):
        '''
        Execute the batch run
        '''
        args = [[],
                self.opts['fun'],
                self.opts['arg'],
                self.opts['timeout'],
                'list',
                ]
        bnum = self.get_bnum()
        to_run = copy.deepcopy(self.minions)
        active = []
        ret = {}
        iters = []

        # the minion tracker keeps track of responses and iterators
        # - it removes finished iterators from iters[]
        # - if a previously detected minion does not respond, its
        #   added with an empty answer to ret{} once the timeout is reached
        # - unresponsive minions are removed from active[] to make
        #   sure that the main while loop finishes even with unresp minions
        minion_tracker = {}

        # Iterate while we still have things to execute
        while len(ret) < len(self.minions):
            next_ = []
            if len(to_run) <= bnum and not active:
                # last bit of them, add them all to next iterator
                while to_run:
                    next_.append(to_run.pop())
            else:
                for i in range(bnum - len(active)):
                    if to_run:
                        next_.append(to_run.pop())

            active += next_
            args[0] = next_

            if next_:
                if not self.quiet:
                    print_cli('\nExecuting run on {0}\n'.format(next_))
                # create a new iterator for this batch of minions
                new_iter = self.local.cmd_iter_no_block(
                                *args,
                                raw=self.opts.get('raw', False),
                                ret=self.opts.get('return', ''),
                                **self.eauth)
                # add it to our iterators and to the minion_tracker
                iters.append(new_iter)
                minion_tracker[new_iter] = {}
                # every iterator added is 'active' and has its set of minions
                minion_tracker[new_iter]['minions'] = next_
                minion_tracker[new_iter]['active'] = True

            else:
                time.sleep(0.02)
            parts = {}

            for queue in iters:
                try:
                    # Gather returns until we get to the bottom
                    ncnt = 0
                    while True:
                        part = next(queue)
                        if part is None:
                            time.sleep(0.01)
                            ncnt += 1
                            if ncnt > 5:
                                break
                            continue
                        if self.opts.get('raw'):
                            parts.update({part['id']: part})
                        else:
                            parts.update(part)
                except StopIteration:
                    # if a iterator is done:
                    # - set it to inactive
                    # - add minions that have not responded to parts{}

                    # check if the tracker contains the iterator
                    if queue in minion_tracker:
                        minion_tracker[queue]['active'] = False

                        # add all minions that belong to this iterator and
                        # that have not responded to parts{} with an empty response
                        for minion in minion_tracker[queue]['minions']:
                            if minion not in parts:
                                parts[minion] = {}
                                parts[minion]['ret'] = {}

            for minion, data in parts.items():
                active.remove(minion)
                if self.opts.get('raw'):
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

            # remove inactive iterators from the iters list
            for queue in minion_tracker:
                # only remove inactive queues
                if not minion_tracker[queue]['active'] and queue in iters:
                    iters.remove(queue)
                    # also remove the iterator's minions from the active list
                    for minion in minion_tracker[queue]['minions']:
                        if minion in active:
                            active.remove(minion)
