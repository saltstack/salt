# -*- coding: utf-8 -*-
'''
:maintainer: Evan Borgstrom <evan@borgstrom.ca>

Pythonic object interface to creating state data, see the pyobjects renderer
for more documentation.
'''
import inspect
import logging

from collections import namedtuple

from salt.utils.odict import OrderedDict

REQUISITES = ('require', 'watch', 'use', 'require_in', 'watch_in', 'use_in')

log = logging.getLogger(__name__)


class StateException(Exception):
    pass


class DuplicateState(StateException):
    pass


class InvalidFunction(StateException):
    pass


class Registry(object):
    '''
    The StateRegistry holds all of the states that have been created.
    '''
    states = OrderedDict()
    requisites = []
    includes = []
    extends = OrderedDict()
    enabled = True

    @classmethod
    def empty(cls):
        cls.states = OrderedDict()
        cls.requisites = []
        cls.includes = []
        cls.extends = OrderedDict()

    @classmethod
    def include(cls, *args):
        if not cls.enabled:
            return

        cls.includes += args

    @classmethod
    def salt_data(cls):
        states = OrderedDict([
            (id_, states_)
            for id_, states_ in cls.states.iteritems()
        ])

        if cls.includes:
            states['include'] = cls.includes

        if cls.extends:
            states['extend'] = OrderedDict([
                (id_, states_)
                for id_, states_ in cls.extends.iteritems()
            ])

        cls.empty()

        return states

    @classmethod
    def add(cls, id_, state, extend=False):
        if not cls.enabled:
            return

        if extend:
            attr = cls.extends
        else:
            attr = cls.states

        if id_ in attr:
            if state.full_func in attr[id_]:
                raise DuplicateState(
                    "A state with id '{0!r}', type '{1!r}' exists".format(
                        id_,
                        state.full_func
                    )
                )
        else:
            attr[id_] = OrderedDict()

        # if we have requisites in our stack then add them to the state
        if len(cls.requisites) > 0:
            for req in cls.requisites:
                if req.requisite not in state.kwargs:
                    state.kwargs[req.requisite] = []
                state.kwargs[req.requisite].append(req())

        attr[id_].update(state())

    @classmethod
    def extend(cls, id_, state):
        cls.add(id_, state, extend=True)

    @classmethod
    def make_extend(cls, name):
        return StateExtend(name)

    @classmethod
    def push_requisite(cls, requisite):
        if not cls.enabled:
            return

        cls.requisites.append(requisite)

    @classmethod
    def pop_requisite(cls):
        if not cls.enabled:
            return

        del cls.requisites[-1]


class StateExtend(object):
    def __init__(self, name):
        self.name = name


class StateRequisite(object):
    def __init__(self, requisite, module, id_):
        self.requisite = requisite
        self.module = module
        self.id_ = id_

    def __call__(self):
        return {self.module: self.id_}

    def __enter__(self):
        Registry.push_requisite(self)

    def __exit__(self, type, value, traceback):
        Registry.pop_requisite()


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
    def __init__(self, module, valid_funcs=None):
        self.module = module
        if valid_funcs is None:
            valid_funcs = []
        self.valid_funcs = valid_funcs

    def __getattr__(self, func):
        if len(self.valid_funcs) > 0 and func not in self.valid_funcs:
            raise InvalidFunction('The function {0!r} does not exist in the '
                                  'StateFactory for {1!r}'.format(
                                      func,
                                      self.module
                                  ))

        def make_state(id_, **kwargs):
            return State(
                id_,
                self.module,
                func,
                **kwargs
            )
        return make_state

    def __call__(self, id_, requisite='require'):
        '''
        When an object is called it is being used as a requisite
        '''
        # return the correct data structure for the requisite
        return StateRequisite(requisite, self.module, id_)


class State(object):
    '''
    This represents a single item in the state tree

    The id_ is the id of the state, the func is the full name of the salt
    state (ie. file.managed). All the keyword args you pass in become the
    properties of your state.
    '''

    def __init__(self, id_, module, func, **kwargs):
        self.id_ = id_
        self.module = module
        self.func = func
        self.kwargs = kwargs

        if isinstance(self.id_, StateExtend):
            Registry.extend(self.id_.name, self)
            self.id_ = self.id_.name
        else:
            Registry.add(self.id_, self)

        self.requisite = StateRequisite('require', self.module, self.id_)

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
        return "{0!s}.{1!s}".format(self.module, self.func)

    def __str__(self):
        return "{0!s} = {1!s}:{2!s}".format(self.id_, self.full_func, self.attrs)

    def __call__(self):
        return {
            self.full_func: self.attrs
        }

    def __enter__(self):
        Registry.push_requisite(self.requisite)

    def __exit__(self, type, value, traceback):
        Registry.pop_requisite()


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
        for mod in _mods.keys():
            mod_name = '{0}Module'.format(str(mod).capitalize())
            mod_object = namedtuple(mod_name, _mods[mod].keys())

            self.mods[mod] = mod_object(**_mods[mod])

    def __getattr__(self, mod):
        if mod not in self.mods:
            raise AttributeError

        return self.mods[mod]


class MapMeta(type):
    '''
    This is the metaclass for our Map class, used for building data maps based
    off of grain data.
    '''
    def __init__(cls, name, bases, nmspc):
        cls.__set_attributes__()
        super(MapMeta, cls).__init__(name, bases, nmspc)

    def __set_attributes__(cls):
        match_groups = OrderedDict([])

        # find all of our filters
        for item in cls.__dict__:
            if item[0] == '_':
                continue

            filt = cls.__dict__[item]

            # only process classes
            if not inspect.isclass(filt):
                continue

            # which grain are we filtering on
            grain = getattr(filt, '__grain__', 'os_family')
            if grain not in match_groups:
                match_groups[grain] = OrderedDict([])

            # does the object pointed to have a __match__ attribute?
            # if so use it, otherwise use the name of the object
            # this is so that you can match complex values, which the python
            # class name syntax does not allow
            if hasattr(filt, '__match__'):
                match = filt.__match__
            else:
                match = item

            match_groups[grain][match] = OrderedDict([])
            for name in filt.__dict__:
                if name[0] == '_':
                    continue

                match_groups[grain][match][name] = filt.__dict__[name]

        attrs = {}
        for grain in match_groups:
            filtered = Map.__salt__['grains.filter_by'](match_groups[grain],
                                                        grain=grain)
            if filtered:
                attrs.update(filtered)

        if hasattr(cls, 'merge'):
            pillar = Map.__salt__['pillar.get'](cls.merge)
            if pillar:
                attrs.update(pillar)

        for name in attrs:
            setattr(cls, name, attrs[name])


def need_salt(*a, **k):
    log.error("Map needs __salt__ set before it can be used!")
    return {}


class Map(object):
    __metaclass__ = MapMeta
    __salt__ = {
        'grains.filter_by': need_salt,
        'pillar.get': need_salt
    }
