.. _matchers:

========
Matchers
========

.. versionadded:: 3000

Matchers are modules that provide Salt's targeting abilities.  As of the
3000 release, matchers can be dynamically loaded.  Currently new matchers
cannot be created because the required plumbing for the CLI does not exist yet.
Existing matchers may have their functionality altered or extended.

For details of targeting methods, see the :ref:`Targeting <targeting>` topic.

A matcher module must have a function called ``match()``. This function ends up
becoming a method on the Matcher class.  All matcher functions require at least
two arguments, ``self`` (because the function will be turned into a method), and
``tgt``, which is the actual target string.  The grains and pillar matchers also
take a ``delimiter`` argument and should default to ``DEFAULT_TARGET_DELIM``.

Like other Salt loadable modules, modules that override built-in functionality
can be placed in ``file_roots`` in a special directory and then copied to the
minion through the normal sync process.  :py:func:`saltutil.sync_all <salt.modules.saltutil.sync_all>`
will transfer all loadable modules, and the 3000 release introduces
:py:func:`saltutil.sync_matchers <salt.modules.saltutil.sync_matchers>`.  For matchers, the directory is
``/srv/salt/_matchers`` (assuming your ``file_roots`` is set to the default
``/srv/salt``).

As an example, let's modify the ``list`` matcher to have the separator be a
'``/``' instead of the default '``,``'.


.. code-block:: python

    from __future__ import absolute_import, print_function, unicode_literals
    from salt.ext import six  # pylint: disable=3rd-party-module-not-gated


    def match(self, tgt):
        """
        Determines if this host is on the list
        """
        if isinstance(tgt, six.string_types):
            # The stock matcher splits on `,`.  Change to `/` below.
            tgt = tgt.split("/")
        return bool(self.opts["id"] in tgt)


Place this code in a file called ``list_match.py`` in a ``_matchers`` directory in your
``file_roots``. Sync this down to your minions with
:py:func:`saltutil.sync_matchers <salt.modules.saltutil.sync_matchers>`.
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
