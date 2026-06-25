.. _targeting-pillar:

======================
Targeting using Pillar
======================

Pillar data can be used when targeting minions. This allows for ultimate
control and flexibility when targeting minions.

.. note::

    To start using Pillar targeting it is required to make a Pillar
    data cache on Salt Master for each Minion via following commands:
    ``salt '*' saltutil.refresh_pillar`` or ``salt '*' saltutil.sync_all``.
    Also Pillar data cache will be populated during the
    :ref:`highstate <running-highstate>` run. Once Pillar data changes, you
    must refresh the cache by running above commands for this targeting
    method to work correctly.

Example:

.. code-block:: bash

    salt -I 'somekey:specialvalue' test.version

Like with :ref:`Grains <targeting-grains>`, it is possible to use globbing
as well as match nested values in Pillar, by adding colons for each level that
is being traversed. The below example would match minions with a pillar named
``foo``, which is a dict containing a key ``bar``, with a value beginning with
``baz``:

.. code-block:: bash

    salt -I 'foo:bar:baz*' test.version

Targeting against a specific pillarenv
======================================

Pillar match commands on the CLI evaluate against the **in-memory** pillar
data that lives on each minion -- i.e. the data that was already compiled
and shipped to the minion the last time it refreshed its pillar.  By
default that in-memory pillar is the merge of every configured pillar
environment.

To target on data sourced exclusively from a single
:conf_minion:`pillarenv`, the targeted minions must first be made to
compile their in-memory pillar against that environment.  Two patterns
are supported:

1. Set :conf_minion:`pillarenv` in the minion configuration file (or
   override it on the master with
   :conf_master:`pillarenv`/``pillarenv_from_saltenv``).  The minion's
   in-memory pillar will then only contain keys from that environment
   and pillar matching with ``-I`` will only see those keys:

   .. code-block:: bash

       salt '*' saltutil.refresh_pillar
       salt -I 'key_only_in_qa_env:value' test.version

2. Run states with an explicit ``pillarenv`` keyword argument when you
   need targeting and pillar selection in the same call:

   .. code-block:: bash

       salt -I 'key:value' state.apply mystates pillarenv=qa

   In this form ``-I 'key:value'`` is still evaluated against the
   minion's *in-memory* pillar; the ``pillarenv=qa`` kwarg only
   controls the pillar made available during state rendering.  If
   ``key`` is not present in the default in-memory pillar the minion
   will not be matched.

.. note::

    Pillar targeting cannot pick which pillarenv to evaluate the match
    against on the master side.  If a key lives only in the ``qa``
    pillarenv, minions must already be running with ``pillarenv: qa``
    (or equivalent) for ``-I 'key:value'`` to find them.  See
    :ref:`How Pillar Environments Are Handled <pillar-environments>`
    for the complete set of options.
