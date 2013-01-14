import weakref
from uuid import uuid4 as _uuid

try:
    from collections import OrderedDict
    Dict = OrderedDict
except ImportError:
    Dict = dict

def sls(sls):
    return Sls(sls)

class Sls(object):

    # tracks all state declarations globally across sls files
    all_decls = weakref.WeakValueDictionary()

    def __init__(self, sls):
        self.name = sls
        self.includes = []
        self.extends = []
        self.decls = []

    def include(self, *sls_names):
        self.includes.extend(sls_names)

    def extend(self, *states):
        for s in states:
            self.extends.append(self.all_decls.pop(s._id))
        
    def state(self, id=None):
        if not id:
            id = '.'+str(_uuid()) 
            # adds a leading dot to make use of stateconf's namespace feature.
        try:
            return self.all_decls[id]
        except KeyError:
            self.all_decls[id] = s = StateDeclaration(id)
            self.decls.append(s)
            return s

    def to_highstate(self, slsmod):
        # generate a state that uses the stateconf.set state, which
        # is a no-op state, to hold a reference to the sls module
        # containing the DSL statements. This is to prevent the module
        # from being GC'ed, so that objects defined in it will be
        # available while salt is executing the states.
        self.state().stateconf.set(slsmod=slsmod)

        highstate = Dict()
        if self.includes:
            highstate['include'] = self.includes[:]
        if self.extends:
            highstate['extend'] = extend = Dict()
        for ext in self.extends:
            extend[ext._id] = ext
        for decl in self.decls:
            highstate[decl._id] = decl._repr()
        return highstate


class StateDeclaration(object):

    def __init__(self, id=None):
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

    def _repr(self):
        return dict(m._repr() for m in self)


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
                return getattr(self._func, name)
        self._func = f = StateFunction(name, self._name)
        return f

    def __call__(self, name, *args, **kws):
        return getattr(self, name).configure(args, kws)

    def __str__(self):
        return self._name

    def _repr(self):
        return (self._name, [self._func.name]+self._func.args)



def _generate_requsite_method(t):
    def req(self, mod, ref=None):
        self.reference(t, mod, ref)
        return self
    return req

class StateFunction(object):
    
    def __init__(self, name, parent_mod):
        self.mod_name = parent_mod
        self.name = name
        self.args = []

    def __call__(self, *args, **kws):
        self.configure(args, kws)
        return self

    def configure(self, args, kws):
        args = list(args)
        if args:
            first = args[0]
            if self.mod_name == 'cmd' and self.name == 'call' and callable(first):
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
            raise ValueError("Invalid argument(s) to a requisite expression!")
        self.args.append({req_type: [{str(mod): str(ref)}]})
        return self

    ns = locals()
    for req_type in "require watch use require_in watch_in use_in".split():
        ns[req_type] = _generate_requsite_method(req_type)
    del ns
    del req_type

