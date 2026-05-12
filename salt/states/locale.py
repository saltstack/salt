"""
Management of languages/locales
===============================

Manage the available locales and the system default:

.. code-block:: yaml

    us_locale:
      locale.present:
        - name: en_US.UTF-8

    default_locale:
      locale.system:
        - name: en_US.UTF-8
        - require:
          - locale: us_locale
"""

from salt.exceptions import CommandExecutionError


def __virtual__():
    """
    Only load if the locale module is available in __salt__
    """
    if "locale.get_locale" in __salt__:
        return True
    return (False, __salt__.missing_fun_string("locale.get_locale"))


def system(name):
    """
    Set the locale for the system

    name
        The name of the locale to use
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}
    try:
        if __salt__["locale.get_locale"]() == name:
            ret["result"] = True
            ret["comment"] = f"System locale {name} already set"
            return ret
        if __opts__["test"]:
            ret["comment"] = f"System locale {name} needs to be set"
            return ret
        if __salt__["locale.set_locale"](name):
            ret["changes"] = {"locale": name}
            ret["result"] = True
            ret["comment"] = f"Set system locale {name}"
            return ret
        else:
            ret["result"] = False
            ret["comment"] = f"Failed to set system locale to {name}"
            return ret
    except CommandExecutionError as err:
        ret["result"] = False
        ret["comment"] = f"Failed to set system locale: {err}"
        return ret


def present(name):
    """
    Generate a locale if it is not present

    .. versionadded:: 2014.7.0

    name
        The name of the locale to be present. Some distributions require the
        charmap to be specified as part of the locale at this point.
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": ""}
    if __salt__["locale.avail"](name):
        ret["result"] = True
        ret["comment"] = f"Locale {name} is already present"
        return ret
    if __opts__["test"]:
        ret["comment"] = f"Locale {name} needs to be generated"
        return ret
    if __salt__["locale.gen_locale"](name):
        ret["changes"] = {"locale": name}
        ret["result"] = True
        ret["comment"] = f"Generated locale {name}"
        return ret
    else:
        ret["result"] = False
        ret["comment"] = f"Failed to generate locale {name}"
        return ret
