'''
Execute batch runs
'''

# Import python libs
import math
import time
import copy

# Import salt libs
import salt.client
import salt.output


class Batch(object):
    '''
    Manage the execution of batch runs
    '''
    def __init__(self, opts, quiet=False):
        self.opts = opts
        self.quiet = quiet
        self.local = salt.client.LocalClient(opts['conf_file'])
        self.minions = self.__gather_minions()

    def __gather_minions(self):
        '''
        Return a list of minions to use for the batch run
        '''
        args = [self.opts['tgt'],
                'test.ping',
                [],
                5,
                ]

        selected_target_option = self.opts.get('selected_target_option', None)
        if selected_target_option is not None:
            args.append(selected_target_option)
        else:
            args.append(self.opts.get('expr_form', 'glob'))

        fret = []
        for ret in self.local.cmd_iter(*args):
            for minion in ret:
                if not self.quiet:
                    print('{0} Detected for this batch run'.format(minion))
                fret.append(minion)
        return sorted(fret)

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
                print(('Invalid batch data sent: {0}\nData must be in the form'
                       'of %10, 10% or 3').format(self.opts['batch']))

    def run(self):
        '''
        Execute the batch run
        '''
        args = [[],
                self.opts['fun'],
                self.opts['arg'],
                99999,
                'list',
                ]
        bnum = self.get_bnum()
        to_run = copy.deepcopy(self.minions)
        active = []
        ret = {}
        iters = []
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
                    print('\nExecuting run on {0}\n'.format(next_))
                iters.append(
                        self.local.cmd_iter_no_block(
                            *args,
                            raw=self.opts.get('raw', False))
                        )
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
                    # remove the iter, it is done
                    pass
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
