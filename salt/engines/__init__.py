"""
Initialize the engines system. This plugin system allows for
complex services to be encapsulated within the salt plugin environment
"""
import logging

import salt
import salt.loader
import salt.utils.platform
import salt.utils.process

log = logging.getLogger(__name__)


def start_engines(opts, proc_mgr, proxy=None):
    """
    Fire up the configured engines!
    """
    utils = salt.loader.utils(opts, proxy=proxy)
    if opts["__role"] == "master":
        runners = salt.loader.runner(opts, utils=utils)
    else:
        runners = []
    funcs = salt.loader.minion_mods(opts, utils=utils, proxy=proxy)
    engines = salt.loader.engines(opts, funcs, runners, utils, proxy=proxy)

    engines_opt = opts.get("engines", [])
    if isinstance(engines_opt, dict):
        engines_opt = [{k: v} for k, v in engines_opt.items()]

    # Function references are not picklable. Windows needs to pickle when
    # spawning processes. On Windows, these will need to be recalculated
    # in the spawned child process.
    if salt.utils.platform.is_windows():
        runners = None
        utils = None
        funcs = None

    for engine in engines_opt:
        if isinstance(engine, dict):
            engine, engine_opts = next(iter(engine.items()))
        else:
            engine_opts = None
        engine_name = None
        if engine_opts is not None and "engine_module" in engine_opts:
            fun = "{}.start".format(engine_opts["engine_module"])
            engine_name = engine
            del engine_opts["engine_module"]
        else:
            fun = "{}.start".format(engine)
        if fun in engines:
            start_func = engines[fun]
            if engine_name:
                name = "{}.Engine({}-{})".format(
                    __name__, start_func.__module__, engine_name
                )
            else:
                name = "{}.Engine({})".format(__name__, start_func.__module__)
            log.info("Starting Engine %s", name)
            proc_mgr.add_process(
                Engine,
                args=(name, opts, fun, engine_opts, funcs, runners, proxy),
                name=name,
            )


class Engine(salt.utils.process.SignalHandlingProcess):
    """
    Execute the given engine in a new process
    """

    def __init__(self, name, opts, fun, config, funcs, runners, proxy, **kwargs):
        """
        Set up the process executor
        """
        super().__init__(**kwargs)
        self.name = name
        self.opts = opts
        self.config = config
        self.fun = fun
        self.funcs = funcs
        self.runners = runners
        self.proxy = proxy

    def run(self):
        """
        Run the master service!
        """
        salt.utils.process.appendproctitle(self.name)
        self.utils = salt.loader.utils(self.opts, proxy=self.proxy)
        if salt.utils.platform.is_windows():
            # Calculate function references since they can't be pickled.
            if self.opts["__role"] == "master":
                self.runners = salt.loader.runner(self.opts, utils=self.utils)
            else:
                self.runners = []
            self.funcs = salt.loader.minion_mods(
                self.opts, utils=self.utils, proxy=self.proxy
            )

        self.engine = salt.loader.engines(
            self.opts, self.funcs, self.runners, self.utils, proxy=self.proxy
        )
        kwargs = self.config or {}
        try:
            self.engine[self.fun](**kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            log.critical(
                "Engine '%s' could not be started!",
                self.fun.split(".")[0],
                exc_info=True,
            )
