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
            self.extends.append(self.all_decls.pop(state.id))
        
    def state(self, id=None):
        if not id:
            id = str(_uuid())
        try:
            return self.all_decls[id]
        except KeyError:
            self.all_decls[id] = s = StateDeclaration(id)
            self.decls.append(s)
            return s

    def to_highstate(self):
        highstate = Dict()
        highstate['include'] = self.includes[:]
        highstate['extend'] = extend = Dict()
        for ext in self.extends:
            extend[ext.id] = ext
        for decl in self.decls:
            highstate[decl.id] = decl._repr()
        return highstate


class StateDeclaration(object):

    def __init__(self, id=None):
        self.id = id
        self.mods = []

    def __getattr__(self, name):
        for m in self.mods:
            if m.name == name:
                return m
        else:
            m = StateModule(name, self.id)
            self.mods.append(m)
            return m

    def __str__(self):
        return self.id

    def __iter__(self):
        return iter(self.mods)

    def _repr(self):
        return dict(m._repr() for m in self)


class StateModule(object):

    def __init__(self, name, parent_decl):
        self.state_id = parent_decl
        self.name = name
        self.func = None

    def __getattr__(self, name):
        if self.func:
            if name == self.func.name:
                return self.func
            else:
                return getattr(self.func, name)
        self.func = f = StateFunction(name)
        return f

    def __call__(self, name, *args, **kws):
        return getattr(self, name).configure(args, kws)

    def __str__(self):
        return self.name

    def _repr(self):
        return (self.name, [self.func.name]+self.func.args)



def _generate_requsite_method(t):
    def req(self, ref, mod=None):
        self.reference(t, ref, mod)
        return self
    return req

class StateFunction(object):
    
    def __init__(self, name):
        self.name = name
        self.args = []

    def __call__(self, *args, **kws):
        self.configure(args, kws)
        return self

    def configure(self, args, kws):
        args = list(args)
        if args:
            args[0] = dict(name=args[0])
        for k, v in kws.iteritems():
            args.append({k: v})
        self.args.extend(args)
        return self

    def reference(self, req_type, ref, mod):
        if isinstance(ref, StateModule):
            mod = ref.name
            ref = ref.state_id
        elif ref and mod:
            ref = str(ref)
            mod = str(mod)
        self.args.append({req_type: [{mod: ref}]})
        return self

    ns = locals()
    for req_type in "require watch use require_in watch_in use_in".split():
        ns[req_type] = _generate_requsite_method(req_type)
    del ns
    del req_type

