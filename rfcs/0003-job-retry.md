- Feature Name: Job retry
- Start Date: 2018-10-16
- RFC PR: https://github.com/saltstack/salt/compare/develop...cachedout:job_retry
- Salt Issue: (leave this empty)

# Summary
[summary]: #summary

This feature enables Salt to detect when a minion did not run a job and when the minion comes back online,
the job is published to that minion.

# Motivation
[motivation]: #motivation

For a long time, people have complained that Salt has no way to send a job to a minion that was not available
to receive it at the time that it was published. Doing so would allow Salt administrators to publish a job and
not worry about whether or not a minion that was down at the time did not receive the job.

# Design
[design]: #detailed-design

At a high level, the way that this feature operates is relatively simple and only minor extensions to the core
of salt itself are necessary.

All operations will be gated behind a configuration option called `job_retry` which will default to being
disabled.

We propose a `job_retry` engine be created which can run on the master. The purpose of this engine is to detect
minion "start" events and then to check a master cache for any jobs which might be enqueued and, if found,
pull those pending jobs from the queue and publish them to the minion.

Jobs are enqueued on the master using the masterapi cache subsystem. There shall be an individual cache for each
minion which is found not to respond. In this cache will be a list of JIDs which the master believes were not
sent.

Jobs to be retried are inserted into the cache by the LocalClient when it deterermines that a minion which it expected
to return did not.

Please see https://github.com/saltstack/salt/compare/develop...cachedout:job_retry for a POC.

## Alternatives
[alternatives]: #alternatives

No alternatives considered but ideas welcome.

## Unresolved questions
[unresolved]: #unresolved-questions

* May not work with anything that interacts with the master but bypasses the LocalClient.

* Should minions also check to see if they have run the job? Probably.

# Drawbacks
[drawbacks]: #drawbacks

The main drawback is the risk of running a job twice. Additionally, failure to clear a cache
may cause a job to be run in a loop which would be pretty bad. ;-/
