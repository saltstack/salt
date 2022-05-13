"""
Use `Varstack <https://github.com/conversis/varstack>`_ to provide tops data

.. |varstack| replace:: **varstack**

This :ref:`master_tops <master-tops-system>` plugin provides access to
the |varstack| hierarchical yaml files, so you can user |varstack| as a full
:mod:`external node classifier <salt.tops.ext_nodes>` and
store state information (top data) in it.

Configuring Varstack
====================

To use varstack as a master top external node classifier, install varstack
as documented. Then, add to your master's configuration:

.. code-block:: yaml

  master_tops:
    varstack: /path/to/the/config/file/varstack.yaml

Varstack will then use /path/to/the/config/file/varstack.yaml (usually
/etc/varstack.yaml) to determine which configuration
data to return as adapter information. From there you can take a look at the
`README <https://github.com/conversis/varstack/blob/master/README.md>`_ of
varstack to learn how this file is evaluated. The ENC part will just return
the 'states' dictionary for the node.

Ie, if my.fqdn.yaml file contains:

.. code-block:: yaml

    ---
    states:
      - sudo
      - openssh
      - apache
      - salt.minion

these will be returned as {'base': ['sudo', 'openssh', 'apache', 'salt.minion']} and
managed by salt as if given from a top.sls file.

"""


try:
    import varstack
except ImportError:
    varstack = None

# Define the module's virtual name
__virtualname__ = "varstack"


def __virtual__():
    return (False, "varstack not installed") if varstack is None else __virtualname__


def top(**kwargs):
    """
    Query |varstack| for the top data (states of the minions).
    """

    conf = __opts__["master_tops"]["varstack"]
    __grains__ = kwargs["grains"]

    vs_ = varstack.Varstack(config_filename=conf)
    ret = vs_.evaluate(__grains__)
    return {"base": ret["states"]}
