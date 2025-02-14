"""
Configuration of the alternatives system

Control the alternatives system

.. code-block:: jinja

  {% set my_hadoop_conf = '/opt/hadoop/conf' %}

  {{ my_hadoop_conf }}:
    file.directory

  hadoop-0.20-conf:
    alternatives.install:
      - name: hadoop-0.20-conf
      - link: /etc/hadoop-0.20/conf
      - path: {{ my_hadoop_conf }}
      - priority: 30
      - require:
        - file: {{ my_hadoop_conf }}

  hadoop-0.20-conf:
    alternatives.remove:
      - name: hadoop-0.20-conf
      - path: {{ my_hadoop_conf }}

"""

# Define a function alias in order not to shadow built-in's
__func_alias__ = {"set_": "set"}


def __virtual__():
    """
    Only load if alternatives execution module is available.
    """
    if "alternatives.auto" in __salt__:
        return True
    return (False, "alernatives module could not be loaded")


def install(name, link, path, priority):
    """
    Install new alternative for defined <name>

    name
        is the master name for this link group
        (e.g. pager)

    link
        is the symlink pointing to /etc/alternatives/<name>.
        (e.g. /usr/bin/pager)

    path
        is the location of the new alternative target.
        NB: This file / directory must already exist.
        (e.g. /usr/bin/less)

    priority
        is an integer; options with higher numbers have higher priority in
        automatic mode.
    """
    ret = {
        "name": name,
        "link": link,
        "path": path,
        "priority": priority,
        "result": True,
        "changes": {},
        "comment": "",
    }

    if __salt__["alternatives.check_exists"](name, path):
        ret["comment"] = "Alternative {} for {} is already registered".format(
            path, name
        )
    else:
        if __opts__["test"]:
            ret["comment"] = (
                "Alternative will be set for {} to {} with priority {}".format(
                    name, path, priority
                )
            )
            ret["result"] = None
            return ret

        out = __salt__["alternatives.install"](name, link, path, priority)
        if __salt__["alternatives.check_exists"](name, path):
            if __salt__["alternatives.check_installed"](name, path):
                ret["comment"] = (
                    "Alternative for {} set to path {} with priority {}".format(
                        name, path, priority
                    )
                )
            else:
                ret["comment"] = (
                    "Alternative {} for {} registered with priority {} and "
                    "not set to default".format(path, name, priority)
                )
            ret["changes"] = {
                "name": name,
                "link": link,
                "path": path,
                "priority": priority,
            }
        else:
            ret["result"] = False
            ret["comment"] = f"Alternative for {name} not installed: {out}"

    return ret


def remove(name, path):
    """
    Removes installed alternative for defined <name> and <path>
    or fallback to default alternative, if some defined before.

    name
        is the master name for this link group
        (e.g. pager)

    path
        is the location of one of the alternative target files.
        (e.g. /usr/bin/less)
    """
    ret = {"name": name, "path": path, "result": True, "changes": {}, "comment": ""}

    isinstalled = __salt__["alternatives.check_exists"](name, path)
    if isinstalled:
        if __opts__["test"]:
            ret["comment"] = f"Alternative for {name} will be removed"
            ret["result"] = None
            return ret
        __salt__["alternatives.remove"](name, path)
        current = __salt__["alternatives.show_current"](name)
        if current:
            ret["result"] = True
            ret["comment"] = (
                "Alternative for {} removed. Falling back to path {}".format(
                    name, current
                )
            )
            ret["changes"] = {"path": current}
            return ret

        ret["comment"] = f"Alternative for {name} removed"
        ret["changes"] = {}
        return ret

    current = __salt__["alternatives.show_current"](name)
    if current:
        ret["result"] = True
        ret["comment"] = "Alternative for {} is set to it's default path {}".format(
            name, current
        )
        return ret

    ret["result"] = False
    ret["comment"] = f"Alternative for {name} doesn't exist"

    return ret


def auto(name):
    """
    .. versionadded:: 0.17.0

    Instruct alternatives to use the highest priority
    path for <name>

    name
        is the master name for this link group
        (e.g. pager)

    """
    ret = {"name": name, "result": True, "comment": "", "changes": {}}

    display = __salt__["alternatives.display"](name)
    line = display.splitlines()[0]
    if line.endswith(" auto mode"):
        ret["comment"] = f"{name} already in auto mode"
        return ret

    if __opts__["test"]:
        ret["comment"] = f"{name} will be put in auto mode"
        ret["result"] = None
        return ret
    ret["changes"]["result"] = __salt__["alternatives.auto"](name)
    return ret


def set_(name, path):
    """
    .. versionadded:: 0.17.0

    Sets alternative for <name> to <path>, if <path> is defined
    as an alternative for <name>.

    name
        is the master name for this link group
        (e.g. pager)

    path
        is the location of one of the alternative target files.
        (e.g. /usr/bin/less)

    .. code-block:: yaml

        foo:
          alternatives.set:
            - path: /usr/bin/foo-2.0
    """
    ret = {"name": name, "path": path, "result": True, "changes": {}, "comment": ""}

    current = __salt__["alternatives.show_current"](name)
    if current == path:
        ret["comment"] = f"Alternative for {name} already set to {path}"
        return ret

    display = __salt__["alternatives.display"](name)
    isinstalled = False
    for line in display.splitlines():
        if line.startswith(path):
            isinstalled = True
            break

    if isinstalled:
        if __opts__["test"]:
            ret["comment"] = "Alternative for {} will be set to path {}".format(
                name, path
            )
            ret["result"] = None
            return ret
        __salt__["alternatives.set"](name, path)
        current = __salt__["alternatives.show_current"](name)
        if current == path:
            ret["comment"] = f"Alternative for {name} set to path {current}"
            ret["changes"] = {"path": current}
        else:
            ret["comment"] = f"Alternative for {name} not updated"

        return ret

    else:
        ret["result"] = False
        ret["comment"] = f"Alternative {path} for {name} doesn't exist"

    return ret
