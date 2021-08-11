"""
Docker Proxy Minion

.. versionadded:: 2019.2.0

:depends: docker

This proxy minion is just a shim to the docker executor, which will use the
:py:func:`docker.call <salt.modules.dockermod.call>` for everything except
state runs.


To configure the proxy minion:

.. code-block:: yaml

    proxy:
      proxytype: docker
      name: festive_leakey

It is also possible to just name the proxy minion the same name as the
container, and use grains to configure the proxy minion:

.. code-block:: yaml

    proxy:
        proxytype: docker
        name: {{grains['id']}}

name

    Name of the docker container
"""

__proxyenabled__ = ["docker"]
__virtualname__ = "docker"


def __virtual__():
    if __opts__.get("proxy", {}).get("proxytype") != __virtualname__:
        return False, "Proxytype does not match: {}".format(__virtualname__)
    return True


def module_executors():
    """
    List of module executors to use for this Proxy Minion
    """
    return [
        "docker",
    ]


def init(opts):
    """
    Always initialize
    """
    __context__["initialized"] = True


def initialized():
    """
    This should always be initialized
    """
    return __context__.get("initialized", False)


def shutdown(opts):
    """
    Nothing needs to be done to shutdown
    """
    __context__["initialized"] = False
