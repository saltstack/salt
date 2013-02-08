'''
:maintainer: Jack Kuan <kjkuan@gmail.com>
:maturity: new
:platform: all

A Python DSL for generating Salt's highstate data structure.

This module is intended to be used with the `pydsl` renderer,
but can also be used on its own. Here's what you can do with
Salt PyDSL::

    # Example translated from the online salt tutorial

    apache = state('apache')
    apache.pkg.installed()
    apache.service.running() \\
                  .watch(pkg='apache',
                         file='/etc/httpd/conf/httpd.conf', 
                         user='apache')

    if __grains__['os'] == 'RedHat':
        apache.pkg.installed(name='httpd')
        apache.service.running(name='httpd')

    apache.group.present(gid=87).require(apache.pkg)
    apache.user.present(uid=87, gid=87,
                        home='/var/www/html',
                        shell='/bin/nologin') \\
               .require(apache.group)

    state('/etc/httpd/conf/httpd.conf').file.managed(
        source='salt://apache/httpd.conf',
        user='root',
        group='root',
        mode=644)


Example with ``include`` and ``extend``, translated from
the online salt tutorial::

    include('http', 'ssh')
    extend(
        state('apache').file(
            name='/etc/httpd/conf/httpd.conf',
            source='salt://http/httpd2.conf'
        ),
        state('ssh-server').service.watch(file='/etc/ssh/banner')
    )
    state('/etc/ssh/banner').file.managed(source='salt://ssh/banner')


Example of a ``cmd`` state calling a python function::

    def hello(s):
        s = "hello world, %s" % s
        return dict(result=True, changes=dict(changed=True, output=s))

    state('hello').cmd.call(hello, 'pydsl!')
        
'''

# Implementation note:
#  - There's a bit of terminology mix-up here: 
#    - what I called a state or state declaration here is actually
#      an ID declaration.
#    - what I called a module or a state module actually corresponds
#      to a state declaration.
#    - and a state function is a function declaration.


#TODOs:
#
#  - support exclude declarations
#
#  - allow this:
#      state('X').cmd.run.cwd = '/'
#      assert state('X').cmd.run.cwd == '/'
#
#  - make it possible to remove:
#    - state declarations
#    - state module declarations
#    - state func and args
#

import weakref
from uuid import uuid4 as _uuid

try:
    from collections import OrderedDict
    Dict = OrderedDict
except ImportError:
    Dict = dict

from salt.state import HighState

REQUISITES = set('require watch use require_in watch_in use_in'.split())
class PyDslError(Exception):
    pass

class Options(dict):
    def __getattr__(self, name):
        return self.get(name)


SLS_MATCHES = None


def sls(*args):
    return Sls(*args)

class Sls(object):

    # tracks all state declarations globally across sls files
    all_decls = weakref.WeakValueDictionary()

    # a stack of current rendering Sls objects, maintained and used by the pydsl renderer.
    render_stack = [] 

    def __init__(self, sls, mod, rendered_sls):
        self.name = sls
        self.includes = []
        self.included_highstate = {}
        self.extends = []
        self.decls = []
        self.options = Options()
        self.funcs = []  # track the ordering of state func declarations
        self.slsmod = mod  # the current rendering sls python module
        self.rendered_sls = rendered_sls # a set of names of rendered sls modules
    
    def set(self, **options):
        self.options.update(options)

    def include(self, *sls_names, **kws):
        env = kws.get('env', self.slsmod.__env__)

        if kws.get('delayed', False):
            for incl in sls_names:
                self.includes.append((env, incl))
            return

        HIGHSTATE = HighState.current
        if not HIGHSTATE:
            raise PyDslError('include() only works when running state.highstate!')

        global SLS_MATCHES
        if SLS_MATCHES is None:
            SLS_MATCHES = HIGHSTATE.top_matches(HIGHSTATE.get_top())

        highstate = self.included_highstate
        slsmods = [] # a list of pydsl sls modules rendered.
        for sls in sls_names:
            if sls not in self.rendered_sls:
                self.rendered_sls.add(sls) # needed in case the starting sls uses the pydsl renderer.
                histates, errors = HIGHSTATE.render_state(sls, env, self.rendered_sls, SLS_MATCHES)
                HIGHSTATE.merge_included_states(highstate, histates, errors)
                if errors:
                    raise PyDslError('\n'.join(errors))
                HIGHSTATE.clean_duplicate_extends(highstate)

            id = '_slsmod_'+sls
            if id not in highstate:
                slsmods.append(None)
            else:
                for arg in highstate[id]['stateconf']:
                    if isinstance(arg, dict) and iter(arg).next() == 'slsmod':
                        slsmods.append(arg['slsmod'])
                        break

        if not slsmods:
            return None
        return slsmods[0] if len(slsmods) == 1 else slsmods

    def extend(self, *state_funcs):
        if self.options.ordered and self.last_func():
            raise PyDslError('Cannot extend() while the ordered option is turned on!')
        for f in state_funcs:
            id = f.mod._state_id
            self.extends.append(self.all_decls[id])
            i = len(self.decls)
            for decl in reversed(self.decls):
                i -= 1
                if decl._id == id:
                    del self.decls[i]
                    break
            try:
                self.funcs.remove(f) # untrack it
            except ValueError:
                pass
        
    def state(self, id=None):
        if not id:
            id = '.'+str(_uuid()) 
            # adds a leading dot to make use of stateconf's namespace feature.
        try:
            return self.all_decls[id]
        except KeyError:
            self.all_decls[id] = s = StateDeclaration(id, self)
            self.decls.append(s)
            return s

    def last_func(self):
        return self.funcs[-1] if self.funcs else None

    def track_func(self, statefunc):
        self.funcs.append(statefunc)

    def to_highstate(self):
        # generate a state that uses the stateconf.set state, which
        # is a no-op state, to hold a reference to the sls module
        # containing the DSL statements. This is to prevent the module
        # from being GC'ed, so that objects defined in it will be
        # available while salt is executing the states.
        self.state('_slsmod_'+self.name).stateconf.set(slsmod=self.slsmod)

        highstate = Dict()
        if self.includes:
            highstate['include'] = [{t[0]: t[1]} for t in self.includes]
        if self.extends:
            highstate['extend'] = extend = Dict()
            for ext in self.extends:
                extend[ext._id] = ext._repr(context='extend')
        for decl in self.decls:
            highstate[decl._id] = decl._repr()


        if self.included_highstate:
            errors = []
            HighState.current.merge_included_states(highstate, self.included_highstate, errors)
            if errors:
                raise PyDslError('\n'.join(errors))
        return highstate


    def load_highstate(self, highstate):
        for sid, decl in highstate.iteritems():
            s = self.state(sid)
            for modname, args in decl.iteritems():
                if '.' in modname:
                    modname, funcname = modname.rsplit('.', 1)
                else:
                    funcname = (x for x in args if isinstance(x, basestring)).next()
                    args.remove(funcname)
                mod = getattr(s, modname)
                named_args = {}
                for x in args:
                    if isinstance(x, dict):
                        k, v = x.iteritems().next()
                        named_args[k] = v
                mod(funcname, **named_args)



class StateDeclaration(object):

    def __init__(self, id, sls):
        self._sls = sls
        self._id = id
        self._mods = []

    def __getattr__(self, name):
        for m in self._mods:
            if m._name == name:
                return m
        else:
            m = StateModule(name, self._id)
            self._mods.append(m)
            return m

    def __str__(self):
        return self._id

    def __iter__(self):
        return iter(self._mods)

    def _repr(self, context=None):
        return dict(m._repr(context) for m in self)



class StateModule(object):

    def __init__(self, name, parent_decl):
        self._state_id = parent_decl
        self._name = name
        self._func = None

    def __getattr__(self, name):
        if self._func:
            if name == self._func.name:
                return self._func
            else:
                if name not in REQUISITES:
                    if self._func.name:
                        raise PyDslError(
                            ('Multiple state functions({0}) not allowed in a '
                             'state module({1})!').format(name, self._name))
                    self._func.name = name
                    return self._func
                return getattr(self._func, name)

        if name in REQUISITES:
            self._func = f = StateFunction(None, self)
            return getattr(f, name)
        else:
            self._func = f = StateFunction(name, self)
            return f

    def __call__(self, _fname, *args, **kws):
        return getattr(self, _fname).configure(args, kws)

    def __str__(self):
        return self._name

    def _repr(self, context=None):
        return (self._name, self._func._repr(context))



def _generate_requsite_method(t):
    def req(self, *args, **kws):
        for mod in args:
            self.reference(t, mod, None)
        for mod_ref in kws.iteritems():
            self.reference(t, *mod_ref)
        return self
    return req

class StateFunction(object):
    
    def __init__(self, name, parent_mod):
        self.mod = parent_mod
        self.name = name
        self.args = []

        sls = Sls.all_decls[parent_mod._state_id]._sls
        if sls.options.ordered:
            last_f = sls.last_func()
            if last_f:
                self.require(last_f.mod)
            sls.track_func(self)

    def __call__(self, *args, **kws):
        self.configure(args, kws)
        return self

    def _repr(self, context=None):
        if not self.name and context != 'extend':
            raise PyDslError('No state function specified for module: '
                             '{0}'.format(self.mod._name))
        if not self.name and context == 'extend':
            return self.args
        return [self.name]+self.args

    def configure(self, args, kws):
        args = list(args)
        if args:
            first = args[0]
            if self.mod._name == 'cmd' and \
               self.name in ('call', 'wait_call') and \
               callable(first):

                args[0] = first.__name__
                kws = dict(func=first, args=args[1:], kws=kws)
                del args[1:]

            args[0] = dict(name=args[0])

        for k, v in kws.iteritems():
            args.append({k: v})

        self.args.extend(args)
        return self

    def reference(self, req_type, mod, ref):
        if isinstance(mod, StateModule):
            ref = mod._state_id
        elif not (mod and ref):
            raise PyDslError(
                    'Invalid a requisite reference declaration! {0}: {1}'.format(
                    mod, ref))
        self.args.append({req_type: [{str(mod): str(ref)}]})

    ns = locals()
    for req_type in REQUISITES:
        ns[req_type] = _generate_requsite_method(req_type)
    del ns
    del req_type


