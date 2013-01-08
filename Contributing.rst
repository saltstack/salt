Reporting issues
================

A bug is a *demonstrable problem* that is caused by the code in the repository.

Please read the following guidelines before you `report an issue`_

1. **Use the GitHub issue search** — check if the issue has already been reported. If it has been, 
   please comment on the existing issue.

2. **Check if the issue has been fixed** — the latest `develop` branch may already contain a fix.

3. **Isolate the demonstrable problem** — make sure that the code in the project's repository is 
   *definitely* responsible for the issue.

4. **Include a reproducible example** — Provide the steps which led you to the problem.

Please try to be as detailed as possible in your report too. What is your environment? What steps 
will reproduce the issue? What Operating System? What would you expect to be the outcome? All these 
details will help people to assess and fix any potential bugs.

**Including the output of** ``salt --versions-report`` **will always help.**


Fixing issues
=============

If you wish to help us fixing the issue you're reporting, `Salt's documentation`_ already includes 
information to help you setup a development environment, under `Developing Salt`_.

Fix the issue you have in hands, if possible also add a test case to Salt's testing suite, create a 
`pull request`_, and **that's it**!

Salt's development team will review your fix and if everything is OK, your fix will be merged into 
salt's code.


.. _`report an issue`: https://github.com/saltstack/salt/issues
.. _`Salt's documentation`: http://docs.saltstack.org/en/latest/index.html
.. _`Developing Salt`: http://docs.saltstack.org/en/latest/topics/community.html#developing-salt
.. _`pull request`: http://docs.saltstack.org/en/latest/topics/community.html#setting-a-github-pull-request

.. vim: fenc=utf-8 spell spl=en cc=100 tw=99 fo=want sts=2 sw=2 et
