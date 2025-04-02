"""
Jinja loading utils to enable a more powerful backend for jinja templates

.. include:: ../../../_incl/jinja_security.rst
"""

import logging
from io import StringIO

import salt.utils.templates
from salt.exceptions import SaltRenderError
from salt.loader.context import NamedLoaderContext

log = logging.getLogger(__name__)


def _split_module_dicts():
    """
    Create a copy of __salt__ dictionary with module.function and module[function]

    Takes advantage of Jinja's syntactic sugar lookup:

    .. code-block::

        {{ salt.cmd.run('uptime') }}
    """
    funcs = __salt__
    if isinstance(__salt__, NamedLoaderContext) and isinstance(__salt__.value(), dict):
        funcs = __salt__.value()
    if not isinstance(funcs, dict):
        return funcs
    mod_dict = dict(funcs)
    for module_func_name, mod_fun in mod_dict.copy().items():
        mod, fun = module_func_name.split(".", 1)
        if mod not in mod_dict:
            # create an empty object that we can add attributes to
            mod_dict[mod] = lambda: None
        setattr(mod_dict[mod], fun, mod_fun)
    return mod_dict


def render(
    template_file,
    saltenv="base",
    sls="",
    argline="",
    context=None,
    tmplpath=None,
    **kws,
):
    """
    Render the template_file, passing the functions and grains into the
    Jinja rendering system.

    :rtype: string
    """
    from_str = argline == "-s"
    if not from_str and argline:
        raise SaltRenderError(f"Unknown renderer option: {argline}")

    tmp_data = salt.utils.templates.JINJA(
        template_file,
        to_str=True,
        salt=_split_module_dicts(),
        grains=__grains__,
        opts=__opts__,
        pillar=__pillar__,
        saltenv=saltenv,
        sls=sls,
        context=context,
        tmplpath=tmplpath,
        proxy=__proxy__,
        from_str=from_str,
        **kws,
    )
    if not tmp_data.get("result", False):
        raise SaltRenderError(
            tmp_data.get("data", "Unknown render error in jinja renderer")
        )
    if isinstance(tmp_data["data"], bytes):
        tmp_data["data"] = tmp_data["data"].decode(__salt_system_encoding__)
    return StringIO(tmp_data["data"])
