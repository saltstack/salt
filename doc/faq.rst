Frequently Asked Questions
==========================

Is Salt open-core?
------------------

No. Salt is 100% committed to being open-source, including all of our APIs and
the new `'Halite' web interface`_ which will be included in version 0.17.0. It
is developed under the `Apache 2.0 license`_, allowing it to be used in both
open and proprietary projects.

.. _`'Halite' web interface`: https://github.com/saltstack/halite
.. _`Apache 2.0 license`: http://www.apache.org/licenses/LICENSE-2.0.html

What ports should I open on my firewall?
----------------------------------------

Minions need to be able to connect to the master on TCP ports 4505 and 4506.
Minions do not need any inbound ports open. More detailed information on
firewall settings can be found :doc:`here </topics/tutorials/firewall>`.

Should I use :mod:`cmd.run <salt.states.cmd.run>` or :mod:`cmd.wait <salt.states.cmd.wait>`?
----------------------------------------------------------------------------------------------------

These states are often confused. A description of the difference between the
two can be found in the docmentation for the :mod:`cmd states
<salt.states.cmd>`.

How does Salt guess the Minion's hostname?
------------------------------------------

This process is explained in detail :ref:`here <minion-id-generation>`.

Why aren't my custom modules/states/etc. syncing to my Minions?
---------------------------------------------------------------

If you are using the :doc:`git fileserver backend </topics/tutorials/gitfs>`,
and Salt 0.16.3 or older, then this may be due to a bug in gitfs. More
information about this can be found :ref:`here <faq-gitfs-bug>`.
