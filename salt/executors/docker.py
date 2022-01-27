"""
Docker executor module

.. versionadded:: 2019.2.0

Used with the docker proxy minion.
"""

__virtualname__ = "docker"

DOCKER_MOD_MAP = {
    "state.sls": "docker.sls",
    "state.apply": "docker.apply",
    "state.highstate": "docker.highstate",
}


def __virtual__():
    if "proxy" not in __opts__:
        return (
            False,
            "Docker executor is only meant to be used with Docker Proxy Minions",
        )
    if __opts__.get("proxy", {}).get("proxytype") != __virtualname__:
        return False, "Proxytype does not match: {}".format(__virtualname__)
    return True


def execute(opts, data, func, args, kwargs):
    """
    Directly calls the given function with arguments
    """
    if data["fun"] == "saltutil.find_job":
        return __executors__["direct_call.execute"](opts, data, func, args, kwargs)
    if data["fun"] in DOCKER_MOD_MAP:
        return __executors__["direct_call.execute"](
            opts,
            data,
            __salt__[DOCKER_MOD_MAP[data["fun"]]],
            [opts["proxy"]["name"]] + args,
            kwargs,
        )
    return __salt__["docker.call"](opts["proxy"]["name"], data["fun"], *args, **kwargs)


def allow_missing_func(function):  # pylint: disable=unused-argument
    """
    Allow all calls to be passed through to docker container.

    The docker call will use direct_call, which will return back if the module
    was unable to be run.
    """
    return True
