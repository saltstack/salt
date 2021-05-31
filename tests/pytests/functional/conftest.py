import logging
import shutil

import attr
import pytest
import salt.features
import salt.loader
import salt.pillar

log = logging.getLogger(__name__)


class Loaders:
    def __init__(self, opts):
        self.opts = opts
        self.context = {}
        self._reset_state_funcs = [self.context.clear]
        self._grains = self._utils = self._modules = self._pillar = None
        self._serializers = self._states = None
        self.opts["grains"] = self.grains
        self.refresh_pillar()
        salt.features.setup_features(self.opts)

    def reset_state(self):
        for func in self._reset_state_funcs:
            func()

    @property
    def grains(self):
        if self._grains is None:
            self._grains = salt.loader.grains(self.opts, context=self.context)
        return self._grains

    @property
    def utils(self):
        if self._utils is None:
            self._utils = salt.loader.utils(self.opts, context=self.context)
        return self._utils

    @property
    def modules(self):
        if self._modules is None:
            self._modules = salt.loader.minion_mods(
                self.opts, context=self.context, utils=self.utils, initial_load=True
            )
        return self._modules

    @property
    def serializers(self):
        if self._serializers is None:
            self._serializers = salt.loader.serializers(self.opts)
        return self._serializers

    @property
    def states(self):
        if self._states is None:
            _states = salt.loader.states(
                self.opts,
                functions=self.modules,
                utils=self.utils,
                serializers=self.serializers,
                context=self.context,
            )
            # For state execution modules, because we'd have to almost copy/paste what salt.modules.state.single
            # does, we actually "proxy" the call through salt.modules.state.single instead of calling the state
            # execution modules directly. This was also how the non pytest test suite worked
            # Let's load all modules now
            _states._load_all()
            # for funcname in list(_states):
            #    _states[funcname]

            # Now, we proxy loaded modules through salt.modules.state.single
            for module_name in list(_states.loaded_modules):
                for func_name in list(_states.loaded_modules[module_name]):
                    full_func_name = "{}.{}".format(module_name, func_name)
                    replacement_function = StateFunction(
                        self.modules.state.single, full_func_name
                    )
                    _states._dict[full_func_name] = replacement_function
                    _states.loaded_modules[module_name][
                        func_name
                    ] = replacement_function
                    setattr(
                        _states.loaded_modules[module_name],
                        func_name,
                        replacement_function,
                    )
            self._states = _states
        return self._states

    @property
    def pillar(self):
        if self._pillar is None:
            self._pillar = salt.pillar.get_pillar(
                self.opts,
                self.opts["grains"],
                self.opts["id"],
                saltenv=self.opts["saltenv"],
                pillarenv=self.opts.get("pillarenv"),
            ).compile_pillar()
        return self._pillar

    def refresh_pillar(self):
        self._pillar = None
        self.opts["pillar"] = self.pillar


@attr.s
class StateResult:
    raw = attr.ib()
    state_id = attr.ib(init=False)
    full_return = attr.ib(init=False)
    filtered = attr.ib(init=False)

    @state_id.default
    def _state_id(self):
        return next(iter(self.raw.keys()))

    @full_return.default
    def _full_return(self):
        return self.raw[self.state_id]

    @filtered.default
    def _filtered_default(self):
        _filtered = {}
        for key, value in self.full_return.items():
            if key.startswith("_") or key in ("duration", "start_time"):
                continue
            _filtered[key] = value
        return _filtered

    @property
    def name(self):
        return self.full_return["name"]

    @property
    def result(self):
        return self.full_return["result"]

    @property
    def changes(self):
        return self.full_return["changes"]

    @property
    def comment(self):
        return self.full_return["comment"]

    def __eq__(self, value):
        raise RuntimeError(
            "Please assert comparissons with {}.filtered instead".format(
                self.__class__.__name__
            )
        )

    def __contains__(self, value):
        raise RuntimeError(
            "Please assert comparissons with {}.filtered instead".format(
                self.__class__.__name__
            )
        )

    def __bool__(self):
        raise RuntimeError(
            "Please assert comparissons with {}.filtered instead".format(
                self.__class__.__name__
            )
        )


@attr.s
class StateFunction:
    proxy_func = attr.ib(repr=False)
    state_func = attr.ib()

    def __call__(self, *args, **kwargs):
        name = None
        if args and len(args) == 1:
            name = args[0]
        if name is not None and "name" in kwargs:
            raise RuntimeError(
                "Either pass 'name' as the single argument to the call or remove 'name' as a keyword argument"
            )
        if name is None:
            name = kwargs.pop("name", None)
        if name is None:
            raise RuntimeError(
                "'name' was not passed as the single argument to the function nor as a keyword argument"
            )
        log.info("Calling state.single(%s, name=%s, %s)", self.state_func, name, kwargs)
        result = self.proxy_func(self.state_func, name=name, **kwargs)
        return StateResult(result)


@pytest.fixture(scope="package")
def minion_id():
    return "func-tests-minion"


@pytest.fixture(scope="module")
def state_tree(tmp_path_factory):
    state_tree_path = tmp_path_factory.mktemp("state-tree-base")
    try:
        yield state_tree_path
    finally:
        shutil.rmtree(str(state_tree_path), ignore_errors=True)


@pytest.fixture(scope="module")
def state_tree_prod(tmp_path_factory):
    state_tree_path = tmp_path_factory.mktemp("state-tree-prod")
    try:
        yield state_tree_path
    finally:
        shutil.rmtree(str(state_tree_path), ignore_errors=True)


@pytest.fixture(scope="module")
def minion_opts(
    salt_factories, minion_id, state_tree, state_tree_prod,
):
    config_overrides = {
        "file_client": "local",
        "file_roots": {"base": [str(state_tree)], "prod": [str(state_tree_prod)]},
        "features": {"enable_slsvars_fixes": True},
    }
    factory = salt_factories.salt_minion_daemon(minion_id, overrides=config_overrides,)
    return factory.config.copy()


@pytest.fixture(scope="module")
def loaders(minion_opts):
    return Loaders(minion_opts)


@pytest.fixture(autouse=True)
def reset_loaders_state(loaders):
    try:
        # Run the tests
        yield
    finally:
        # Reset the loaders state
        loaders.reset_state()
