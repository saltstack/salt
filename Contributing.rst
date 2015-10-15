Licence Notice
==============

The Salt project is open and encouraging to code contributions. Please be
advised that all code contributions will be licenced under the Apache 2.0
License. We cannot accept contributions that already hold a Licence other
than Apache 2.0 without explicit exception.


Reporting issues
================

The Salt issue tracker is used for feature requests and bug reports.

Bugs
----

A bug is a *demonstrable problem* that is caused by the code in the repository.

Please read the following guidelines before you `report an issue`_

1. **Use the GitHub issue search** -- check if the issue has
   already been reported. If it has been, please comment on the existing issue.

2. **Check if the issue has been fixed** -- the latest `develop`
   branch may already contain a fix. Please try to reproduce the bug against
   the latest git head or the latest release.

3. **Isolate the demonstrable problem** -- make sure that the
   code in the project's repository is *definitely* responsible for the issue.

4. **Include a reproducible example** -- Provide the steps which
   led you to the problem.

Please try to be as detailed as possible in your report too. What is your
environment? What steps will reproduce the issue? What Operating System? What
would you expect to be the outcome? All these details will help people to
assess and fix any potential bugs.

**Including the output of** ``salt --versions-report`` **will always help.**

Valid bugs will be categorized for the next release and worked on as quickly
as resources can be reasonably allocated

Features
--------

Salt is always working to be more powerful. Feature additions and requests are
welcomed. When requesting a feature it will be categorized for a release or
placed under "Approved for Future Release".

If a new feature is desired, the fastest way to get it into Salt is to
contribute the code. Before starting on a new feature an issue should be filed
for it. The one requesting the feature will be able to then discuss the feature
with the Salt team and discover the best way to get the feature into Salt and
if the feature makes sense.

It is extremely common that the desired feature has already been completed,
look for it in the docs, ask about it first in IRC, and on the mailing list
before filing the request. It is also common that the problem which would be
solved by the new feature can be easily solved another way, which is a great
reason to ask first.

Fixing issues
=============

If you wish to help us fixing the issue you're reporting, `Salt's documentation`_ already includes
information to help you setup a development environment, under `Developing Salt`_.

Fix the issue you have in hands, if possible also add a test case to Salt's testing suite, create a
`pull request`_, and **that's it**!

Salt's development team will review your fix and if everything is OK, your fix will be merged into
salt's code.


.. _`report an issue`: https://github.com/saltstack/salt/issues
.. _`Salt's documentation`: http://docs.saltstack.com/en/latest/index.html
.. _`Developing Salt`: http://docs.saltstack.com/en/latest/topics/development/hacking.html
.. _`pull request`: http://docs.saltstack.com/en/latest/topics/development/contributing.html#sending-a-github-pull-request

.. vim: fenc=utf-8 spell spl=en
