'''
The module used to execute states in salt. A state is unlike a module
execution in that instead of just executing a command it ensure that a
certain state is present on the system.

The data sent to the state calls is as follows:
    { 'state': '<state module name>',
      'fun': '<state function name>',
      'name': '<the name argument passed to all states>'
      'argn': '<arbitrary argument, can have many of these>'
      }
'''

# Import python libs
import os
import copy
import inspect
import fnmatch
import logging
import collections
import traceback

# Import salt libs
import salt.utils
import salt.loader
import salt.minion
import salt.pillar
import salt.fileclient
import salt.utils.event
from salt._compat import string_types, callable
from salt.template import compile_template, compile_template_str
from salt.exceptions import SaltReqTimeoutError, SaltException

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
        del aspec.args[0]  # self
    else:
        raise TypeError('Cannot inspect argument list for "{0}"'.format(func))

    return aspec


def trim_req(req):
    '''
    Trim any function off of a requisite
    '''
    reqfirst = next(iter(req))
    if '.' in reqfirst:
        return {reqfirst.split('.')[0]: req[reqfirst]}
    return req


def state_args(id_, state, high):
    '''
    Return a set of the arguments passed to the named state
    '''
    args = set()
    if id_ not in high:
        return args
    if state not in high[id_]:
        return args
    for item in high[id_][state]:
        if not isinstance(item, dict):
            continue
        if len(item) != 1:
            continue
        args.add(next(iter(item)))
    return args


def find_name(name, state, high):
    '''
    Scan high data for the id referencing the given name
    '''
    ext_id = ''
    if name in high:
        ext_id = name
    else:
        # We need to scan for the name
        for nid in high:
            if state in high[nid]:
                if isinstance(
                        high[nid][state],
                        list):
                    for arg in high[nid][state]:
                        if not isinstance(arg, dict):
                            continue
                        if len(arg) != 1:
                            continue
                        if arg[next(iter(arg))] == name:
                            ext_id = nid
    return ext_id


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
                    if isinstance(chg['diff'], string_types):
                        msg = 'File changed:\n{0}'.format(chg['diff'])
                if all([isinstance(x, dict) for x in chg.values()]):
                    if all([('old' in x and 'new' in x)
                            for x in chg.values()]):
                        # This is the return data from a package install
                        msg = 'Installed Packages:\n'
                        for pkg in chg:
                            old = chg[pkg]['old'] or 'absent'
                            new = chg[pkg]['new'] or 'absent'
                            msg += '{0} changed from {1} to ' \
                                   '{2}\n'.format(pkg, old, new)
            if not msg:
                msg = str(ret['changes'])
            if ret['result'] is True or ret['result'] is None:
                log.info(msg)
            else:
                log.error(msg)
    else:
        # catch unhandled data
        log.info(str(ret))


def master_compile(master_opts, minion_opts, grains, id_, env):
    '''
    Compile the master side low state data, and build the hidden state file
    '''
    st_ = MasterHighState(master_opts, minion_opts, grains, id_, env)
    return st_.compile_highstate()


def ishashable(obj):
    try:
        hash(obj)
    except TypeError:
        return False
    return True


class StateError(Exception):
    '''
    Custom exception class.
    '''
    pass


class Compiler(object):
    '''
    Class used to compile and manage the High Data structure
    '''
    def __init__(self, opts):
        self.opts = opts
        self.rend = salt.loader.render(self.opts, {})

    def render_template(self, template, **kwargs):
        '''
        Enforce the states in a template
        '''
        high = compile_template(
            template, self.rend, self.opts['renderer'], **kwargs)
        if not high:
            return high
        return self.pad_funcs(high)

    def pad_funcs(self, high):
        '''
        Turns dot delimited function refs into function strings
        '''
        for name in high:
            if not isinstance(high[name], dict):
                if isinstance(high[name], string_types):
                    # Is this is a short state? It needs to be padded!
                    if '.' in high[name]:
                        comps = high[name].split('.')
                        if len(comps) >= 2:
                            # Merge the comps
                            comps[1] = '.'.join(comps[1:len(comps)])
                        high[name] = {
                            #'__sls__': template,
                            #'__env__': None,
                            comps[0]: [comps[1]]
                        }
                        continue
                    continue
            skeys = set()
            for key in sorted(high[name]):
                if key.startswith('_'):
                    continue
                if not isinstance(high[name][key], list):
                    continue
                if '.' in key:
                    comps = key.split('.')
                    if len(comps) >= 2:
                        # Merge the comps
                        comps[1] = '.'.join(comps[1:len(comps)])
                    # Salt doesn't support state files such as:
                    #
                    # /etc/redis/redis.conf:
                    #   file.managed:
                    #     - user: redis
                    #     - group: redis
                    #     - mode: 644
                    #   file.comment:
                    #     - regex: ^requirepass
                    if comps[0] in skeys:
                        continue
                    high[name][comps[0]] = high[name].pop(key)
                    high[name][comps[0]].append(comps[1])
                    skeys.add(comps[0])
                    continue
                skeys.add(key)
        return high

    def verify_high(self, high):
        '''
        Verify that the high data is viable and follows the data structure
        '''
        errors = []
        if not isinstance(high, dict):
            errors.append('High data is not a dictionary and is invalid')
        reqs = {}
        for name, body in high.items():
            if name.startswith('__'):
                continue
            if not isinstance(name, string_types):
                err = ('The name {0} in sls {1} is not formed as a '
                       'string but is a {2}').format(
                               name, body['__sls__'], type(name))
                errors.append(err)
            if not isinstance(body, dict):
                err = ('The type {0} in {1} is not formated as a dictionary'
                       .format(name, body))
                errors.append(err)
                continue
            for state in body:
                if state.startswith('__'):
                    continue
                if not isinstance(body[state], list):
                    err = ('The state "{0}" in sls {1} is not formed as a list'
                           .format(name, body['__sls__']))
                    errors.append(err)
                else:
                    fun = 0
                    if '.' in state:
                        fun += 1
                    for arg in body[state]:
                        if isinstance(arg, string_types):
                            fun += 1
                            if ' ' in arg.strip():
                                errors.append(('The function "{0}" in state '
                                '"{1}" in SLS "{2}" has '
                                'whitespace, a function with whitespace is '
                                'not supported, perhaps this is an argument '
                                'that is missing a ":"').format(
                                    arg,
                                    name,
                                    body['__sls__']))
                        elif isinstance(arg, dict):
                            # The arg is a dict, if the arg is require or
                            # watch, it must be a list.
                            #
                            # Add the requires to the reqs dict and check them
                            # all for recursive requisites.
                            argfirst = next(iter(arg))
                            if argfirst == 'require' or argfirst == 'watch':
                                if not isinstance(arg[argfirst], list):
                                    errors.append(('The require or watch'
                                    ' statement in state "{0}" in sls "{1}" '
                                    'needs to be formed as a list').format(
                                        name,
                                        body['__sls__']
                                        ))
                                # It is a list, verify that the members of the
                                # list are all single key dicts.
                                else:
                                    reqs[name] = {'state': state}
                                    for req in arg[argfirst]:
                                        if not isinstance(req, dict):
                                            err = ('Requisite declaration {0}'
                                            ' in SLS {1} is not formed as a'
                                            ' single key dictionary').format(
                                                req,
                                                body['__sls__'])
                                            errors.append(err)
                                            continue
                                        req_key = next(iter(req))
                                        req_val = req[req_key]
                                        if not ishashable(req_val):
                                            errors.append((
                                                'Illegal requisite "{0}", '
                                                'is SLS {1}\n'
                                                ).format(
                                                    str(req_val),
                                                    body['__sls__']))
                                            continue

                                        # Check for global recursive requisites
                                        reqs[name][req_val] = req_key
                                        # I am going beyond 80 chars on
                                        # purpose, this is just too much
                                        # of a pain to deal with otherwise
                                        if req_val in reqs:
                                            if name in reqs[req_val]:
                                                if reqs[req_val][name] == state:
                                                    if reqs[req_val]['state'] == reqs[name][req_val]:
                                                        err = ('A recursive '
                                                        'requisite was found, SLS '
                                                        '"{0}" ID "{1}" ID "{2}"'
                                                        ).format(
                                                                body['__sls__'],
                                                                name,
                                                                req_val
                                                                )
                                                        errors.append(err)
                                # Make sure that there is only one key in the
                                # dict
                                if len(list(arg)) != 1:
                                    errors.append(('Multiple dictionaries '
                                    'defined in argument of state "{0}" in sls'
                                    ' {1}').format(
                                        name,
                                        body['__sls__']))
                    if not fun:
                        if state == 'require' or state == 'watch':
                            continue
                        errors.append(('No function declared in state "{0}" in'
                            ' sls {1}').format(state, body['__sls__']))
                    elif fun > 1:
                        errors.append(('Too many functions declared in state'
                            ' "{0}" in sls {1}').format(
                                state, body['__sls__']))
        return errors

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
                if chunk['order'] > cap - 1 and chunk['order'] > 0:
                    cap = chunk['order'] + 100
        for chunk in chunks:
            if 'order' not in chunk:
                chunk['order'] = cap
            else:
                if not isinstance(chunk['order'], int):
                    if chunk['order'] == 'last':
                        chunk['order'] = cap + 1000000
                    else:
                        chunk['order'] = cap
                elif isinstance(chunk['order'], int) and chunk['order'] < 0:
                    chunk['order'] = cap + 1000000 + chunk['order']
        chunks.sort(key=lambda chunk: (chunk['order'], '{0[state]}{0[name]}{0[fun]}'.format(chunk)))
        return chunks

    def compile_high_data(self, high):
        '''
        "Compile" the high data as it is retrieved from the CLI or YAML into
        the individual state executor structures
        '''
        chunks = []
        for name, body in high.items():
            if name.startswith('__'):
                continue
            for state, run in body.items():
                funcs = set()
                names = set()
                if state.startswith('__'):
                    continue
                chunk = {'state': state,
                         'name': name}
                if '__sls__' in body:
                    chunk['__sls__'] = body['__sls__']
                if '__env__' in body:
                    chunk['__env__'] = body['__env__']
                chunk['__id__'] = name
                for arg in run:
                    if isinstance(arg, string_types):
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
                    for low_name in names:
                        live = copy.deepcopy(chunk)
                        live['name'] = low_name
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

    def apply_exclude(self, high):
        '''
        Read in the __exclude__ list and remove all excluded objects from the
        high data
        '''
        if '__exclude__' not in high:
            return high
        ex_sls = set()
        ex_id = set()
        exclude = high.pop('__exclude__')
        for exc in exclude:
            if isinstance(exc, str):
                # The exclude statement is a string, assume it is an sls
                ex_sls.add(exc)
            if isinstance(exc, dict):
                # Explicitly declared exclude
                if len(exc) != 1:
                    continue
                key = exc.keys()[0]
                if key == 'sls':
                    ex_sls.add(exc['sls'])
                elif key == 'id':
                    ex_id.add(exc['id'])
        # Now the excludes have been simplified, use them
        if ex_sls:
            # There are sls excludes, find the associtaed ids
            for name, body in high.items():
                if name.startswith('__'):
                    continue
                if body.get('__sls__', '') in ex_sls:
                    ex_id.add(name)
        for id_ in ex_id:
            if id_ in high:
                high.pop(id_)
        return high


class State(object):
    '''
    Class used to execute salt states
    '''
    def __init__(self, opts, pillar=None):
        if 'grains' not in opts:
            opts['grains'] = salt.loader.grains(opts)
        self.opts = opts
        self.opts['pillar'] = self.__gather_pillar()
        if pillar and isinstance(pillar, dict):
            self.opts['pillar'].update(pillar)
        self.state_con = {}
        self.load_modules()
        self.active = set()
        self.mod_init = set()
        self.__run_num = 0

    def __gather_pillar(self):
        '''
        Whenever a state run starts, gather the pillar data fresh
        '''
        pillar = salt.pillar.get_pillar(
                self.opts,
                self.opts['grains'],
                self.opts['id']
                )
        return pillar.compile_pillar()

    def _mod_init(self, low):
        '''
        Check the module initialization function, if this is the first run
        of a state package that has a mod_init function, then execute the
        mod_init function in the state module.
        '''
        minit = '{0}.mod_init'.format(low['state'])
        if low['state'] not in self.mod_init:
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
        self.functions = salt.loader.minion_mods(self.opts, self.state_con)
        if isinstance(data, dict):
            if data.get('provider', False):
                if isinstance(data['provider'], str):
                    providers = [{data['state']: data['provider']}]
                elif isinstance(data['provider'], list):
                    providers = data['provider']
                else:
                    providers = {}
                for provider in providers:
                    for mod in provider:
                        funcs = salt.loader.raw_mod(self.opts,
                                provider[mod],
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

    def module_refresh(self):
        '''
        Refresh all the modules
        '''
        self.load_modules()
        module_refresh_path = os.path.join(
            self.opts['cachedir'],
            'module_refresh')
        with salt.utils.fopen(module_refresh_path, 'w+') as ofile:
            ofile.write('')

    def check_refresh(self, data, ret):
        '''
        Check to see if the modules for this state instance need to be updated,
        only update if the state is a file or a package and if it changed
        something. If the file function is managed check to see if the file is a
        possible module type, e.g. a python, pyx, or .so. Always refresh if the
        function is recurse, since that can lay down anything.
        '''
        if not ret['changes']:
            return
        if data['state'] == 'file':
            if data['fun'] == 'managed':
                if data['name'].endswith(
                    ('.py', '.pyx', '.pyo', '.pyc', '.so')):
                    self.module_refresh()
            elif data['fun'] == 'recurse':
                self.module_refresh()
        elif data['state'] == 'pkg':
            self.module_refresh()

    def verify_ret(self, ret):
        '''
        Verify the state return data
        '''
        if not isinstance(ret, dict):
            raise SaltException(
                    'Malformed state return, return must be a dict'
                    )
        bad = []
        for val in ['name', 'result', 'changes', 'comment']:
            if val not in ret:
                bad.append(val)
        if bad:
            raise SaltException(
                    ('The following keys were not present in the state '
                     'return: {0}'
                     ).format(','.join(bad)))

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
        if not isinstance(data['name'], string_types):
            err = ('The name {0} in sls {1} is not formed as a '
                   'string but is a {2}').format(
                           data['name'], data['__sls__'], type(data['name']))
            errors.append(err)
        if errors:
            return errors
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
                    errors.append('Missing parameter ' + aspec[0][ind]
                                + ' for state ' + full)
        # If this chunk has a recursive require, then it will cause a
        # recursive loop when executing, check for it
        reqdec = ''
        if 'require' in data:
            reqdec = 'require'
        if 'watch' in data:
            # Check to see if the service has a mod_watch function, if it does
            # not, then just require
            # to just require extend the require statement with the contents
            # of watch so that the mod_watch function is not called and the
            # requisite capability is still used
            if '{0}.mod_watch'.format(data['state']) not in self.states:
                if 'require' in data:
                    data['require'].extend(data.pop('watch'))
                else:
                    data['require'] = data.pop('watch')
                reqdec = 'require'
            else:
                reqdec = 'watch'
        if reqdec:
            for req in data[reqdec]:
                reqfirst = next(iter(req))
                if data['state'] == reqfirst:
                    if (fnmatch.fnmatch(data['name'], req[reqfirst])
                            or fnmatch.fnmatch(data['__id__'], req[reqfirst])):
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
        reqs = {}
        for name, body in high.items():
            if name.startswith('__'):
                continue
            if not isinstance(name, string_types):
                err = ('The name {0} in sls {1} is not formed as a '
                       'string but is a {2}').format(
                               name, body['__sls__'], type(name))
                errors.append(err)
            if not isinstance(body, dict):
                err = ('The type {0} in {1} is not formated as a dictionary'
                       .format(name, body))
                errors.append(err)
                continue
            for state in body:
                if state.startswith('__'):
                    continue
                if not isinstance(body[state], list):
                    err = ('The state "{0}" in sls {1} is not formed as a list'
                           .format(name, body['__sls__']))
                    errors.append(err)
                else:
                    fun = 0
                    if '.' in state:
                        fun += 1
                    for arg in body[state]:
                        if isinstance(arg, string_types):
                            fun += 1
                            if ' ' in arg.strip():
                                errors.append(('The function "{0}" in state '
                                '"{1}" in SLS "{2}" has '
                                'whitespace, a function with whitespace is '
                                'not supported, perhaps this is an argument '
                                'that is missing a ":"').format(
                                    arg,
                                    name,
                                    body['__sls__']))
                        elif isinstance(arg, dict):
                            # The arg is a dict, if the arg is require or
                            # watch, it must be a list.
                            #
                            # Add the requires to the reqs dict and check them
                            # all for recursive requisites.
                            argfirst = next(iter(arg))
                            if argfirst == 'names':
                                if not isinstance(arg[argfirst], list):
                                    errors.append(('Names statement in state '
                                    '"{0}" in sls "{1}" needs to be formed as'
                                    'a list').format(
                                        name,
                                        body['__sls__']))
                            if argfirst == 'require' or argfirst == 'watch':
                                if not isinstance(arg[argfirst], list):
                                    errors.append(('The require or watch'
                                    ' statement in state "{0}" in sls "{1}" '
                                    'needs to be formed as a list').format(
                                        name,
                                        body['__sls__']
                                        ))
                                # It is a list, verify that the members of the
                                # list are all single key dicts.
                                else:
                                    reqs[name] = {'state': state}
                                    for req in arg[argfirst]:
                                        if not isinstance(req, dict):
                                            err = ('Requisite declaration {0}'
                                            ' in SLS {1} is not formed as a'
                                            ' single key dictionary').format(
                                                req,
                                                body['__sls__'])
                                            errors.append(err)
                                            continue
                                        req_key = next(iter(req))
                                        req_val = req[req_key]
                                        if not ishashable(req_val):
                                            errors.append((
                                                'Illegal requisite "{0}", '
                                                'please check your syntax.\n'
                                                ).format(str(req_val)))
                                            continue

                                        # Check for global recursive requisites
                                        reqs[name][req_val] = req_key
                                        # I am going beyond 80 chars on
                                        # purpose, this is just too much
                                        # of a pain to deal with otherwise
                                        if req_val in reqs:
                                            if name in reqs[req_val]:
                                                if reqs[req_val][name] == state:
                                                    if reqs[req_val]['state'] == reqs[name][req_val]:
                                                        err = ('A recursive '
                                                        'requisite was found, SLS '
                                                        '"{0}" ID "{1}" ID "{2}"'
                                                        ).format(
                                                                body['__sls__'],
                                                                name,
                                                                req_val
                                                                )
                                                        errors.append(err)
                                # Make sure that there is only one key in the
                                # dict
                                if len(list(arg)) != 1:
                                    errors.append(('Multiple dictionaries '
                                    'defined in argument of state "{0}" in sls'
                                    ' {1}').format(
                                        name,
                                        body['__sls__']))
                    if not fun:
                        if state == 'require' or state == 'watch':
                            continue
                        errors.append(('No function declared in state "{0}" in'
                            ' sls {1}').format(state, body['__sls__']))
                    elif fun > 1:
                        errors.append(('Too many functions declared in state'
                            ' "{0}" in sls {1}').format(
                                state, body['__sls__']))
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
                if chunk['order'] > cap - 1 and chunk['order'] > 0:
                    cap = chunk['order'] + 100
        for chunk in chunks:
            if 'order' not in chunk:
                chunk['order'] = cap
            else:
                if not isinstance(chunk['order'], int):
                    if chunk['order'] == 'last':
                        chunk['order'] = cap + 1000000
                    else:
                        chunk['order'] = cap
                elif isinstance(chunk['order'], int) and chunk['order'] < 0:
                    chunk['order'] = cap + 1000000 + chunk['order']
        chunks.sort(key=lambda k: (k['order'], '{0[state]}{0[name]}{0[fun]}'.format(k)))
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
        if aspec[2]:
            # This state accepts kwargs
            ret['kwargs'] = {}
            for key in data:
                # Passing kwargs the conflict with args == stack trace
                if key in aspec[0]:
                    continue
                ret['kwargs'][key] = data[key]
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
        "Compile" the high data as it is retrieved from the CLI or YAML into
        the individual state executor structures
        '''
        chunks = []
        for name, body in high.items():
            if name.startswith('__'):
                continue
            for state, run in body.items():
                funcs = set()
                names = set()
                if state.startswith('__'):
                    continue
                chunk = {'state': state,
                         'name': name}
                if '__sls__' in body:
                    chunk['__sls__'] = body['__sls__']
                if '__env__' in body:
                    chunk['__env__'] = body['__env__']
                chunk['__id__'] = name
                for arg in run:
                    if isinstance(arg, string_types):
                        funcs.add(arg)
                        continue
                    if isinstance(arg, dict):
                        for key, val in arg.items():
                            if key == 'names':
                                names.update(val)
                            elif key == 'state':
                                # Don't pass down a state override
                                continue
                            elif (key == 'name' and
                                  not isinstance(val, string_types)):
                                # Invalid name, fall back to ID
                                chunk[key] = name
                            else:
                                chunk[key] = val
                if names:
                    for low_name in names:
                        live = copy.deepcopy(chunk)
                        live['name'] = low_name
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
                        'Cannot extend ID {0} in "{1}:{2}". It is not part '
                        'of the high state.'.format(
                            name,
                            body.get('__env__', 'base'),
                            body.get('__sls__', 'base'))
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
                            if (isinstance(arg, string_types) and
                            isinstance(high[name][state][hind], string_types)):
                                # replacing the function, replace the index
                                high[name][state].pop(hind)
                                high[name][state].insert(hind, arg)
                                update = True
                                continue
                            if (isinstance(arg, dict) and
                                    isinstance(high[name][state][hind], dict)):
                                # It is an option, make sure the options match
                                argfirst = next(iter(arg))
                                if (argfirst ==
                                    next(iter(high[name][state][hind]))):
                                    # They match, check if the option is a
                                    # watch or require, append, otherwise
                                    # replace
                                    if (argfirst == 'require' or
                                        argfirst == 'watch'):
                                        # Extend the list
                                        (high[name][state][hind][argfirst]
                                         .extend(arg[argfirst]))
                                        update = True
                                    else:
                                        # Replace the value
                                        high[name][state][hind] = arg
                                        update = True
                                if (argfirst == 'name' and
                                    next(iter(high[name][state][hind])) == 'names'):
                                    # If names are overwritten by name use the name
                                    high[name][state][hind] = arg
                        if not update:
                            high[name][state].append(arg)
        return high, errors

    def apply_exclude(self, high):
        '''
        Read in the __exclude__ list and remove all excluded objects from the
        high data
        '''
        if '__exclude__' not in high:
            return high
        ex_sls = set()
        ex_id = set()
        exclude = high.pop('__exclude__')
        for exc in exclude:
            if isinstance(exc, str):
                # The exclude statement is a string, assume it is an sls
                ex_sls.add(exc)
            if isinstance(exc, dict):
                # Explicitly declared exclude
                if len(exc) != 1:
                    continue
                key = exc.keys()[0]
                if key == 'sls':
                    ex_sls.add(exc['sls'])
                elif key == 'id':
                    ex_id.add(exc['id'])
        # Now the excludes have been simplified, use them
        if ex_sls:
            # There are sls excludes, find the associtaed ids
            for name, body in high.items():
                if name.startswith('__'):
                    continue
                if body.get('__sls__', '') in ex_sls:
                    ex_id.add(name)
        for id_ in ex_id:
            if id_ in high:
                high.pop(id_)
        return high

    def requisite_in(self, high):
        '''
        Extend the data reference with requisite_in arguments
        '''
        req_in = set(['require_in', 'watch_in', 'use', 'use_in'])
        req_in_all = req_in.union(set(['require', 'watch']))
        extend = {}
        for id_, body in high.items():
            if not isinstance(body, dict):
                continue
            for state, run in body.items():
                if state.startswith('__'):
                    continue
                for arg in run:
                    if isinstance(arg, dict):
                        # It is not a function, verify that the arg is a
                        # requisite in statement
                        if len(arg) < 1:
                            # Empty arg dict
                            # How did we get this far?
                            continue
                        # Split out the components
                        key = next(iter(arg))
                        if key not in req_in:
                            continue
                        rkey = key.split('_')[0]
                        items = arg[key]
                        if isinstance(items, dict):
                            # Formated as a single req_in
                            for _state, name in items.items():

                                # Not a use requisite_in
                                found = False
                                if name not in extend:
                                    extend[name] = {}
                                if _state not in extend[name]:
                                    extend[name][_state] = []
                                extend[name]['__env__'] = body['__env__']
                                extend[name]['__sls__'] = body['__sls__']
                                for ind in range(len(extend[name][_state])):
                                    if next(iter(
                                        extend[name][_state][ind])) == rkey:
                                        # Extending again
                                        extend[name][_state][ind][rkey].append(
                                                {state: id_}
                                                )
                                        found = True
                                if found:
                                    continue
                                # The rkey is not present yet, create it
                                extend[name][_state].append(
                                        {rkey: [{state: id_}]}
                                        )

                        if isinstance(items, list):
                            # Formed as a list of requisite additions
                            for ind in items:
                                if not isinstance(ind, dict):
                                    # Malformed req_in
                                    continue
                                if len(ind) < 1:
                                    continue
                                _state = next(iter(ind))
                                name = ind[_state]
                                if key == 'use_in':
                                    # Add the running states args to the
                                    # use_in states
                                    ext_id = find_name(name, _state, high)
                                    if not ext_id:
                                        continue
                                    ext_args = state_args(ext_id, _state, high)
                                    if ext_id not in extend:
                                        extend[ext_id] = {}
                                    if _state not in extend[ext_id]:
                                        extend[ext_id][_state] = []
                                    ignore_args = req_in_all.union(ext_args)
                                    for arg in high[id_][state]:
                                        if not isinstance(arg, dict):
                                            continue
                                        if len(arg) != 1:
                                            continue
                                        if next(iter(arg)) in ignore_args:
                                            continue
                                        # Don't use name or names
                                        if arg.keys()[0] == 'name':
                                            continue
                                        if arg.keys()[0] == 'names':
                                            continue
                                        extend[ext_id][_state].append(arg)
                                    continue
                                if key == 'use':
                                    # Add the use state's args to the
                                    # running state
                                    ext_id = find_name(name, _state, high)
                                    if not ext_id:
                                        continue
                                    loc_args = state_args(id_, state, high)
                                    if id_ not in extend:
                                        extend[id_] = {}
                                    if state not in extend[id_]:
                                        extend[id_][state] = []
                                    ignore_args = req_in_all.union(loc_args)
                                    for arg in high[ext_id][_state]:
                                        if not isinstance(arg, dict):
                                            continue
                                        if len(arg) != 1:
                                            continue
                                        if next(iter(arg)) in ignore_args:
                                            continue
                                        # Don't use name or names
                                        if arg.keys()[0] == 'name':
                                            continue
                                        if arg.keys()[0] == 'names':
                                            continue
                                        extend[id_][state].append(arg)
                                    continue
                                found = False
                                if name not in extend:
                                    extend[name] = {}
                                if _state not in extend[name]:
                                    extend[name][_state] = []
                                extend[name]['__env__'] = body['__env__']
                                extend[name]['__sls__'] = body['__sls__']
                                for ind in range(len(extend[name][_state])):
                                    if next(iter(
                                        extend[name][_state][ind])) == rkey:
                                        # Extending again
                                        extend[name][_state][ind][rkey].append(
                                                {state: id_}
                                                )
                                        found = True
                                if found:
                                    continue
                                # The rkey is not present yet, create it
                                extend[name][_state].append(
                                        {rkey: [{state: id_}]}
                                        )
        high['__extend__'] = []
        for key, val in extend.items():
            high['__extend__'].append({key: val})
        return self.reconcile_extend(high)

    def call(self, data):
        '''
        Call a state directly with the low data structure, verify data
        before processing.
        '''
        errors = self.verify_data(data)
        if errors:
            ret = {
                'result': False,
                'name': data['name'],
                'changes': {},
                'comment': '',
                }
            for err in errors:
                ret['comment'] += '{0}\n'.format(err)
            ret['__run_num__'] = self.__run_num
            self.__run_num += 1
            format_log(ret)
            self.check_refresh(data, ret)
            return ret

        log.info(
                'Executing state {0[state]}.{0[fun]} for {0[name]}'.format(
                    data
                    )
                )
        if 'provider' in data:
            self.load_modules(data)
        cdata = self.format_call(data)
        try:
            if 'kwargs' in cdata:
                ret = self.states[cdata['full']](
                    *cdata['args'], **cdata['kwargs'])
            else:
                ret = self.states[cdata['full']](*cdata['args'])
            self.verify_ret(ret)
        except Exception:
            trb = traceback.format_exc()
            ret = {
                'result': False,
                'name': cdata['args'][0],
                'changes': {},
                'comment': 'An exception occurred in this state: {0}'.format(
                    trb)
                }
        ret['__run_num__'] = self.__run_num
        self.__run_num += 1
        format_log(ret)
        if 'provider' in data:
            self.load_modules()
        self.check_refresh(data, ret)
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
            self.active = set()
        return running

    def check_failhard(self, low, running):
        '''
        Check if the low data chunk should send a failhard signal
        '''
        tag = _gen_tag(low)
        if (low.get('failhard', False) or self.opts['failhard']
                and tag in running):
            return not running[tag]['result']
        return False

    def check_requisite(self, low, running, chunks):
        '''
        Look into the running data to check the status of all requisite
        states
        '''
        present = False
        if 'watch' in low:
            if '{0}.mod_watch'.format(low['state']) not in self.states:
                if 'require' in low:
                    low['require'].extend(low.pop('watch'))
                else:
                    low['require'] = low.pop('watch')
            else:
                present = True
        if 'require' in low:
            present = True
        if not present:
            return 'met'
        reqs = {'require': [], 'watch': []}
        for r_state in reqs:
            if r_state in low:
                for req in low[r_state]:
                    req = trim_req(req)
                    found = False
                    for chunk in chunks:
                        req_key = next(iter(req))
                        req_val = req[req_key]
                        if (fnmatch.fnmatch(chunk['name'], req_val) or
                            fnmatch.fnmatch(chunk['__id__'], req_val)):
                            if chunk['state'] == req_key:
                                found = True
                                reqs[r_state].append(chunk)
                        elif req_key == 'sls':
                            # Allow requisite tracking of entire sls files
                            if fnmatch.fnmatch(chunk['__sls__'], req_val):
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
                if running[tag]['result'] is False:
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
        Check if a chunk has any requires, execute the requires and then
        the chunk
        '''
        self._mod_init(low)
        tag = _gen_tag(low)
        self.active.add(tag)
        requisites = ('require', 'watch')
        status = self.check_requisite(low, running, chunks)
        if status == 'unmet':
            lost = {'require': [], 'watch': []}
            reqs = []
            for requisite in requisites:
                if requisite not in low:
                    continue
                for req in low[requisite]:
                    req = trim_req(req)
                    found = False
                    for chunk in chunks:
                        req_key = next(iter(req))
                        req_val = req[req_key]
                        if (fnmatch.fnmatch(chunk['name'], req_val) or
                            fnmatch.fnmatch(chunk['__id__'], req_val)):
                            if chunk['state'] == req_key:
                                reqs.append(chunk)
                                found = True
                        elif req_key == 'sls':
                            # Allow requisite tracking of entire sls files
                            if fnmatch.fnmatch(chunk['__sls__'], req_val):
                                found = True
                                reqs.append(chunk)
                    if not found:
                        lost[requisite].append(req)
            if lost['require'] or lost['watch']:
                comment = 'The following requisites were not found:\n'
                for requisite, lreqs in lost.items():
                    for lreq in lreqs:
                        comment += '{0}{1}: {2}\n'.format(' ' * 19,
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
                    if ctag in self.active:
                        log.error('Recursive requisite found')
                        if ctag not in running:
                            running[tag] = {
                                    'changes': {},
                                    'result': False,
                                    'comment': 'Recursive requisite found',
                                    '__run_num__': self.__run_num}
                        self.__run_num += 1
                        return running
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
                low = low.copy()
                low['sfun'] = low['fun']
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
        errors = []
        # If there is extension data reconcile it
        high, ext_errors = self.reconcile_extend(high)
        errors += ext_errors
        errors += self.verify_high(high)
        if errors:
            return errors
        high, req_in_errors = self.requisite_in(high)
        errors += req_in_errors
        high = self.apply_exclude(high)
        # Verify that the high data is structurally sound
        if errors:
            return errors
        # Compile and verify the raw chunks
        chunks = self.compile_high_data(high)
        # If there are extensions in the highstate, process them and update
        # the low data chunks
        if errors:
            return errors
        ret = self.call_chunks(chunks)
        return ret

    def render_template(self, high, template):
        errors = []
        if not high:
            return high, errors

        if not isinstance(high, dict):
            errors.append(
                'Template {0} does not render to a dictionary'.format(template)
            )
            return high, errors

        invalid_items = ('include', 'exclude', 'extends')
        for item in invalid_items:
            if item in high:
                errors.append(
                    'The \'{0}\' declaration found on \'{1}\' is invalid when '
                    'rendering single templates'.format(item, template)
                )
                return high, errors

        for name in high:
            if not isinstance(high[name], dict):
                if isinstance(high[name], string_types):
                    # Is this is a short state, it needs to be padded
                    if '.' in high[name]:
                        comps = high[name].split('.')
                        high[name] = {
                            #'__sls__': template,
                            #'__env__': None,
                            comps[0]: [comps[1]]
                        }
                        continue

                    errors.append(
                        'Name {0} in template {1} is not a dictionary'.format(
                            name, template
                        )
                    )
                    continue
            skeys = set()
            for key in sorted(high[name]):
                if key.startswith('_'):
                    continue
                if not isinstance(high[name][key], list):
                    continue
                if '.' in key:
                    comps = key.split('.')
                    # Salt doesn't support state files such as:
                    #
                    # /etc/redis/redis.conf:
                    #   file.managed:
                    #     - user: redis
                    #     - group: redis
                    #     - mode: 644
                    #   file.comment:
                    #     - regex: ^requirepass
                    if comps[0] in skeys:
                        errors.append(
                            'Name \'{0}\' in template \'{1}\' contains '
                            'multiple state decs of the same type'.format(
                                name, template
                            )
                        )
                        continue
                    high[name][comps[0]] = high[name].pop(key)
                    high[name][comps[0]].append(comps[1])
                    skeys.add(comps[0])
                    continue
                skeys.add(key)

        return high, errors

    def call_template(self, template):
        '''
        Enforce the states in a template
        '''
        high = compile_template(
            template, self.rend, self.opts['renderer'])
        if not high:
            return high
        high, errors = self.render_template(high, template)
        if errors:
            return errors
        return self.call_high(high)

    def call_template_str(self, template):
        '''
        Enforce the states in a template, pass the template as a string
        '''
        high = compile_template_str(
            template, self.rend, self.opts['renderer'])
        if not high:
            return high
        high, errors = self.render_template(high, '<template-str>')
        if errors:
            return errors
        return self.call_high(high)


class BaseHighState(object):
    '''
    The BaseHighState is the foundation of running a highstate, extend it and
    add a self.state object of type State
    '''
    def __init__(self, opts):
        self.opts = self.__gen_opts(opts)
        self.avail = self.__gather_avail()
        self.serial = salt.payload.Serial(self.opts)

    def __gather_avail(self):
        '''
        Gather the lists of available sls data from the master
        '''
        avail = {}
        for env in self._get_envs():
            avail[env] = self.client.list_states(env)
        return avail

    def __gen_opts(self, opts):
        '''
        The options used by the High State object are derived from options
        on the minion and the master, or just the minion if the high state
        call is entirely local.
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
        opts['file_roots'] = mopts['file_roots']
        return opts

    def _get_envs(self):
        '''
        Pull the file server environments out of the master options
        '''
        envs = set(['base'])
        if 'file_roots' in self.opts:
            envs.update(list(self.opts['file_roots']))
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
                    compile_template(
                        self.client.cache_file(
                            self.opts['state_top'],
                            self.opts['environment']
                            ),
                        self.state.rend,
                        self.state.opts['renderer'],
                        env=self.opts['environment']
                        )
                    ]
        else:
            for env in self._get_envs():
                tops[env].append(
                        compile_template(
                            self.client.cache_file(
                                self.opts['state_top'],
                                env
                                ),
                            self.state.rend,
                            self.state.opts['renderer'],
                            env=env
                            )
                        )

        # Search initial top files for includes
        for env, ctops in tops.items():
            for ctop in ctops:
                if 'include' not in ctop:
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
                for sls_match in states:
                    for sls in fnmatch.filter(self.avail[env], sls_match):
                        if sls in done[env]:
                            continue
                        tops[env].append(
                                compile_template(
                                    self.client.get_state(
                                        sls,
                                        env
                                        ).get('dest', False),
                                    self.state.rend,
                                    self.state.opts['renderer'],
                                    env=env
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
        for ctops in tops.values():
            for ctop in ctops:
                for env, targets in ctop.items():
                    if env == 'include':
                        continue
                    for tgt in targets:
                        if tgt not in top[env]:
                            top[env][tgt] = ctop[env][tgt]
                            continue
                        matches = []
                        states = set()
                        for comp in top[env][tgt]:
                            if isinstance(comp, dict):
                                matches.append(comp)
                            if isinstance(comp, string_types):
                                states.add(comp)
                        top[env][tgt] = matches
                        top[env][tgt].extend(list(states))
        return top

    def verify_tops(self, tops):
        '''
        Verify the contents of the top file data
        '''
        errors = []
        if not isinstance(tops, dict):
            errors.append('Top data was not formed as a dict')
            # No further checks will work, bail out
            return errors
        for env, matches in tops.items():
            if env == 'include':
                continue
            if not isinstance(env, string_types):
                err = ('Environment {0} in top file is not formed as a '
                       'string').format(env)
                errors.append(err)
            if env == '':
                errors.append('Empty environment statement in top file')
            if not isinstance(matches, dict):
                err = ('The top file matches for environment {0} are not '
                       'laid out as a dict').format(env)
                errors.append(err)
            for slsmods in matches.values():
                for slsmod in slsmods:
                    if isinstance(slsmod, dict):
                        # This value is a match option
                        for val in slsmod.values():
                            if not val:
                                err = ('Improperly formatted top file matcher '
                                       'in environment {0}: {1} file'.format(
                                           slsmod,
                                           val
                                           )
                                       )
                                errors.append(err)
                    elif isinstance(slsmod, string_types):
                        # This is a sls module
                        if not slsmod:
                            err = ('Environment {0} contains an empty sls '
                                   'index').format(env)
                            errors.append(err)

        return errors

    def get_top(self):
        '''
        Returns the high data derived from the top file
        '''
        tops = self.get_tops()
        return self.merge_tops(tops)

    def top_matches(self, top):
        '''
        Search through the top high data for matches and return the states
        that this minion needs to execute.

        Returns:
        {'env': ['state1', 'state2', ...]}
        '''
        matches = {}
        for env, body in top.items():
            if self.opts['environment']:
                if env != self.opts['environment']:
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
                        if isinstance(item, string_types):
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
        syncd = self.state.functions['saltutil.sync_all'](list(matches))
        if syncd[2]:
            self.opts['grains'] = salt.loader.grains(self.opts)
        self.state.module_refresh()

    def render_state(self, sls, env, mods, matches):
        '''
        Render a state file and retrieve all of the include states
        '''
        err = ''
        errors = []
        state_data = self.client.get_state(sls, env)
        fn_ = state_data.get('dest', False)
        if not fn_:
            errors.append(('Specified SLS {0} in environment {1} is not'
                           ' available on the salt master').format(sls, env))
        state = None
        try:
            state = compile_template(
                fn_, self.state.rend, self.state.opts['renderer'], env, sls,
                rendered_sls=mods
            )
        except Exception as exc:
            msg = 'Rendering SLS {0} failed, render error: {1}'.format(
                sls, exc
            )
            log.error(
                msg,
                # Show the traceback if the debug logging level is enabled
                exc_info=log.isEnabledFor(logging.DEBUG)
            )
            errors.append('{0}\n{1}'.format(msg, traceback.format_exc()))
        mods.add(sls)
        if state:
            if not isinstance(state, dict):
                errors.append(
                    'SLS {0} does not render to a dictionary'.format(sls)
                )
            else:
                include = []
                if 'include' in state:
                    if not isinstance(state['include'], list):
                        err = ('Include Declaration in SLS {0} is not formed '
                               'as a list'.format(sls))
                        errors.append(err)
                    else:
                        include = state.pop('include')

                self._handle_extend(state, sls, env, errors)
                self._handle_exclude(state, sls, env, errors)
                self._handle_state_decls(state, sls, env, errors)

                for inc_sls in include:
                    # inc_sls may take the form of:
                    #   'sls.to.include' <- same as {<env>: 'sls.to.include'}
                    #   {<env_key>: 'sls.to.include'}
                    #   {'_xenv': 'sls.to.resolve'}
                    xenv_key = '_xenv'

                    if isinstance(inc_sls, dict):
                        env_key, inc_sls = inc_sls.popitem()
                    else:
                        env_key = env

                    if inc_sls.startswith('.'):
                        p_comps = sls.split('.')
                        if state_data.get('source', '').endswith('/init.sls'):
                            inc_sls = sls + inc_sls
                        else:
                            inc_sls = '.'.join(p_comps[:-1]) + inc_sls

                    if env_key != xenv_key:
                        # Resolve inc_sls in the specified environment
                        if env_key in matches and fnmatch.filter(self.avail[env_key], inc_sls):
                            resolved_envs = [env_key]
                        else:
                            resolved_envs = []
                    else:
                        # Resolve inc_sls in the subset of environment matches
                        resolved_envs = [
                            aenv for aenv in matches
                            if fnmatch.filter(self.avail[aenv], inc_sls)
                        ]

                    # An include must be resolved to a single environment, or
                    # the include must exist in the current environment
                    if len(resolved_envs) == 1 or env in resolved_envs:
                        if inc_sls not in mods:
                            nstate, err = self.render_state(
                                inc_sls,
                                resolved_envs[0] if len(resolved_envs) == 1 else env,
                                mods,
                                matches
                            )
                            if nstate:
                                self.merge_included_states(state, nstate, errors)
                                state.update(nstate)
                            if err:
                                errors.extend(err)
                    else:
                        msg = ''
                        if not resolved_envs:
                            msg = ('Unknown include: Specified SLS {0}: {1} is not available on the salt '
                                   'master in environment(s): {2} '
                                   ).format(env_key,
                                            inc_sls,
                                            ', '.join(matches) if env_key == xenv_key else env_key)
                        elif len(resolved_envs) > 1:
                            msg = ('Ambiguous include: Specified SLS {0}: {1} is available on the salt master '
                                   'in multiple available environments: {2}'
                                   ).format(env_key,
                                            inc_sls,
                                            ', '.join(resolved_envs))
                        log.error(msg)
                        if self.opts['failhard']:
                            errors.append(msg)
        else:
            state = {}
        return state, errors

    def _handle_state_decls(self, state, sls, env, errors):
        for name in state:
            if not isinstance(state[name], dict):
                if name == '__extend__':
                    continue
                if name == '__exclude__':
                    continue

                if isinstance(state[name], string_types):
                    # Is this is a short state, it needs to be padded
                    if '.' in state[name]:
                        comps = state[name].split('.')
                        state[name] = {'__sls__': sls,
                                       '__env__': env,
                                       comps[0]: [comps[1]]}
                        continue
                errors.append(
                    ('Name {0} in sls {1} is not a dictionary'
                    .format(name, sls)))
                continue
            skeys = set()
            for key in sorted(state[name]):
                if key.startswith('_'):
                    continue
                if not isinstance(state[name][key], list):
                    continue
                if '.' in key:
                    comps = key.split('.')
                    # Salt doesn't support state files such as:
                    #
                    #     /etc/redis/redis.conf:
                    #       file.managed:
                    #         - source: salt://redis/redis.conf
                    #         - user: redis
                    #         - group: redis
                    #         - mode: 644
                    #       file.comment:
                    #           - regex: ^requirepass
                    if comps[0] in skeys:
                        err = ('Name "{0}" in sls "{1}" contains '
                               'multiple state decs of the same type'
                              ).format(name, sls)
                        errors.append(err)
                        continue
                    state[name][comps[0]] = state[name].pop(key)
                    state[name][comps[0]].append(comps[1])
                    skeys.add(comps[0])
                    continue
                skeys.add(key)
            if '__sls__' not in state[name]:
                state[name]['__sls__'] = sls
            if '__env__' not in state[name]:
                state[name]['__env__'] = env

    def _handle_extend(self, state, sls, env, errors):
        if 'extend' in state:
            ext = state.pop('extend')
            if not isinstance(ext, dict):
                errors.append(('Extension value in sls {0} is not a '
                               'dictionary').format(sls))
                return
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
                for key in ext[name]:
                    if key.startswith('_'):
                        continue
                    if not isinstance(ext[name][key], list):
                        continue
                    if '.' in key:
                        comps = key.split('.')
                        ext[name][comps[0]] = ext[name].pop(key)
                        ext[name][comps[0]].append(comps[1])
            state.setdefault('__extend__', []).append(ext)

    def _handle_exclude(self, state, sls, env, errors):
        if 'exclude' in state:
            exc = state.pop('exclude')
            if not isinstance(exc, list):
                err = ('Exclude Declaration in SLS {0} is not formed '
                       'as a list'.format(sls))
                errors.append(err)
            state.setdefault('__exclude__', []).extend(exc)

    def render_highstate(self, matches):
        '''
        Gather the state files and render them into a single unified salt
        high data structure.
        '''
        highstate = {}
        all_errors = []
        for env, states in matches.items():
            mods = set()
            for sls_match in states:
                statefiles = fnmatch.filter(self.avail[env], sls_match)
                if not statefiles:
                    # No matching sls file was found!  Output an error
                    log.error(
                            'No matching sls found for \'{0}\' in env \'{1}\''
                            .format(sls_match, env)
                    )
                for sls in statefiles:
                    state, errors = self.render_state(sls, env, mods, matches)
                    if state:
                        self.merge_included_states(highstate, state, errors)
                    all_errors.extend(errors)

        self.clean_duplicate_extends(highstate)
        return highstate, all_errors

    def clean_duplicate_extends(self, highstate):
        if '__extend__' in highstate:
            highext = []
            for items in (ext.items() for ext in highstate['__extend__']):
                for item in items:
                    if item not in highext:
                        highext.append(item)
            highstate['__extend__'] = [{t[0]: t[1]} for t in highext]

    def merge_included_states(self, highstate, state, errors):
        # The extend members can not be treated as globally unique:
        if '__extend__' in state:
            highstate.setdefault('__extend__',
                                 []).extend(state.pop('__extend__'))
        if '__exclude__' in state:
            highstate.setdefault('__exclude__',
                                 []).extend(state.pop('__exclude__'))
        for id_ in state:
            if id_ in highstate:
                if highstate[id_] != state[id_]:
                    errors.append((
                            'Detected conflicting IDs, SLS'
                            ' IDs need to be globally unique.\n    The'
                            ' conflicting ID is "{0}" and is found in SLS'
                            ' "{1}:{2}" and SLS "{3}:{4}"').format(
                                    id_,
                                    highstate[id_]['__env__'],
                                    highstate[id_]['__sls__'],
                                    state[id_]['__env__'],
                                    state[id_]['__sls__'])
                    )
        try:
            highstate.update(state)
        except ValueError:
            errors.append(
                'Error when rendering state with contents: {0}'.format(state)
            )

    def call_highstate(self, exclude=None, cache=None, cache_name='highstate'):
        '''
        Run the sequence to execute the salt highstate for this minion
        '''
        #Check that top file exists
        tag_name = 'no_|-states_|-states_|-None'
        ret = {tag_name: {
                'result': False,
                'comment': 'No states found for this minion',
                'name': 'No States',
                'changes': {},
                '__run_num__': 0,
        }}
        cfn = os.path.join(
                self.opts['cachedir'],
                '{0}.cache.p'.format(cache_name)
        )

        if cache:
            if os.path.isfile(cfn):
                with open(cfn, 'r') as fp_:
                    high = self.serial.load(fp_)
                    return self.state.call_high(high)
        #File exists so continue
        err = []
        try:
            top = self.get_top()
        except Exception:
            trb = traceback.format_exc()
            err.append(trb)
            return err
        err += self.verify_tops(top)
        matches = self.top_matches(top)
        if not matches:
            msg = ('No Top file or external nodes data matches found')
            ret[tag_name]['comment'] = msg
            return ret
        self.load_dynamic(matches)
        high, errors = self.render_highstate(matches)
        if exclude:
            if isinstance(exclude, str):
                exclude = exclude.split(',')
            if '__exclude__' in high:
                high['__exclude__'].extend(exclude)
            else:
                high['__exclude__'] = exclude
        err += errors
        if err:
            return err
        if not high:
            return ret
        with open(cfn, 'w+') as fp_:
            try:
                self.serial.dump(high, fp_)
            except TypeError:
                # Can't serialize pydsl
                pass
        return self.state.call_high(high)

    def compile_highstate(self):
        '''
        Return just the highstate or the errors
        '''
        err = []
        top = self.get_top()
        err += self.verify_tops(top)
        matches = self.top_matches(top)
        high, errors = self.render_highstate(matches)
        err += errors

        if err:
            return err

        return high

    def compile_low_chunks(self):
        '''
        Compile the highstate but don't run it, return the low chunks to
        see exactly what the highstate will execute
        '''
        top = self.get_top()
        matches = self.top_matches(top)
        high, errors = self.render_highstate(matches)

        # If there is extension data reconcile it
        high, ext_errors = self.state.reconcile_extend(high)
        errors += ext_errors

        # Verify that the high data is structurally sound
        errors += self.state.verify_high(high)
        high, req_in_errors = self.state.requisite_in(high)
        errors += req_in_errors
        high = self.state.apply_exclude(high)

        if errors:
            return errors

        # Compile and verify the raw chunks
        chunks = self.state.compile_high_data(high)

        return chunks


class HighState(BaseHighState):
    '''
    Generate and execute the salt "High State". The High State is the
    compound state derived from a group of template files stored on the
    salt master or in the local cache.
    '''
    stack = [] # a stack of active HighState objects during a state.highstate run.

    def __init__(self, opts, pillar=None):
        self.client = salt.fileclient.get_file_client(opts)
        BaseHighState.__init__(self, opts)
        self.state = State(self.opts, pillar)
        self.matcher = salt.minion.Matcher(self.opts)

        # tracks all pydsl state declarations globally across sls files
        self._pydsl_all_decls = {}

        # a stack of current rendering Sls objects, maintained and used by the pydsl renderer.
        self._pydsl_render_stack = []

    def push_active(self):
        self.stack.append(self)

    @classmethod
    def pop_active(cls):
        cls.stack.pop()

    @classmethod
    def get_active(cls):
        try:
            return cls.stack[-1]
        except IndexError:
            return None


class MasterState(State):
    '''
    Create a State object for master side compiling
    '''
    def __init__(self, opts, minion):
        State.__init__(self, opts)

    def load_modules(self, data=None):
        '''
        Load the modules into the state
        '''
        log.info('Loading fresh modules for state activity')
        # Load a modified client interface that looks like the interface used
        # from the minion, but uses remote execution
        #
        self.functions = salt.client.FunctionWrapper(
                self.opts,
                self.opts['id']
                )
        # Load the states, but they should not be used in this class apart
        # from inspection
        self.states = salt.loader.states(self.opts, self.functions)
        self.rend = salt.loader.render(self.opts, self.functions)


class MasterHighState(BaseHighState):
    '''
    Execute highstate compilation from the master
    '''
    def __init__(self, master_opts, minion_opts, grains, id_, env=None):
        # Force the fileclient to be local
        opts = copy.deepcopy(minion_opts)
        opts['file_client'] = 'local'
        opts['file_roots'] = master_opts['master_roots']
        opts['renderer'] = master_opts['renderer']
        opts['state_top'] = master_opts['state_top']
        opts['id'] = id_
        opts['grains'] = grains
        self.client = salt.fileclient.get_file_client(opts)
        BaseHighState.__init__(self, opts)
        # Use the master state object
        self.state = MasterState(self.opts, grains)
        self.matcher = salt.minion.Matcher(self.opts)


class RemoteHighState(object):
    '''
    Manage gathering the data from the master
    '''
    def __init__(self, opts, grains):
        self.opts = opts
        self.grains = grains
        self.serial = salt.payload.Serial(self.opts)
        self.auth = salt.crypt.SAuth(opts)
        self.sreq = salt.payload.SREQ(self.opts['master_uri'])

    def compile_master(self):
        '''
        Return the state data from the master
        '''
        load = {'grains': self.grains,
                'opts': self.opts,
                'cmd': '_master_state'}
        try:
            return self.auth.crypticle.loads(self.sreq.send(
                    'aes',
                    self.auth.crypticle.dumps(load),
                    3,
                    72000))
        except SaltReqTimeoutError:
            return {}
