.. _matchers:

========
Matchers
========

.. versionadded:: Flourine

Matchers are modules that provide Salt's targeting abilities.  As of the
Flourine release, matchers can be dynamically loaded.  Currently new matchers
cannot be created, but existing matchers may have their functionality altered or
extended.

For details of targeting methods, see the :ref:`Targeting <targeting>` topic.

Matchers have a master and a minion component. The minion-side matcher component
is what the minion uses to verify that its ID (or other targetable-data)
complies with the target expression that was sent over the event bus. The
master-side component is what narrows down the targeted minions so every minion
in a Salt infrastructure is not targeted for every command. It's important that
both components return congruent results or else minions will be targeted
incorrectly and/or targeting will appear to fail for no apparent reason.

The minion-side component of a matcher module must have a function called
``match()``. This function ends up becoming a method on the Matcher class and 
requires at least two arguments, ``self`` (because the function
will be turned into a method), and ``tgt``, which is the actual target string.
The grains and pillar matchers also take a ``delimiter`` argument and should
default to ``DEFAULT_TARGET_DELIM``.

Minion-side matcher functions return a boolean indicating if the ID of the minion on which
the function runs is in the set of minions being targeted.

The master-side component of a matcher must have a function called ``mmatch()``
(for "Master-side Matcher").  Unlike the minion-side this function will not be
turned into an object method, but it still takes an argument of ``self`` as it
will be called by object methods and will need access to their attributes.  This
function also takes the following parameters:

.. code-block:: python

   expr: The expression that was passed in against which we will target
   delimiter: The separator used in the target (for example, grains typically
              have the key and value separated by a ``:``)
   greedy: A boolean indicating if the match should use greedy regular expression
           semantics.  This is only used when the matcher involves regular expressions.

Master-side matcher functions return a dictionary with two keys, ``minions`` and ``missing``.

.. code-block:: python

   { 'minions': <list of minions that match the target>,
     'missing': <list of minions that do not match the target> }


Like other Salt loadable modules, modules that override built-in functionality
can be placed in ``file_roots`` in a special directory and then copied to the
minion through the normal sync process.  :py:func:`saltutil.sync_all <salt.modules.saltutil.sync_all>`
will transfer all loadable modules, and the Flourine release introduces both module and runner versions of
:py:func:`saltutil.sync_matchers <salt.modules.saltutil.sync_matchers>`.  For matchers, the directory is
``/srv/salt/_matchers`` (assuming your ``file_roots`` is set to the default
``/srv/salt``).

As an example, let's modify the ``list`` matcher to have the separator be a
'``/``' instead of the default '``,``'.


.. code-block:: python

    # -*- coding: utf-8 -*-
    from __future__ import absolute_import, print_function, unicode_literals
    from salt.ext import six  # pylint: disable=3rd-party-module-not-gated

    import logging

    log = logging.getLogger(__file__)

    def match(self, tgt):
        '''
        Determines if this host is on the list
        '''
        if isinstance(tgt, six.string_types):
            minions_target = tgt.split('/')
        if isinstance(tgt, list):
            minions_target = []
            for minion_match in tgt:
                minions_target.extend(minion_match.split('/'))
        return bool(self.opts['id'] in minions_target)


    def mmatch(self, expr, greedy):

        if isinstance(expr, six.string_types):
            minions_target = [m for m in expr.split('/') if m]
        if isinstance(expr, list):
            minions_target = []
            for minion_match in expr:
                minions_target.extend(minion_match.split('/'))
        minions = self._pki_minions()
        ret = {'minions': [x for x in minions_target if x in minions],
                'missing': [x for x in minions_target if x not in minions]}
        return ret


Place this code in a file called ``list_match.py`` in ``_matchers`` in your
``file_roots``. Sync this down to your minions with
:py:func:`saltutil.sync_matchers <salt.modules.saltutil.sync_matchers>`.  Then
sync the it to the master's loadable module cache with ``salt-run saltutil.sync_matchers``.
Restart your master and minions.

Then attempt to match with the following, replacing ``minionX`` with three of your minions.

.. code-block:: shell

   salt -L 'minion1/minion2/minion3' test.ping


Three of your minions should respond.

The current supported matchers and associated filenames are

===============  ======================  ===================
Salt CLI Switch  Match Type              Filename
===============  ======================  ===================
<none>           Glob                    glob_match.py
-C               Compound                compound_match.py
-E               Perl-Compatible         pcre_match.py
                 Regular Expressions
-L               List                    list_match.py
-G               Grain                   grain_match.py
-P               Grain Perl-Compatible   grain_pcre_match.py
                 Regular Expressions
-N               Nodegroup               nodegroup_match.py
-R               Range                   range_match.py
-I               Pillar                  pillar_match.py
-J               Pillar Perl-Compatible  pillar_pcre.py
                 Regular Expressions    
-S               IP-Classless Internet   ipcidr_match.py
                 Domain Routing
===============  ======================  ===================
