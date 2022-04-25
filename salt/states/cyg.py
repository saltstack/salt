"""
Installation of Cygwin packages.

A state module to manage cygwin packages. Packages can be installed
or removed.

.. code-block:: yaml

    dos2unix:
      cyg.installed
"""

import logging

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only load if cyg module is available in __salt__.
    """
    if "cyg.list" in __salt__:
        return True
    return (False, "cyg module could not be loaded")


def installed(name, cyg_arch="x86_64", mirrors=None):
    """
    Make sure that a package is installed.

    name
        The name of the package to install

    cyg_arch : x86_64
        The cygwin architecture to install the package into.
        Current options are x86 and x86_64

    mirrors : None
        List of mirrors to check.
        None will use a default mirror (kernel.org)

    CLI Example:

    .. code-block:: yaml

        rsync:
          cyg.installed:
            - mirrors:
              - http://mirror/without/public/key: ""
              - http://mirror/with/public/key: http://url/of/public/key
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    if cyg_arch not in ["x86", "x86_64"]:
        ret["result"] = False
        ret["comment"] = "The 'cyg_arch' argument must be one of 'x86' or 'x86_64'"
        return ret

    log.debug("Installed State: Initial Mirror list: %s", mirrors)

    if not __salt__["cyg.check_valid_package"](
        name, cyg_arch=cyg_arch, mirrors=mirrors
    ):
        ret["result"] = False
        ret["comment"] = "Invalid package name."
        return ret

    pkgs = __salt__["cyg.list"](name, cyg_arch)
    if name in pkgs:
        ret["result"] = True
        ret["comment"] = "Package is already installed."
        return ret

    if __opts__["test"]:
        ret["comment"] = "The package {} would have been installed".format(name)
        return ret

    if __salt__["cyg.install"](name, cyg_arch=cyg_arch, mirrors=mirrors):
        ret["result"] = True
        ret["changes"][name] = "Installed"
        ret["comment"] = "Package was successfully installed"
    else:
        ret["result"] = False
        ret["comment"] = "Could not install package."

    return ret


def removed(name, cyg_arch="x86_64", mirrors=None):
    """
    Make sure that a package is not installed.

    name
        The name of the package to uninstall

    cyg_arch : x86_64
        The cygwin architecture to remove the package from.
        Current options are x86 and x86_64

    mirrors : None
        List of mirrors to check.
        None will use a default mirror (kernel.org)

    CLI Example:

    .. code-block:: yaml

        rsync:
          cyg.removed:
            - mirrors:
              - http://mirror/without/public/key: ""
              - http://mirror/with/public/key: http://url/of/public/key
    """
    ret = {"name": name, "result": None, "comment": "", "changes": {}}

    if cyg_arch not in ["x86", "x86_64"]:
        ret["result"] = False
        ret["comment"] = "The 'cyg_arch' argument must be one of 'x86' or 'x86_64'"
        return ret

    if not __salt__["cyg.check_valid_package"](
        name, cyg_arch=cyg_arch, mirrors=mirrors
    ):
        ret["result"] = False
        ret["comment"] = "Invalid package name."
        return ret

    if name not in __salt__["cyg.list"](name, cyg_arch):
        ret["result"] = True
        ret["comment"] = "Package is not installed."
        return ret

    if __opts__["test"]:
        ret["comment"] = "The package {} would have been removed".format(name)
        return ret
    if __salt__["cyg.uninstall"](name, cyg_arch):
        ret["result"] = True
        ret["changes"][name] = "Removed"
        ret["comment"] = "Package was successfully removed."
    else:
        ret["result"] = False
        ret["comment"] = "Could not remove package."
    return ret


def updated(name=None, cyg_arch="x86_64", mirrors=None):
    """
    Make sure all packages are up to date.

    name : None
        No affect, salt fails poorly without the arg available

    cyg_arch : x86_64
        The cygwin architecture to update.
        Current options are x86 and x86_64

    mirrors : None
        List of mirrors to check.
        None will use a default mirror (kernel.org)

    CLI Example:

    .. code-block:: yaml

        rsync:
          cyg.updated:
            - mirrors:
              - http://mirror/without/public/key: ""
              - http://mirror/with/public/key: http://url/of/public/key
    """
    ret = {"name": "cyg.updated", "result": None, "comment": "", "changes": {}}

    if cyg_arch not in ["x86", "x86_64"]:
        ret["result"] = False
        ret["comment"] = "The 'cyg_arch' argument must be one of 'x86' or 'x86_64'"
        return ret

    if __opts__["test"]:
        ret["comment"] = "All packages would have been updated"
        return ret

    if not mirrors:
        log.warning("No mirror given, using the default.")

    before = __salt__["cyg.list"](cyg_arch=cyg_arch)
    if __salt__["cyg.update"](cyg_arch, mirrors=mirrors):
        after = __salt__["cyg.list"](cyg_arch=cyg_arch)
        differ = DictDiffer(after, before)
        ret["result"] = True
        if differ.same():
            ret["comment"] = "Nothing to update."
        else:
            ret["changes"]["added"] = list(differ.added())
            ret["changes"]["removed"] = list(differ.removed())
            ret["changes"]["changed"] = list(differ.changed())
            ret["comment"] = "All packages successfully updated."
    else:
        ret["result"] = False
        ret["comment"] = "Could not update packages."
    return ret


# https://github.com/hughdbrown/dictdiffer
# DictDiffer is licensed as MIT code
# A dictionary difference calculator
# Originally posted as:
# http://stackoverflow.com/a/1165552


class DictDiffer:
    """
    Calculate the difference between two dictionaries.

    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values
    """

    def __init__(self, current_dict, past_dict):
        """
        Iitialize the differ.
        """
        self.current_dict, self.past_dict = current_dict, past_dict
        self.current_keys, self.past_keys = (
            set(d.keys()) for d in (current_dict, past_dict)
        )
        self.intersect = self.current_keys.intersection(self.past_keys)

    def same(self):
        """
        True if the two dicts are the same.
        """
        return self.current_dict == self.past_dict

    def added(self):
        """
        Return a set of additions to past_dict.
        """
        return self.current_keys - self.intersect

    def removed(self):
        """
        Return a set of things removed from past_dict.
        """
        return self.past_keys - self.intersect

    def changed(self):
        """
        Return a set of the keys with changed values.
        """
        return {o for o in self.intersect if self.past_dict[o] != self.current_dict[o]}

    def unchanged(self):
        """
        Return a set of the keys with unchanged values.
        """
        return {o for o in self.intersect if self.past_dict[o] == self.current_dict[o]}
