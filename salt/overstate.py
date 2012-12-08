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

    def call_stage(self, name, stage):
        '''
        Check if a stage has any requisites and run them first
        '''
        errors = []
        fun = 'state.highstate'
        arg = ()
        if not 'match' in stage:
            errors.append('No "match" argument in stage.')
        if errors:
            return errors
        if 'sls' in stage:
            fun = 'state.sls'
            arg = (','.join(stage['sls']), self.env)
        req_fail = {name: {}}
        if 'require' in stage:
            for req in stage['require']:
                if req in self.over_run:
                    if self._check_result(self.over_run[req]):
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
                elif req not in self.over:
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
                    self.call_stage(self.over[req])
        if req_fail[name]:
            return req_fail
        ret = {}
        tgt = self._stage_list(stage['match'])
        for minion in self.local.cmd_iter(
                tgt,
                fun,
                arg,
                expr_form='list'):
            ret.update({minion.keys()[0]: minion[minion.keys()[0]]['ret']})
        self.over_run[name] = ret
        return ret

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
        self.over_run = {}
        for comp in self.over:
            name = comp.keys()[0]
            stage = comp[name]
            if not name in self.over_run:
                yield [comp]
                yield self.call_stage(name, stage)
