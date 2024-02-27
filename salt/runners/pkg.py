"""
Package helper functions using ``salt.modules.pkg``

.. versionadded:: 2015.8.0
"""

import salt.minion
import salt.output


def _get_returner(returner_types):
    """
    Helper to iterate over retuerner_types and pick the first one
    """
    for returner in returner_types:
        if returner:
            return returner


def list_upgrades(jid, style="group", outputter="nested", ext_source=None):
    """
    Show list of available pkg upgrades using a specified format style

    CLI Example:

    .. code-block:: bash

        salt-run pkg.list_upgrades jid=20141120114114417719 style=group
    """
    mminion = salt.minion.MasterMinion(__opts__)
    returner = _get_returner(
        (__opts__["ext_job_cache"], ext_source, __opts__["master_job_cache"])
    )

    data = mminion.returners[f"{returner}.get_jid"](jid)
    pkgs = {}

    if style == "group":
        for minion in data:
            results = data[minion]["return"]
            for pkg, pkgver in results.items():
                if pkg not in pkgs:
                    pkgs[pkg] = {pkgver: {"hosts": []}}

                if pkgver not in pkgs[pkg].keys():
                    pkgs[pkg].update({pkgver: {"hosts": []}})

                pkgs[pkg][pkgver]["hosts"].append(minion)

    if outputter:
        salt.output.display_output(pkgs, outputter, opts=__opts__)

    return pkgs
