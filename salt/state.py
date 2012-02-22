'''
The module used to execute states in salt. A state is unlike a module execution
in that instead of just executing a command it ensure that a certain state is
present on the system.

The data sent to the state calls is as follows:
    { 'state': '<state module name>',
      'fun': '<state function name>',
      'name': '<the name argument passed to all states>'
      'argn': '<arbitrary argument, can have many of these>'
      }
'''

import copy
import inspect
import fnmatch
import logging
import os
import tempfile
import collections

import salt.loader
import salt.minion


log = logging.getLogger(__name__)


def _gen_tag(low):
    '''
    Generate the running dict tag string from the low data structure
    '''
    return '{0[state]}_|-{0[__id__]}_|-{0[name]}_|-{0[fun]}'.format(low)


def _getargs(func):
    '''
    A small wrapper around getargspec that also supports callable classes
    '''
    if not callable(func):
        raise TypeError('{0} is not a callable'.format(func))

    if inspect.isfunction(func):
        aspec = inspect.getargspec(func)
    elif isinstance(func, object):
        aspec = inspect.getargspec(func.__call__)
        del aspec.args[0] # self
    else:
        raise TypeError("Cannot inspect argument list for '{0}'".format(func))

    return aspec


def format_log(ret):
    '''
    Format the state into a log message
    '''
    msg = ''
    if isinstance(ret, dict):
        # Looks like the ret may be a valid state return
        if 'changes' in ret:
            # Yep, looks like a valid state return
            chg = ret['changes']
            if not chg:
                msg = 'No changes made for {0[name]}'.format(ret)
            elif isinstance(chg, dict):
                if 'diff' in chg:
                    if isinstance(chg['diff'], basestring):
                        msg = 'File changed:\n{0}'.format(
                                chg['diff'])
                if isinstance(chg[chg.keys()[0]], dict):
                    if 'new' in chg[chg.keys()[0]]:
                        # This is the return data from a package install
                        msg = 'Installed Packages:\n'
                        for pkg in chg:
                            old = 'absent'
                            if chg[pkg]['old']:
                                old = chg[pkg]['old']
                            msg += '{0} changed from {1} to {2}\n'.format(
                                    pkg, old, chg[pkg]['new'])
            if not msg:
                msg = str(ret['changes'])
            if ret['result']:
                log.info(msg)
            else:
                log.error(msg)
    else:
        # catch unhandled data
        log.info(str(ret))


class StateError(Exception):
    '''
    Custom exception class.
    '''

    pass


class State(object):
    '''
    Class used to execute salt states
    '''
    def __init__(self, opts):
        if 'grains' not in opts:
            opts['grains'] = salt.loader.grains(opts)
        self.opts = opts
        self.load_modules()
        self.mod_init = set()
        self.__run_num = 0

    def _mod_init(self, low):
        '''
        Check the module initilization function, if this is the first run of
        a state package that has a mod_init function, then execute the
        mod_init function in the state module.
        '''
        minit = '{0}.mod_init'.format(low['state'])
        if not low['state'] in self.mod_init:
            if minit in self.states:
                mret = self.states[minit](low)
                if not mret:
                    return
                self.mod_init.add(low['state'])

    def load_modules(self, data=None):
        '''
        Load the modules into the state
        '''
        log.info('Loading fresh modules for state activity')
        self.functions = salt.loader.minion_mods(self.opts)
        if isinstance(data, dict):
            if data.get('redirect', False):
                redirect = {}
                if isinstance(data['redirect'], str):
                    redirects = [{data['state']: data['redirect']}]
                elif isinstance(data['redirect'], list):
                    redirects = data['redirect']
                for redirect in redirects:
                    for mod in redirect:
                        funcs = salt.loader.raw_mod(self.opts,
                                redirect[mod],
                                self.functions)
                        if funcs:
                            for func in funcs:
                                f_key = '{0}{1}'.format(
                                        mod,
                                        func[func.rindex('.'):]
                                        )
                                self.functions[f_key] = funcs[func]
        self.states = salt.loader.states(self.opts, self.functions)
        self.rend = salt.loader.render(self.opts, self.functions)

    def module_refresh(self, data):
        '''
        Check to see if the modules for this state instance need to be
        updated, only update if the state is a file. If the function is
        managed check to see if the file is a possible module type, eg a
        python, pyx, or .so. Always refresh if the function is recuse, since
        that can lay down anything.
        '''
        if data['state'] == 'file':
            if data['fun'] == 'managed':
                if any((data['name'].endswith('.py'),
                        data['name'].endswith('.pyx'),
                        data['name'].endswith('.pyo'),
                        data['name'].endswith('.pyc'),
                        data['name'].endswith('.so'))):
                    self.load_modules()
                    open(os.path.join(
                        self.opts['cachedir'],
                        'module_refresh'),
                        'w+').write('')
            elif data['fun'] == 'recurse':
                self.load_modules()
                open(os.path.join(
                    self.opts['cachedir'],
                    'module_refresh'),
                    'w+').write('')
        elif data['state'] == 'pkg':
            self.load_modules()
            open(os.path.join(
                self.opts['cachedir'],
                'module_refresh'),
                'w+').write('')


    def format_verbosity(self, returns):
        '''
        Check for the state_verbose option and strip out the result=True and
        changes={} members of the state return list.
        '''
        if self.opts['state_verbose']:
            return returns
        rm_tags = []
        for tag in returns:
            if returns[tag]['result'] and not returns[tag]['changes']:
                rm_tags.append(tag)
        for tag in rm_tags:
            returns.pop(tag)
        return returns


    def verify_data(self, data):
        '''
        Verify the data, return an error statement if something is wrong
        '''
        errors = []
        if 'state' not in data:
            errors.append('Missing "state" data')
        if 'fun' not in data:
            errors.append('Missing "fun" data')
        if 'name' not in data:
            errors.append('Missing "name" data')
        if errors:
            return errors
        if data['fun'].startswith('mod_'):
            errors.append(
                    'State {0} in sls {1} uses an invalid function {2}'.format(
                        data['state'],
                        data['__sls__'],
                        data['fun'])
                    )
        full = data['state'] + '.' + data['fun']
        if full not in self.states:
            if '__sls__' in data:
                errors.append(
                    'State {0} found in sls {1} is unavailable'.format(
                        full,
                        data['__sls__']
                        )
                    )
            else:
                errors.append(
                        'Specified state {0} is unavailable.'.format(
                            full
                            )
                        )
        else:
            # First verify that the parameters are met
            aspec = _getargs(self.states[full])
            arglen = 0
            deflen = 0
            if isinstance(aspec[0], list):
                arglen = len(aspec[0])
            if isinstance(aspec[3], tuple):
                deflen = len(aspec[3])
            for ind in range(arglen - deflen):
                if aspec[0][ind] not in data:
                    errors.append('Missing parameter ' + aspec[0][ind]\
                                + ' for state ' + full)
        # If this chunk has a recursive require, then it will cause a
        # recursive loop when executing, check for it
        reqdec = ''
        if 'require' in data:
            reqdec = 'require'
        if 'watch' in data:
            # Check to see if the service has a mod_watch function, if it does
            # not, then just require
            if not '{0}.mod_watch'.format(data['state']) in self.states:
                data['require'] = data.pop('watch')
                reqdec = 'require'
            else:
                reqdec = 'watch'
        if reqdec:
            for req in data[reqdec]:
                if data['state'] == req.keys()[0]:
                    if fnmatch.fnmatch(data['name'], req[req.keys()[0]]) \
                            or fnmatch.fnmatch(data['__id__'], req[req.keys()[0]]):
                        err = ('Recursive require detected in SLS {0} for'
                               ' require {1} in ID {2}').format(
                                   data['__sls__'],
                                   req,
                                   data['__id__'])
                        errors.append(err)
        return errors

    def verify_high(self, high):
        '''
        Verify that the high data is viable and follows the data structure
        '''
        errors = []
        if not isinstance(high, dict):
            errors.append('High data is not a dictionary and is invalid')
        for name, body in high.items():
            if name.startswith('__'):
                continue
            if not isinstance(body, dict):
                err = ('The type {0} in {1} is not formated as a dictionary'
                       .format(name, body['__sls__']))
                errors.append(err)
                continue
            for state, run in body.items():
                if state.startswith('__'):
                    continue
                if not isinstance(body[state], list):
                    err = ('The state {0} in sls {1} is not formed as a list'
                           .format(name, body['__sls__']))
                    errors.append(err)
                else:
                    fun = 0
                    for arg in body[state]:
                        if isinstance(arg, str):
                            fun += 1
                        elif isinstance(arg, dict):
                            # The arg is a dict, if the arg is require or
                            # watch, it must be a list.
                            if arg.keys()[0] == 'require' \
                                    or arg.keys()[0] == 'watch':
                                if not isinstance(arg[arg.keys()[0]], list):
                                    errors.append(('The require or watch'
                                    ' statement in state {0} in sls {1} needs'
                                    ' to be formed as a list').format(
                                        name,
                                        body['__sls__']
                                        ))
                                # It is a list, verify that the members of the
                                # list are all single key dicts.
                                else:
                                    for req in arg[arg.keys()[0]]:
                                        if not isinstance(req, dict):
                                            err = ('Requisite declaration {0}'
                                            ' in SLS {1} is not formed as a'
                                            ' single key dictionary').format(
                                                req,
                                                body['__sls__'])
                                            errors.append(err)
                                # Make sure that there is only one key in the dict
                                if len(arg.keys()) != 1:
                                    errors.append(('Multiple dictionaries defined'
                                    ' in argument of state {0} in sls {1}').format(
                                        name,
                                        body['__sls__']))
                    if not fun:
                        if state == 'require' or state == 'watch':
                            continue
                        errors.append(('No function declared in state {0} in'
                            ' sls {1}').format(state, body['__sls__']))
                    elif fun > 1:
                        errors.append(('Too many functions declared in state'
                            ' {0} in sls {1}').format(state, body['__sls__']))
        return errors

    def verify_chunks(self, chunks):
        '''
        Verify the chunks in a list of low data structures
        '''
        err = []
        for chunk in chunks:
            err += self.verify_data(chunk)
        return err

    def order_chunks(self, chunks):
        '''
        Sort the chunk list verifying that the chunks follow the order
        specified in the order options.
        '''
        cap = 1
        for chunk in chunks:
            if 'order' in chunk:
                if not isinstance(chunk['order'], int):
                    continue
                if chunk['order'] > cap - 1:
                    cap = chunk['order'] + 100
        for chunk in chunks:
            if not 'order' in chunk:
                chunk['order'] = cap
            else:
                if not isinstance(chunk['order'], int):
                    if chunk['order'] == 'last':
                        chunk['order'] = cap + 100
                    else:
                        chunk['order'] = cap
        chunks = sorted(
                chunks,
                key=lambda k:'{0[state]}{0[name]}{0[fun]}'.format(k)
                )
        chunks = sorted(
                chunks,
                key=lambda k: k['order']
                )
        return chunks

    def format_call(self, data):
        '''
        Formats low data into a list of dict's used to actually call the state,
        returns:
        {
        'full': 'module.function',
        'args': [arg[0], arg[1], ...]
        }
        used to call the function like this:
        self.states[ret['full']](*ret['args'])

        It is assumed that the passed data has already been verified with
        verify_data
        '''
        ret = {}
        ret['full'] = '{0[state]}.{0[fun]}'.format(data)
        ret['args'] = []
        aspec = _getargs(self.states[ret['full']])
        arglen = 0
        deflen = 0
        if isinstance(aspec[0], list):
            arglen = len(aspec[0])
        if isinstance(aspec[3], tuple):
            deflen = len(aspec[3])
        kwargs = {}
        for ind in range(arglen - 1, 0, -1):
            minus = arglen - ind
            if deflen - minus > -1:
                kwargs[aspec[0][ind]] = aspec[3][-minus]
        for arg in kwargs:
            if arg in data:
                kwargs[arg] = data[arg]
        for arg in aspec[0]:
            if arg in kwargs:
                ret['args'].append(kwargs[arg])
            else:
                ret['args'].append(data[arg])
        return ret

    def compile_high_data(self, high):
        '''
        "Compile" the high data as it is retrieved from the cli or yaml into
        the individual state executor structures
        '''
        chunks = []
        for name, body in high.items():
            if name.startswith('__'):
                continue
            for state, run in body.items():
                if state.startswith('__'):
                    continue
                chunk = {'state': state,
                         'name': name}
                if '__sls__' in body:
                    chunk['__sls__'] = body['__sls__']
                if '__env__' in body:
                    chunk['__env__'] = body['__env__']
                chunk['__id__'] = name
                funcs = set()
                names = set()
                for arg in run:
                    if isinstance(arg, str):
                        funcs.add(arg)
                        continue
                    if isinstance(arg, dict):
                        for key, val in arg.items():
                            if key == 'names':
                                names.update(val)
                                continue
                            else:
                                chunk.update(arg)
                if names:
                    for name in names:
                        live = copy.deepcopy(chunk)
                        live['name'] = name
                        for fun in funcs:
                            live['fun'] = fun
                            chunks.append(live)
                else:
                    live = copy.deepcopy(chunk)
                    for fun in funcs:
                        live['fun'] = fun
                        chunks.append(live)
        chunks = self.order_chunks(chunks)
        return chunks

    def reconcile_extend(self, high):
        '''
        Pull the extend data and add it to the respective high data
        '''
        errors = []
        if '__extend__' not in high:
            return high, errors
        ext = high.pop('__extend__')
        for ext_chunk in ext:
            for name, body in ext_chunk.items():
                if name not in high:
                    errors.append(
                        'Extension {0} is not part of the high state'.format(
                            name
                            )
                        )
                    continue
                for state, run in body.items():
                    if state.startswith('__'):
                        continue
                    if state not in high[name]:
                        high[name][state] = run
                        continue
                    # high[name][state] is extended by run, both are lists
                    for arg in run:
                        update = False
                        for hind in range(len(high[name][state])):
                            if isinstance(arg, str) and \
                                    isinstance(high[name][state][hind], str):
                                # replacing the function, replace the index
                                high[name][state].pop(hind)
                                high[name][state].insert(hind, arg)
                                update = True
                                continue
                            if isinstance(arg, dict) and \
                                    isinstance(high[name][state][hind], dict):
                                # It is an option, make sure the options match
                                if (arg.keys()[0] ==
                                    high[name][state][hind].keys()[0]):
                                    # They match, check if the option is a
                                    # watch or require, append, otherwise
                                    # replace
                                    if arg.keys()[0] == 'require' or \
                                            arg.keys()[0] == 'watch':
                                        # Extend the list
                                        (high[name][state][hind][arg.keys()[0]]
                                         .extend(arg[arg.keys()[0]]))
                                        update = True
                                    else:
                                        # Replace the value
                                        high[name][state][hind] = arg
                                        update = True
                        if not update:
                            high[name][state].append(arg)
        return high, errors

    def template_shebang(self, template):
        '''
        Check the template shebang line and return the renderer
        '''
        # Open up the first line of the sls template
        line = open(template, 'r').readline()
        # Check if it starts with a shebang
        if line.startswith('#!'):
            # pull out the shebang data
            trend = line.strip()[2:]
            # If the specified renderer exists, use it, or fallback
            if trend in self.rend:
                return trend
        return self.opts['renderer']

    def compile_template(self, template, env='', sls=''):
        '''
        Take the path to a template and return the high data structure derived
        from the template.
        '''
        if not isinstance(template, str):
            return {}
        if not os.path.isfile(template):
            return {}
        return self.rend[self.template_shebang(template)](template, env, sls)

    def compile_template_str(self, template):
        '''
        Take the path to a template and return the high data structure derived
        from the template.
        '''
        fn_ = tempfile.mkstemp()[1]
        open(fn_, 'w+').write(template)
        high = self.rend[self.template_shebang(fn_)](fn_)
        os.remove(fn_)
        return high

    def call(self, data):
        '''
        Call a state directly with the low data structure, verify data before
        processing.
        '''
        log.info(
                'Executing state {0[state]}.{0[fun]} for {0[name]}'.format(
                    data
                    )
                )
        if 'redirect' in data:
            self.load_modules(data)
        cdata = self.format_call(data)
        ret = self.states[cdata['full']](*cdata['args'])
        ret['__run_num__'] = self.__run_num
        self.__run_num += 1
        format_log(ret)
        if 'redirect' in data:
            self.load_modules()
        return ret

    def call_chunks(self, chunks):
        '''
        Iterate over a list of chunks and call them, checking for requires.
        '''
        running = {}
        for low in chunks:
            if '__FAILHARD__' in running:
                running.pop('__FAILHARD__')
                return running
            tag = _gen_tag(low)
            if tag not in running:
                running = self.call_chunk(low, running, chunks)
                if self.check_failhard(low, running):
                    return running
        return running

    def check_failhard(self, low, running):
        '''
        Check if the low data chunk should send a failhard signal
        '''
        tag = _gen_tag(low)
        if low.get('failhard', False) \
                or self.opts['failhard'] \
                and tag in running:
            return not running[tag]['result']
        return False

    def check_requisite(self, low, running, chunks):
        '''
        Look into the running data to check the status of all requisite states
        '''
        present = False
        if 'watch' in low:
            present = True
        if 'require' in low:
            present = True
        if not present:
            return 'met'
        reqs = {'require': [],
                'watch': []}
        status = 'unmet'
        for r_state in reqs.keys():
            if r_state in low:
                for req in low[r_state]:
                    found = False
                    for chunk in chunks:
                        if fnmatch.fnmatch(chunk['__id__'], req[req.keys()[0]]) or \
                                fnmatch.fnmatch(chunk['name'], req[req.keys()[0]]):
                            if chunk['state'] == req.keys()[0]:
                                found = True
                                reqs[r_state].append(chunk)
                    if not found:
                        return 'unmet'
        fun_stats = set()
        for r_state, chunks in reqs.items():
            for chunk in chunks:
                tag = _gen_tag(chunk)
                if tag not in running:
                    fun_stats.add('unmet')
                    continue
                if not running[tag]['result']:
                    fun_stats.add('fail')
                    continue
                if r_state == 'watch' and running[tag]['changes']:
                    fun_stats.add('change')
                    continue
                else:
                    fun_stats.add('met')

        if 'unmet' in fun_stats:
            return 'unmet'
        elif 'fail' in fun_stats:
            return 'fail'
        elif 'change' in fun_stats:
            return 'change'
        return 'met'

    def call_chunk(self, low, running, chunks):
        '''
        Check if a chunk has any requires, execute the requires and then the
        chunk
        '''
        self._mod_init(low)
        tag = _gen_tag(low)
        requisites = ('require', 'watch')
        status = self.check_requisite(low, running, chunks)
        if status == 'unmet':
            lost = {'require': [],
                    'watch': []}
            reqs = []
            for requisite in requisites:
                if not requisite in low:
                    continue
                for req in low[requisite]:
                    found = False
                    for chunk in chunks:
                        if fnmatch.fnmatch(chunk['name'], req[req.keys()[0]]) \
                                or fnmatch.fnmatch(chunk['__id__'],
                                        req[req.keys()[0]]):
                            if chunk['state'] == req.keys()[0]:
                                reqs.append(chunk)
                                found = True
                    if not found:
                        lost[requisite].append(req)
            if lost['require'] or lost['watch']:
                comment = 'The following requisites were not found:\n'
                for requisite, lreqs in lost.items():
                    for lreq in lreqs:
                        comment += '{0}{1}: {2}\n'.format(' '*19,
                                requisite,
                                lreq)
                running[tag] = {'changes': {},
                                'result': False,
                                'comment': comment,
                                '__run_num__': self.__run_num}
                self.__run_num += 1
                return running
            for chunk in reqs:
                # Check to see if the chunk has been run, only run it if
                # it has not been run already
                ctag = _gen_tag(chunk)
                if ctag not in running:
                    running = self.call_chunk(chunk, running, chunks)
                    if self.check_failhard(chunk, running):
                        running['__FAILHARD__'] = True
                        return running
            running = self.call_chunk(low, running, chunks)
            if self.check_failhard(chunk, running):
                running['__FAILHARD__'] = True
                return running
        elif status == 'met':
            running[tag] = self.call(low)
        elif status == 'fail':
            running[tag] = {'changes': {},
                            'result': False,
                            'comment': 'One or more requisite failed',
                            '__run_num__': self.__run_num}
            self.__run_num += 1
        elif status == 'change':
            ret = self.call(low)
            if not ret['changes']:
                low['fun'] = 'mod_watch'
                ret = self.call(low)
            running[tag] = ret
        else:
            running[tag] = self.call(low)
        return running

    def call_high(self, high):
        '''
        Process a high data call and ensure the defined states.
        '''
        err = []
        errors = []
        # If there is extension data reconcile it
        high, ext_errors = self.reconcile_extend(high)
        errors += ext_errors
        # Verify that the high data is structurally sound
        errors += self.verify_high(high)
        if errors:
            return errors
        # Compile and verify the raw chunks
        chunks = self.compile_high_data(high)
        errors += self.verify_chunks(chunks)
        # If there are extensions in the highstate, process them and update
        # the low data chunks
        if errors:
            return errors
        ret = self.format_verbosity(self.call_chunks(chunks))
        return ret

    def call_template(self, template):
        '''
        Enforce the states in a template
        '''
        high = self.compile_template(template)
        if high:
            return self.call_high(high)
        return high

    def call_template_str(self, template):
        '''
        Enforce the states in a template, pass the template as a string
        '''
        high = self.compile_template_str(template)
        if high:
            return self.call_high(high)
        return high


class HighState(object):
    '''
    Generate and execute the salt "High State". The High State is the compound
    state derived from a group of template files stored on the salt master or
    in the local cache.
    '''
    def __init__(self, opts):
        self.client = salt.minion.FileClient(opts)
        self.opts = self.__gen_opts(opts)
        self.state = State(self.opts)
        self.matcher = salt.minion.Matcher(self.opts)

    def __gen_opts(self, opts):
        '''
        The options used by the High State object are derived from options on
        the minion and the master, or just the minion if the high state call is
        entirely local.
        '''
        # If the state is intended to be applied locally, then the local opts
        # should have all of the needed data, otherwise overwrite the local
        # data items with data from the master
        if 'local_state' in opts:
            if opts['local_state']:
                return opts
        mopts = self.client.master_opts()
        opts['renderer'] = mopts['renderer']
        opts['failhard'] = mopts.get('failhard', False)
        if mopts['state_top'].startswith('salt://'):
            opts['state_top'] = mopts['state_top']
        elif mopts['state_top'].startswith('/'):
            opts['state_top'] = os.path.join('salt://', mopts['state_top'][1:])
        else:
            opts['state_top'] = os.path.join('salt://', mopts['state_top'])
        opts['nodegroups'] = mopts.get('nodegroups', {})
        return opts

    def _get_envs(self):
        '''
        Pull the file server environments out of the master options
        '''
        envs = set(['base'])
        if 'file_roots' in self.opts:
            envs.update(self.opts['file_roots'].keys())
        return envs

    def get_tops(self):
        '''
        Gather the top files
        '''
        tops = collections.defaultdict(list)
        include = collections.defaultdict(list)
        done = collections.defaultdict(list)
        # Gather initial top files
        if self.opts['environment']:
            tops[self.opts['environment']] = [
                    self.state.compile_template(
                        self.client.cache_file(
                            self.opts['state_top'],
                            self.opts['environment']
                            ),
                        self.opts['environment']
                        )
                    ]
        else:
            for env in self._get_envs():
                tops[env].append(
                        self.state.compile_template(
                            self.client.cache_file(
                                self.opts['state_top'],
                                env
                                ),
                            env
                            )
                        )

        # Search initial top files for includes
        for env, ctops in tops.items():
            for ctop in ctops:
                if not 'include' in ctop:
                    continue
                for sls in ctop['include']:
                    include[env].append(sls)
                ctop.pop('include')
        # Go through the includes and pull out the extra tops and add them
        while include:
            pops = []
            for env, states in include.items():
                pops.append(env)
                if not states:
                    continue
                for sls in states:
                    if sls in done[env]:
                        continue
                    tops[env].append(
                            self.state.compile_template(
                                self.client.get_state(
                                    sls,
                                    env
                                    ),
                                env
                                )
                            )
                    done[env].append(sls)
            for env in pops:
                if env in include:
                    include.pop(env)

        return tops

    def merge_tops(self, tops):
        '''
        Cleanly merge the top files
        '''
        top = collections.defaultdict(dict)
        for sourceenv, ctops in tops.items():
            for ctop in ctops:
                for env, targets in ctop.items():
                    if env == 'include':
                        continue
                    for tgt in targets:
                        if not tgt in top[env]:
                            top[env][tgt] = ctop[env][tgt]
                            continue
                        matches = []
                        states = set()
                        for comp in ctop[env][tgt]:
                            if isinstance(comp, dict):
                                cmatches.append(comp)
                            if isinstance(comp, str):
                                cstates.add(comp)
                        for comp in top[env][tgt]:
                            if isinstance(comp, dict):
                                matches.append(comp)
                            if isinstance(comp, str):
                                states.add(comp)
                        top[env][tgt] = matches
                        top[env][tgt].extend(list(states))
        return top

    def get_top(self):
        '''
        Returns the high data derived from the top file
        '''
        tops = self.get_tops()
        return self.merge_tops(tops)

    def top_matches(self, top):
        '''
        Search through the top high data for matches and return the states that
        this minion needs to execute.

        Returns:
        {'env': ['state1', 'state2', ...]}
        '''
        matches = {}
        for env, body in top.items():
            if self.opts['environment']:
                if not env == self.opts['environment']:
                    continue
            for match, data in body.items():
                if self.matcher.confirm_top(
                        match,
                        data,
                        self.opts['nodegroups']
                        ):
                    if env not in matches:
                        matches[env] = []
                    for item in data:
                        if isinstance(item, basestring):
                            matches[env].append(item)
        ext_matches = self.client.ext_nodes()
        for env in ext_matches:
            if env in matches:
                matches[env] = list(set(ext_matches[env]).union(matches[env]))
            else:
                matches[env] = ext_matches[env]
        return matches

    def load_dynamic(self, matches):
        '''
        If autoload_dynamic_modules is True then automatically load the
        dynamic modules
        '''
        if not self.opts['autoload_dynamic_modules']:
            return
        syncd = self.state.functions['saltutil.sync_all'](matches.keys())
        if syncd[2]:
            self.opts['grains'] = salt.loader.grains(self.opts)
        faux = {'state': 'file', 'fun': 'recurse'}
        self.state.module_refresh(faux)

    def gather_states(self, matches):
        '''
        Gather the template files from the master
        '''
        group = []
        for env, states in matches.items():
            for sls in states:
                state = self.client.get_state(sls, env)
                if state:
                    group.append(state)
        return group

    def render_state(self, sls, env, mods):
        '''
        Render a state file and retrieve all of the include states
        '''
        err = ''
        errors = []
        fn_ = self.client.get_state(sls, env)
        if not fn_:
            errors.append(('Specifed SLS {0} in environment {1} is not'
                           ' available on the salt master').format(sls, env))
        state = None
        try:
            state = self.state.compile_template(fn_, env, sls)
        except Exception as exc:
            errors.append(('Rendering SLS {0} failed, render error:\n{1}'
                           .format(sls, exc)))
        mods.add(sls)
        nstate = None
        if state:
            if not isinstance(state, dict):
                errors.append(('SLS {0} does not render to a dictionary'
                               .format(sls)))
            else:
                if 'include' in state:
                    if not isinstance(state['include'], list):
                        err = ('Include Declaration in SLS {0} is not formed '
                               'as a list'.format(sls))
                        errors.append(err)
                    else:
                        for sub_sls in state.pop('include'):
                            if sub_sls not in mods:
                                nstate, mods, err = self.render_state(
                                        sub_sls,
                                        env,
                                        mods
                                        )
                            if nstate:
                                state.update(nstate)
                            if err:
                                errors += err
                if 'extend' in state:
                    ext = state.pop('extend')
                    for name in ext:
                        if not isinstance(ext[name], dict):
                            errors.append(('Extension name {0} in sls {1} is '
                                           'not a dictionary'
                                           .format(name, sls)))
                            continue
                        if '__sls__' not in ext[name]:
                            ext[name]['__sls__'] = sls
                        if '__env__' not in ext[name]:
                            ext[name]['__env__'] = env
                        if '__extend__' not in state:
                            state['__extend__'] = [ext]
                        else:
                            state['__extend__'].append(ext)
                for name in state:
                    if not isinstance(state[name], dict):
                        if name == '__extend__':
                            continue
                        errors.append(('Name {0} in sls {1} is not a dictionary'
                                       .format(name, sls)))
                        continue
                    if '__sls__' not in state[name]:
                        state[name]['__sls__'] = sls
                    if '__env__' not in state[name]:
                        state[name]['__env__'] = env
        return state, mods, errors

    def render_highstate(self, matches):
        '''
        Gather the state files and render them into a single unified salt high
        data structure.
        '''
        highstate = {}
        errors = []
        for env, states in matches.items():
            mods = set()
            for sls in states:
                state, mods, err = self.render_state(sls, env, mods)
                for id_ in state:
                    if id_ in highstate:
                        if highstate[id_] != state[id_]:
                            errors.append(('Detected conflicting IDs, SLS IDs'
                            ' need to be globally unique.\n    The'
                            ' conflicting ID is "{0}" and is found in SLS'
                            ' "{1}" and SLS "{2}"').format(
                                    id_,
                                    highstate[id_]['__sls__'],
                                    state[id_]['__sls__'])
                            )
                if state:
                    highstate.update(state)
                if err:
                    errors += err
        return highstate, errors

    def call_highstate(self):
        '''
        Run the sequence to execute the salt highstate for this minion
        '''
        top = self.get_top()
        matches = self.top_matches(top)
        self.load_dynamic(matches)
        high, errors = self.render_highstate(matches)
        if errors:
            return errors
        if not high:
            return {'no_|-states_|-states_|-None': {
                        'result': False,
                        'comment': 'No states found for this minion',
                        'name': 'No States',
                        'changes': {}
                        }
                   }
        return self.state.call_high(high)

    def compile_highstate(self):
        '''
        Return just the highstate or the errors
        '''
        top = self.get_top()
        matches = self.top_matches(top)
        high, errors = self.render_highstate(matches)

        if errors:
            return errors

        return high

    def compile_low_chunks(self):
        '''
        Compile the highstate but don't run it, return the low chunks to see
        exactly what the highstate will execute
        '''
        err = []
        top = self.get_top()
        matches = self.top_matches(top)
        high, errors = self.render_highstate(matches)

        # If there is extension data reconcile it
        high, ext_errors = self.state.reconcile_extend(high)
        errors += ext_errors

        # Verify that the high data is structurally sound
        errors += self.state.verify_high(high)

        # Compile and verify the raw chunks
        chunks = self.state.compile_high_data(high)
        errors += self.state.verify_chunks(chunks)

        if errors:
            return errors
        return chunks
