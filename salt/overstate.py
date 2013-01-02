'''
Manage the proces of the overstate. The overstate is a means to orchistrate
the deployment of states over groups of servers.
'''

# 1. Read in overstate
# 2. Create initial order
# 3. Start list evaluation
# 4. Verify requisites
# 5. Execute state call
# 6. append data to running

# Import python libs
import sys
import os

# Import salt libs
import salt.client
import salt.utils

# Import third party libs
import yaml


class OverState(object):
    '''
    Manage sls file calls over multiple systems
    '''
    def __init__(self, opts, env='base', overstate=None):
        self.opts = opts
        self.env = env
        self.over = self.__read_over(overstate)
        self.names = self._names()
        self.local = salt.client.LocalClient(self.opts['conf_file'])
        self.over_run = {}

    def __read_over(self, overstate):
        '''
        Read in the overstate file
        '''
        if overstate:
            with salt.utils.fopen(overstate) as fp_:
                try:
                    # TODO Use render system
                    return self.__sort_stages(yaml.load(fp_))
                except Exception:
                    return {}
        if self.env not in self.opts['file_roots']:
            return {}
        for root in self.opts['file_roots'][self.env]:
            fn_ = os.path.join(
                    root,
                    self.opts.get('overstate', 'overstate.sls')
                    )
            if not os.path.isfile(fn_):
                continue
            with salt.utils.fopen(fn_) as fp_:
                try:
                    # TODO Use render system
                    return self.__sort_stages(yaml.load(fp_))
                except Exception:
                    return {}
        return {}

    def __sort_stages(self, pre_over):
        '''
        Generate the list of executions
        '''
        comps = []
        for key in sorted(pre_over):
            comps.append({key: pre_over[key]})
        return comps

    def _stage_list(self, match):
        '''
        Return a list of ids cleared for a given stage
        '''
        if isinstance(match, list):
            match = ' or '.join(match)
        raw = self.local.cmd(match, 'test.ping', expr_form='compound')
        return raw.keys()

    def _check_result(self, running):
        '''
        Check the total return value of the run and determine if the running
        dict has any issues
        '''
        if not isinstance(running, dict):
            return False
        if not running:
            return False
        for host in running:
            for tag, ret in running[host].items():
                if not 'result' in ret:
                    return False
                if ret['result'] is False:
                    return False
        return True

    def _names(self):
        '''
        Return a list of names defined in the overstate
        '''
        names = set()
        for comp in self.over:
            names.add(comp.keys()[0])
        return names

    def get_stage(self, name):
        '''
        Return the named stage
        '''
        for stage in self.over:
            if name in stage:
                return stage

    def verify_stage(self, name, stage):
        '''
        Verify that the stage is valid, return the stage, or a list of errors
        '''
        errors = []
        if not 'match' in stage:
            errors.append('No "match" argument in stage.')
        if errors:
            return errors
        return stage

    def call_stage(self, name, stage):
        '''
        Check if a stage has any requisites and run them first
        '''
        fun = 'state.highstate'
        arg = ()
        if 'sls' in stage:
            fun = 'state.sls'
            arg = (','.join(stage['sls']), self.env)
        req_fail = {name: {}}
        if 'require' in stage:
            for req in stage['require']:
                if req in self.over_run:
                    # The req has been called, check it
                    if self._check_result(self.over_run[req]):
                        # This req is good, check the next
                        continue
                    else:
                        tag_name = 'req_|-fail_|-fail_|-None'
                        failure = {tag_name: {
                                'result': False,
                                'comment': 'Requisite {0} failed for stage'.format(req),
                                'name': 'Requisite Failure',
                                'changes': {},
                                '__run_num__': 0,
                                    }
                                }
                        self.over_run[name] = failure
                        req_fail[name].update(failure)
                elif req not in self.names:
                    tag_name = 'No_|-Req_|-fail_|-None'
                    failure = {tag_name: {
                            'result': False,
                            'comment': 'Requisite {0} was not found'.format(req),
                            'name': 'Requisite Failure',
                            'changes': {},
                            '__run_num__': 0,
                                }
                            }
                    self.over_run[name] = failure
                    req_fail[name].update(failure)
                else:
                    for comp in self.over:
                        rname = comp.keys()[0]
                        if req == rname:
                            stage = comp[rname]
                            v_stage = self.verify_stage(rname, stage)
                            if isinstance(v_stage, list):
                                yield {rname: v_stage}
                            else:
                                yield self.call_stage(rname, stage)
        if req_fail[name]:
            yield req_fail
        else:
            ret = {}
            tgt = self._stage_list(stage['match'])
            for minion in self.local.cmd_iter(
                    tgt,
                    fun,
                    arg,
                    expr_form='list'):
                ret.update({minion.keys()[0]: minion[minion.keys()[0]]['ret']})
            self.over_run[name] = ret
            yield {name: ret}

    def stages(self):
        '''
        Execute the stages
        '''
        self.over_run = {}
        for comp in self.over:
            name = comp.keys()[0]
            stage = comp[name]
            if not name in self.over_run:
                self.call_stage(name, stage)

    def stages_iter(self):
        '''
        Return an iterator that yields the state call data as it is processed
        '''
        def yielder(gen_ret):
            if (not isinstance(gen_ret, list)
                    and not isinstance(gen_ret, dict)
                    and hasattr(gen_ret, 'next')):
                for sub_ret in gen_ret:
                    for yret in yielder(sub_ret):
                        yield yret
            else:
                yield gen_ret

        self.over_run = {}
        yield self.over
        for comp in self.over:
            name = comp.keys()[0]
            stage = comp[name]
            if not name in self.over_run:
                v_stage = self.verify_stage(name, stage)
                if isinstance(v_stage, list):
                    yield [comp]
                    yield v_stage
                else:
                    for sret in self.call_stage(name, stage):
                        for yret in yielder(sret):
                            sname = yret.keys()[0]
                            yield [self.get_stage(sname)]
                            yield yret[sname]
