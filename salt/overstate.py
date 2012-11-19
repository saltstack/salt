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
#
# Import Python libs
import sys

# Import Salt libs
import salt.client
import salt.utils

# Import third party libs
import yaml


class OverState(object):
    '''
    Manage sls file calls over multiple systems
    '''
    def __init__(self, opts, env='base'):
        self.opts = opts
        self.env = env
        self.over = self.__read_over()
        self.local = salt.client.LocalClient(self.opts)
        self.over_run = {}

    def __read_over(self):
        '''
        Read in the overstate file
        '''
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
            match = ' and '.join(match)
        raw = self.local.cmd(match, 'test.ping', expr_form='compound')
        return raw.keys()

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
        if 'require' in stage:
            for req in stage['require']:
                if req in self.over_run:
                    if self._check_result(self.over_run[req]):
                        continue
                    else:
                        self.over_run[name] = False
                elif req not in self.over:
                    self.over_run[name] = False
                else:
                    self.call_stage(self.over[req])
        ret = {}
        tgt = self._statge_list(stage['match'])
        for minion in self.local.cmd_iter(
                tgt,
                fun,
                arg,
                expr_form='compound'):
            ret.update(minion)
        self.over_run[name] = ret

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
