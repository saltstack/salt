# -*- coding: utf-8 -*-
"""
Manage package remote repo using FreeBSD pkgng
==============================================

Salt can manage the URL pkgng pulls packages from.
ATM the state and module are small so use cases are
typically rather simple:

.. code-block:: yaml

    pkgng_clients:
      pkgng.update_packaging_site:
        - name: "http://192.168.0.2"
"""
from __future__ import absolute_import, print_function, unicode_literals


def update_packaging_site(name):
    ret = {"name": name, "changes": {}, "result": False, "comment": ""}

    __salt__["pkgng.update_package_site"](name)
    #    cmd = 'diff /usr/local/etc/pkg.conf /usr/local/etc/pkg.conf.bak'
    #    res = __salt__['cmd.run'](cmd)
    #    ret['changes'] = res
    ret["result"] = True
    return ret
