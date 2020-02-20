.. _triage-process:

==============
Triage Process
==============

This documentation outlines the current triage process for issues. The current process
is assigned out on a weekly rotation. The person assigned to the rotation each week will triage
the incoming issues that week.


Step 1: Information and Discussion
----------------------------------

Need to determine if the issue has enough information or requires additional discussion
from users outside of the original author. If it is determined that the issue requires more information or
discussion, the user triaging the issue will need to apply the applicaple :ref:`info or discussion label <info-labels>`
and the ``Blocked`` Github Milestone. Once the the required information is obtained they can then
further triage the issue and continue onto Step 2.

Step 2: Type
------------

The next step is to determine what type of issue it is. Please see the different type labels
:ref:`here <type-labels>` for a complete list and apply one label.

Step 3: Replicate (Bug Only)
----------------------------

If possible, the triage user will need to confirm that the bug actually exists by replicating
the reported use case. If the bug is able to be replicated the ``Confirmed`` status label
will need to be applied to the issue.

Step 4: Severity (Bug Only)
---------------------------

If issue is a bug, then one :ref:`severity label <bug-severity-labels>` will need to be applied.

Step 5: Status (Bug Only)
-------------------------

Also, only for Bug issues a :ref:`status label <status-labels>` will need to be applied.

Step 6: Regression (Bug Only)
-----------------------------

If an issue is determined to have regressed from a previous release a ``Regression`` label
will need to be applied to the issue.

Step 7: Milestone
-----------------

Next a Github :ref:`Milestone <milestone-labels>` needs to be applied to the issue.
