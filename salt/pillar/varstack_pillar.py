"""
Use `Varstack <https://github.com/conversis/varstack>`_ data as a Pillar source

Configuring Varstack
====================

Using varstack in Salt is fairly simple. Just put the following into the
config file of your master:

.. code-block:: yaml

    ext_pillar:
      - varstack: /etc/varstack.yaml

Varstack will then use /etc/varstack.yaml to determine which configuration
data to return as pillar information. From there you can take a look at the
`README <https://github.com/conversis/varstack/blob/master/README.md>`_ of
varstack on how this file is evaluated.
"""

try:
    import varstack
except ImportError:
    varstack = None

# Define the module's virtual name
__virtualname__ = "varstack"


def __virtual__():
    return (
        varstack and __virtualname__ or False,
        "The varstack module could not be loaded: varstack dependency is missing.",
    )


def ext_pillar(
    minion_id, pillar, conf  # pylint: disable=W0613  # pylint: disable=W0613
):
    """
    Parse varstack data and return the result
    """
    vs = varstack.Varstack(config_filename=conf)
    return vs.evaluate(__grains__)
