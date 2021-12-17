"""
Functions to interact with the pillar compiler on the master
"""

import logging

import salt.pillar
import salt.utils.minions

log = logging.getLogger(__name__)


def show_top(minion=None, saltenv="base"):
    """
    Returns the compiled top data for pillar for a specific minion.  If no
    minion is specified, we use the first minion we find.

    CLI Example:

    .. code-block:: bash

        salt-run pillar.show_top
    """
    id_, grains, _ = salt.utils.minions.get_minion_data(minion, __opts__)
    pillar = salt.pillar.Pillar(__opts__, grains, id_, saltenv)

    top, errors = pillar.get_top()

    if errors:
        __jid_event__.fire_event({"data": errors, "outputter": "nested"}, "progress")
        return errors

    return top


def show_pillar(minion="*", **kwargs):
    """
    Returns the compiled pillar either of a specific minion
    or just the global available pillars. This function assumes
    that no minion has the id ``*``.
    Function also accepts pillarenv as attribute in order to limit to a specific pillar branch of git

    CLI Example:

    shows minion specific pillar:

    .. code-block:: bash

        salt-run pillar.show_pillar 'www.example.com'

    shows global pillar:

    .. code-block:: bash

        salt-run pillar.show_pillar

    shows global pillar for 'dev' pillar environment:
    (note that not specifying pillarenv will merge all pillar environments
    using the master config option pillar_source_merging_strategy.)

    .. code-block:: bash

        salt-run pillar.show_pillar 'pillarenv=dev'

    shows global pillar for 'dev' pillar environment and specific pillarenv = dev:

    .. code-block:: bash

        salt-run pillar.show_pillar 'saltenv=dev' 'pillarenv=dev'

    API Example:

    .. code-block:: python

        import salt.config
        import salt.runner
        opts = salt.config.master_config('/etc/salt/master')
        runner = salt.runner.RunnerClient(opts)
        pillar = runner.cmd('pillar.show_pillar', [])
        print(pillar)
    """
    pillarenv = None
    saltenv = "base"
    id_, grains, _ = salt.utils.minions.get_minion_data(minion, __opts__)
    if grains is None:
        grains = {"fqdn": minion}

    for key in kwargs:
        if key == "saltenv":
            saltenv = kwargs[key]
        elif key == "pillarenv":
            # pillarenv overridden on CLI
            pillarenv = kwargs[key]
        else:
            grains[key] = kwargs[key]

    pillar = salt.pillar.Pillar(__opts__, grains, id_, saltenv, pillarenv=pillarenv)

    compiled_pillar = pillar.compile_pillar()
    return compiled_pillar


def clear_pillar_cache(minion="*", **kwargs):
    """
    Clears the cached values when using pillar_cache

    .. versionadded:: 3003

    CLI Example:

    Clears the pillar cache for a specific minion:

    .. code-block:: bash

        salt-run pillar.clear_pillar_cache 'minion'

    """

    if not __opts__.get("pillar_cache"):
        log.info("The pillar_cache is set to False or not enabled.")
        return False

    ckminions = salt.utils.minions.CkMinions(__opts__)
    ret = ckminions.check_minions(minion)

    pillarenv = kwargs.pop("pillarenv", None)
    saltenv = kwargs.pop("saltenv", "base")

    pillar_cache = {}
    for tgt in ret.get("minions", []):
        id_, grains, _ = salt.utils.minions.get_minion_data(tgt, __opts__)

        for key in kwargs:
            grains[key] = kwargs[key]

        if grains is None:
            grains = {"fqdn": minion}

        pillar = salt.pillar.PillarCache(
            __opts__, grains, id_, saltenv, pillarenv=pillarenv
        )
        pillar.clear_pillar()

        if __opts__.get("pillar_cache_backend") == "memory":
            _pillar_cache = pillar.cache
        else:
            _pillar_cache = pillar.cache._dict

        if tgt in _pillar_cache and _pillar_cache[tgt]:
            pillar_cache[tgt] = _pillar_cache.get(tgt).get(pillarenv)

    return pillar_cache


def show_pillar_cache(minion="*", **kwargs):
    """
    Shows the cached values in pillar_cache

    .. versionadded:: 3003

    CLI Example:

    Shows the pillar cache for a specific minion:

    .. code-block:: bash

        salt-run pillar.show_pillar_cache 'minion'

    """

    if not __opts__.get("pillar_cache"):
        log.info("The pillar_cache is set to False or not enabled.")
        return False

    ckminions = salt.utils.minions.CkMinions(__opts__)
    ret = ckminions.check_minions(minion)

    pillarenv = kwargs.pop("pillarenv", None)
    saltenv = kwargs.pop("saltenv", "base")

    pillar_cache = {}
    for tgt in ret.get("minions", []):
        id_, grains, _ = salt.utils.minions.get_minion_data(tgt, __opts__)

        for key in kwargs:
            grains[key] = kwargs[key]

        if grains is None:
            grains = {"fqdn": minion}

        pillar = salt.pillar.PillarCache(
            __opts__, grains, id_, saltenv, pillarenv=pillarenv
        )

        if __opts__.get("pillar_cache_backend") == "memory":
            _pillar_cache = pillar.cache
        else:
            _pillar_cache = pillar.cache._dict

        if tgt in _pillar_cache and _pillar_cache[tgt]:
            pillar_cache[tgt] = _pillar_cache[tgt].get(pillarenv)

    return pillar_cache
