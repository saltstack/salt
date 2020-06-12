Feature Name: netapi-async-batch
- Start Date: 2018-09-20
- RFC PR: (leave this empty)

# Summary
[summary]: #summary

Salt's HTTP API (NetApi) has incomplete support for the "batching mode" available via the commandline `-b` switch, in particular the `rest_cherrypy` implementation can either support asynchronous or batched commands, but not both at the same time.

This RFC is about supporting batched commands in the existing asynchronous endpoint via additional parameters.

# Motivation
[motivation]: #motivation

Salt can run commands in parallel on huge number of minions, and those commands might generate load on potentially unrelated parts of the user's infrastructure (eg. Web servers), hence some kind of rate limiting ("batching" in current Salt jargon) is desirable.

Uyuni/SUSE Manager would need to leverage such mechanism through `rest_cherrypy`, in particular via asynchronous commands which is how the integration is done at this point.

# Design
[design]: #detailed-design

Despite batching being implemented in [salt/cli/batch.py](https://github.com/saltstack/salt/blob/v2018.3.2/salt/cli/batch.py), the current `Batch` class is actually a shared component used by:
  - [the command line `salt` command](https://github.com/saltstack/salt/blob/v2018.3.2/salt/cli/salt.py#L232)
  - [the `rest_cherrypy` implementation](https://github.com/saltstack/salt/blob/v2018.3.2/salt/client/__init__.py#L571) (through `LocalClient.cmd_batch`)
  - [the currently-deleted `rest_tornado` implementation](https://github.com/saltstack/salt/blob/2015.5/salt/netapi/rest_tornado/saltnado.py#L216) but only to resolve the list of minions. [The bulk of the logic has been reimplemented in saltnado.py](https://github.com/saltstack/salt/blob/2015.5/salt/netapi/rest_tornado/saltnado.py#L862-L884). Note that the whole batching code in `rest_tornado` [has been deleted](https://github.com/saltstack/salt/commit/3d8f3d18f6afa760c70db87cbbaaa71d877ca4d3) as a [response of a security issue](https://github.com/saltstack/salt/issues/38497) (lack of eauth support) - but in principle this code here works

Please note that the `Batch` class currently works synchronously only - this is of course OK for the CLI, it's acceptable for direct `LocalClient` use by third-party Python code, it's probably also acceptable for `rest_cherrypy` (although asynchronous calls are not supported) or direct `LocalClient` but it's definitely not adequate for `rest_tornado`.

We propose to move the handling of batches into `salt-master`, so that long-term there is only one implementation and all clients/NetApi clients get support "for free".

Implementation ideas:
 - a new method is added to `ClearFuncs` that is called in place of the [publish](https://github.com/saltstack/salt/blob/develop/salt/master.py#L2035) for asynchronous batched command execution (eg. `publish_batch`). This method will receive batch-specific parameters and use `publish` internally
 - it is assumed the [publish](https://github.com/saltstack/salt/blob/develop/salt/master.py#L2035) will not be changed. Further, separate discussion might be needed otherwise
 - implementation in principle follows from the existing `cli.Batch` class and makes it nonblocking/Tornado-aware, and removes the dependency from the client implementation. It is not expected for this method to duplicate significant code from `publish`, separate discussion might be needed otherwise
 - long term, all endpoints use this new code and `cli.Batch` is removed. Immediate goal would be to add asynchronous, batching mode to `rest_cherrypy` only (conforming to the now-deleted `rest_tornado` implementation noted above)

The PR would come with unit or integration tests.

## Alternatives
[alternatives]: #alternatives

 - bringing back the support to `salt_tornado` by adding `eauth` handling. This is viable for Salt in general but not viable in Uyuni, because we need `ssh` client support [which `salt_tornado` does not have at the moment](https://github.com/saltstack/salt/issues/26505)
 - implementing a worker thread in `rest_cherrypy` to use the current `cli.Batch` class "in the background". This is doable and easier, but is felt like a less clean solution in that code is not really shared. We can consider that option if Salt maintainers like it better

## Unresolved questions
[unresolved]: #unresolved-questions

 - can we reuse part of the dropped code from `rest_tornado`?
 - do SaltStack maintainers have any plan to drop `rest_cherrypy` or to complete missing features in `rest_tornado`?

# Drawbacks
[drawbacks]: #drawbacks

As this is a refactoring, there is some risk of regressions. It is not expected the risk to be high due to the fact this mechanism is totally optional and not made default.

