.. _reporting-bugs:

==============
Reporting Bugs
==============

Salt uses GitHub to track open issues and feature requests.

To file a bug, please navigate to the `new issue page for the Salt project`__.

.. __: https://github.com/saltstack/salt/issues/new

In an issue report, please include the following information:

 * The output of ``salt --versions-report`` from the relevant machines. This
   can also be gathered remotely by using ``salt <my_tgt>
   test.versions_report``.

 * A description of the problem including steps taken to cause the issue to
   occur and the expected behaviour.

 * Any steps taken to attempt to remediate the problem.

 * Any configuration options set in a configuration file that may be relevant.

 * A reproducible test case. This may be as simple as an SLS file that
   illustrates a problem or it may be a link to a repository that contains a
   number of SLS files that can be used together to re-produce a problem. If
   the problem is transitory, any information that can be used to try and
   reproduce the problem is helpful.

 * [Optional] The output of each salt component (master/minion/CLI) running
   with the ``-ldebug`` flag set.

 .. note::

    Please be certain to scrub any logs or SLS files for sensitive data!
