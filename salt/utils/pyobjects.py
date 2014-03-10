# -*- coding: utf-8 -*-
'''
:maintainer: Evan Borgstrom <evan@borgstrom.ca>

Pythonic object interface to creating state data, see the pyobjects renderer
for more documentation.
'''
from collections import namedtuple

from salt.utils.odict import OrderedDict

REQUISITES = ('require', 'watch', 'use', 'require_in', 'watch_in', 'use_in')


class StateException(Exception):
    pass


class DuplicateState(StateException):
    pass


class InvalidFunction(StateException):
    pass


class StateRegistry(object):
    '''
    The StateRegistry holds all of the states that have been created.
    '''
    def __init__(self):
        self.empty()

    def empty(self):
        self.states = OrderedDict()
        self.requisites = []
        self.includes = []
        self.extends = OrderedDict()

    def include(self, *args):
        self.includes += args

    def salt_data(self):
        states = OrderedDict([
            (id_, states_)
            for id_, states_ in self.states.iteritems()
        ])

        if self.includes:
            states['include'] = self.includes

        if self.extends:
            states['extend'] = OrderedDict([
                (id_, states_)
                for id_, states_ in self.extends.iteritems()
            ])

        self.empty()

        return states

    def add(self, id_, state, extend=False):
        if extend:
            attr = self.extends
        else:
            attr = self.states

        if id_ in attr:
            if state.full_func in attr[id_]:
                raise DuplicateState("A state with id '%s', type '%s' exists" % (
                    id_,
                    state.full_func
                ))
        else:
            attr[id_] = OrderedDict()

        # if we have requisites in our stack then add them to the state
        if len(self.requisites) > 0:
            for req in self.requisites:
                if req.requisite not in state.kwargs:
                    state.kwargs[req.requisite] = []
                state.kwargs[req.requisite].append(req())

        attr[id_].update(state())

    def extend(self, id_, state):
        self.add(id_, state, extend=True)

    def make_extend(self, name):
        return StateExtend(name)

    def push_requisite(self, requisite):
        self.requisites.append(requisite)

    def pop_requisite(self):
        del self.requisites[-1]


class StateExtend(object):
    def __init__(self, name):
        self.name = name


class StateRequisite(object):
    def __init__(self, requisite, module, id_, registry):
        self.requisite = requisite
        self.module = module
        self.id_ = id_
        self.registry = registry

    def __call__(self):
        return {self.module: self.id_}

    def __enter__(self):
        self.registry.push_requisite(self)

    def __exit__(self, type, value, traceback):
        self.registry.pop_requisite()


class StateFactory(object):
    '''
    The StateFactory is used to generate new States through a natural syntax

    It is used by initializing it with the name of the salt module::

        File = StateFactory("file")

    Any attribute accessed on the instance returned by StateFactory is a lambda
    that is a short cut for generating State objects::

        File.managed('/path/', owner='root', group='root')

    The kwargs are passed through to the State object
    '''
    def __init__(self, module, registry, valid_funcs=None):
        self.module = module
        self.registry = registry
        if valid_funcs is None:
            valid_funcs = []
        self.valid_funcs = valid_funcs

    def __getattr__(self, func):
        if len(self.valid_funcs) > 0 and func not in self.valid_funcs:
            raise InvalidFunction("The function '%s' does not exist in the "
                                  "StateFactory for '%s'" % (func, self.module))

        def make_state(id_, **kwargs):
            return State(
                id_,
                self.module,
                func,
                registry=self.registry,
                **kwargs
            )
        return make_state

    def __call__(self, id_, requisite='require'):
        '''
        When an object is called it is being used as a requisite
        '''
        # return the correct data structure for the requisite
        return StateRequisite(requisite, self.module, id_,
                              registry=self.registry)


class State(object):
    '''
    This represents a single item in the state tree

    The id_ is the id of the state, the func is the full name of the salt
    state (ie. file.managed). All the keyword args you pass in become the
    properties of your state.

    The registry is where the state should be stored. It is optional and will
    use the default registry if not specified.
    '''

    def __init__(self, id_, module, func, registry, **kwargs):
        self.id_ = id_
        self.module = module
        self.func = func
        self.kwargs = kwargs
        self.registry = registry

        if isinstance(self.id_, StateExtend):
            self.registry.extend(self.id_.name, self)
            self.id_ = self.id_.name
        else:
            self.registry.add(self.id_, self)

        self.requisite = StateRequisite('require', self.module, self.id_,
                                        registry=self.registry)

    @property
    def attrs(self):
        kwargs = self.kwargs

        # handle our requisites
        for attr in REQUISITES:
            if attr in kwargs:
                # our requisites should all be lists, but when you only have a
                # single item it's more convenient to provide it without
                # wrapping it in a list. transform them into a list
                if not isinstance(kwargs[attr], list):
                    kwargs[attr] = [kwargs[attr]]

                # rebuild the requisite list transforming any of the actual
                # StateRequisite objects into their representative dict
                kwargs[attr] = [
                    req() if isinstance(req, StateRequisite) else req
                    for req in kwargs[attr]
                ]

        # build our attrs from kwargs. we sort the kwargs by key so that we
        # have consistent ordering for tests
        return [
            {k: kwargs[k]}
            for k in sorted(kwargs.iterkeys())
        ]

    @property
    def full_func(self):
        return "%s.%s" % (self.module, self.func)

    def __str__(self):
        return "%s = %s:%s" % (self.id_, self.full_func, self.attrs)

    def __call__(self):
        return {
            self.full_func: self.attrs
        }

    def __enter__(self):
        self.registry.push_requisite(self.requisite)

    def __exit__(self, type, value, traceback):
        self.registry.pop_requisite()


class SaltObject(object):
    '''
    Object based interface to the functions in __salt__

    .. code-block:: python
       :linenos:
        Salt = SaltObject(__salt__)
        Salt.cmd.run(bar)
    '''
    def __init__(self, salt):
        _mods = {}
        for full_func in salt:
            mod, func = full_func.split('.')

            if mod not in _mods:
                _mods[mod] = {}
            _mods[mod][func] = salt[full_func]

        # now transform using namedtuples
        self.mods = {}
        for mod in _mods:
            mod_object = namedtuple('%sModule' % mod.capitalize(),
                                    _mods[mod].keys())

            self.mods[mod] = mod_object(**_mods[mod])

    def __getattr__(self, mod):
        if mod not in self.mods:
            raise AttributeError

        return self.mods[mod]
