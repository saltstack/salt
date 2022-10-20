"""
Yaml helper module for troubleshooting yaml


.. versionadded:: 3005

:depends:   yamllint >= 1.20.0


"""

import logging

import salt.utils.versions

log = logging.getLogger(__name__)

__virtualname__ = "yaml"


try:
    import salt.utils.yamllint

    HAS_LINT = True
except ImportError:
    HAS_LINT = False


def __virtual__():

    if HAS_LINT:
        if salt.utils.yamllint.has_yamllint():
            version = salt.utils.yamllint.version()
            version_cmp = salt.utils.versions.version_cmp(version, "1.20.0")
        else:
            return (False, "yamllint not installed")
        if version_cmp >= 0:
            return __virtualname__
        else:
            return (False, "yamllint below 1.20.0, please pip install a newer version")
    else:
        return (False, "yamllint not installed")


def lint(source, saltenv=None, pre_render=None, **kwargs):
    """
    lint the output after detecting a sucsessful render.

    :param str source: managed source file

    :param str saltenv: the saltenv to use, defaults
        to minions enviroment or base if not set

    :param str pre_render: The render options passed to
        slsutil.renderer other wise file is cached and loaded as stream

    CLI Example:

    .. code-block:: bash

        salt '*' yaml.lint salt://example/bad_yaml.sls
    """
    if saltenv is None:
        saltenv = __salt__["config.get"]("saltenv", "base")
        if saltenv is None:
            saltenv = "base"
    if pre_render is None:
        cache = __salt__["cp.cache_file"](source, saltenv)
        if cache is False:
            return (False, "Template was unable to be cached")
        with __utils__["files.fopen"](cache, "r") as yaml_stream:
            yaml_out = yaml_stream.read(-1)
    else:
        kwargs.update({"saltenv": saltenv})
        yaml_out = __salt__["slsutil.renderer"](
            path=source, default_renderer=pre_render, **kwargs
        )
    return salt.utils.yamllint.lint(yaml_out)
