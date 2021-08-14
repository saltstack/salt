"""
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

"""

# Implementation note:
#  - There's a bit of terminology mix-up here:
#    - what I called a state or state declaration here is actually
#      an ID declaration.
#    - what I called a module or a state module actually corresponds
#      to a state declaration.
#    - and a state function is a function declaration.


# TODOs:
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


from uuid import uuid4 as _uuid

from salt.state import HighState
from salt.utils.odict import OrderedDict

REQUISITES = set(
    "listen require watch prereq use listen_in require_in watch_in prereq_in use_in"
    " onchanges onfail".split()
)


class PyDslError(Exception):
    pass


class Options(dict):
    def __getattr__(self, name):
        return self.get(name)


SLS_MATCHES = None


class Sls:
    def __init__(self, sls, saltenv, rendered_sls):
        self.name = sls
        self.saltenv = saltenv
        self.includes = []
        self.included_highstate = HighState.get_active().building_highstate
        self.extends = []
        self.decls = []
        self.options = Options()
        self.funcs = []  # track the ordering of state func declarations
        self.rendered_sls = rendered_sls  # a set of names of rendered sls modules

        if not HighState.get_active():
            raise PyDslError("PyDSL only works with a running high state!")

    @classmethod
    def get_all_decls(cls):
        return HighState.get_active()._pydsl_all_decls

    @classmethod
    def get_render_stack(cls):
        return HighState.get_active()._pydsl_render_stack

    def set(self, **options):
        self.options.update(options)

    def include(self, *sls_names, **kws):
        if "env" in kws:
            # "env" is not supported; Use "saltenv".
            kws.pop("env")

        saltenv = kws.get("saltenv", self.saltenv)

        if kws.get("delayed", False):
            for incl in sls_names:
                self.includes.append((saltenv, incl))
            return

        HIGHSTATE = HighState.get_active()

        global SLS_MATCHES
        if SLS_MATCHES is None:
            SLS_MATCHES = HIGHSTATE.top_matches(HIGHSTATE.get_top())

        highstate = self.included_highstate
        slsmods = []  # a list of pydsl sls modules rendered.
        for sls in sls_names:
            r_env = "{}:{}".format(saltenv, sls)
            if r_env not in self.rendered_sls:
                self.rendered_sls.add(
                    sls
                )  # needed in case the starting sls uses the pydsl renderer.
                histates, errors = HIGHSTATE.render_state(
                    sls, saltenv, self.rendered_sls, SLS_MATCHES
                )
                HIGHSTATE.merge_included_states(highstate, histates, errors)
                if errors:
                    raise PyDslError("\n".join(errors))
                HIGHSTATE.clean_duplicate_extends(highstate)

            state_id = "_slsmod_{}".format(sls)
            if state_id not in highstate:
                slsmods.append(None)
            else:
                for arg in highstate[state_id]["stateconf"]:
                    if isinstance(arg, dict) and next(iter(arg)) == "slsmod":
                        slsmods.append(arg["slsmod"])
                        break

        if not slsmods:
            return None
        return slsmods[0] if len(slsmods) == 1 else slsmods

    def extend(self, *state_funcs):
        if self.options.ordered or self.last_func():
            raise PyDslError("Cannot extend() after the ordered option was turned on!")
        for f in state_funcs:
            state_id = f.mod._state_id
            self.extends.append(self.get_all_decls().pop(state_id))
            i = len(self.decls)
            for decl in reversed(self.decls):
                i -= 1
                if decl._id == state_id:
                    del self.decls[i]
                    break

    def state(self, id=None):
        if not id:
            id = ".{}".format(_uuid())
            # adds a leading dot to make use of stateconf's namespace feature.
        try:
            return self.get_all_decls()[id]
        except KeyError:
            self.get_all_decls()[id] = s = StateDeclaration(id)
            self.decls.append(s)
            return s

    def last_func(self):
        return self.funcs[-1] if self.funcs else None

    def track_func(self, statefunc):
        self.funcs.append(statefunc)

    def to_highstate(self, slsmod):
        # generate a state that uses the stateconf.set state, which
        # is a no-op state, to hold a reference to the sls module
        # containing the DSL statements. This is to prevent the module
        # from being GC'ed, so that objects defined in it will be
        # available while salt is executing the states.
        slsmod_id = "_slsmod_" + self.name
        self.state(slsmod_id).stateconf.set(slsmod=slsmod)
        del self.get_all_decls()[slsmod_id]

        highstate = OrderedDict()
        if self.includes:
            highstate["include"] = [{t[0]: t[1]} for t in self.includes]
        if self.extends:
            highstate["extend"] = extend = OrderedDict()
            for ext in self.extends:
                extend[ext._id] = ext._repr(context="extend")
        for decl in self.decls:
            highstate[decl._id] = decl._repr()

        if self.included_highstate:
            errors = []
            HighState.get_active().merge_included_states(
                highstate, self.included_highstate, errors
            )
            if errors:
                raise PyDslError("\n".join(errors))
        return highstate

    def load_highstate(self, highstate):
        for sid, decl in highstate.items():
            s = self.state(sid)
            for modname, args in decl.items():
                if "." in modname:
                    modname, funcname = modname.rsplit(".", 1)
                else:
                    funcname = next(x for x in args if isinstance(x, str))
                    args.remove(funcname)
                mod = getattr(s, modname)
                named_args = {}
                for x in args:
                    if isinstance(x, dict):
                        k, v = next(iter(x.items()))
                        named_args[k] = v
                mod(funcname, **named_args)


class StateDeclaration:
    def __init__(self, id):
        self._id = id
        self._mods = []

    def __getattr__(self, name):
        for m in self._mods:
            if m._name == name:
                return m
        m = StateModule(name, self._id)
        self._mods.append(m)
        return m

    __getitem__ = __getattr__

    def __str__(self):
        return self._id

    def __iter__(self):
        return iter(self._mods)

    def _repr(self, context=None):
        return OrderedDict(m._repr(context) for m in self)

    def __call__(self, check=True):
        sls = Sls.get_render_stack()[-1]
        if self._id in sls.get_all_decls():
            last_func = sls.last_func()
            if last_func and self._mods[-1]._func is not last_func:
                raise PyDslError(
                    "Cannot run state({}: {}) that is required by a runtime "
                    "state({}: {}), at compile time.".format(
                        self._mods[-1]._name,
                        self._id,
                        last_func.mod,
                        last_func.mod._state_id,
                    )
                )
            sls.get_all_decls().pop(self._id)
            sls.decls.remove(self)
            self._mods[0]._func._remove_auto_require()
            for m in self._mods:
                try:
                    sls.funcs.remove(m._func)
                except ValueError:
                    pass

        result = HighState.get_active().state.functions["state.high"](
            {self._id: self._repr()}
        )

        if not isinstance(result, dict):
            # A list is an error
            raise PyDslError(
                "An error occurred while running highstate: {}".format(
                    "; ".join(result)
                )
            )

        result = sorted(result.items(), key=lambda t: t[1]["__run_num__"])
        if check:
            for k, v in result:
                if not v["result"]:
                    import pprint

                    raise PyDslError(
                        "Failed executing low state at compile time:\n{}".format(
                            pprint.pformat({k: v})
                        )
                    )
        return result


class StateModule:
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
                            "Multiple state functions({}) not allowed in a "
                            "state module({})!".format(name, self._name)
                        )
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
        for mod_ref in kws.items():
            self.reference(t, *mod_ref)
        return self

    return req


class StateFunction:
    def __init__(self, name, parent_mod):
        self.mod = parent_mod
        self.name = name
        self.args = []

        # track the position of the auto-added require for easy
        # removal if run at compile time.
        self.require_index = None

        sls = Sls.get_render_stack()[-1]
        if sls.options.ordered:
            last_f = sls.last_func()
            if last_f:
                self.require(last_f.mod)
                self.require_index = len(self.args) - 1
            sls.track_func(self)

    def _remove_auto_require(self):
        if self.require_index is not None:
            del self.args[self.require_index]
            self.require_index = None

    def __call__(self, *args, **kws):
        self.configure(args, kws)
        return self

    def _repr(self, context=None):
        if not self.name and context != "extend":
            raise PyDslError(
                "No state function specified for module: {}".format(self.mod._name)
            )
        if not self.name and context == "extend":
            return self.args
        return [self.name] + self.args

    def configure(self, args, kws):
        args = list(args)
        if args:
            first = args[0]
            if (
                self.mod._name == "cmd"
                and self.name in ("call", "wait_call")
                and callable(first)
            ):

                args[0] = first.__name__
                kws = dict(func=first, args=args[1:], kws=kws)
                del args[1:]

            args[0] = dict(name=args[0])

        for k, v in kws.items():
            args.append({k: v})

        self.args.extend(args)
        return self

    def reference(self, req_type, mod, ref):
        if isinstance(mod, StateModule):
            ref = mod._state_id
        elif not (mod and ref):
            raise PyDslError(
                "Invalid a requisite reference declaration! {}: {}".format(mod, ref)
            )
        self.args.append({req_type: [{str(mod): str(ref)}]})

    ns = locals()
    for req_type in REQUISITES:
        ns[req_type] = _generate_requsite_method(req_type)
    del ns
    del req_type
