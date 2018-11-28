- Feature Name: Makes salt minion's master_port and publish_port options depend on each master's ip.
- Start Date: 2018-12-12
- RFC PR:
- Salt Issue:

# Summary
[summary]: #summary

For example, current salt minion configuration can't cover the following setting of multi-master.

master1's config
```
 interface: 1.1.1.1
 ret_port: 30001
 publish_port: 30002
```
master2's config
```
 interface: 1.1.1.2
 ret_port: 30008
 publish_port: 30009
```

minion's config
```
master:
  1.1.1.1:30001
  1.1.1.2:30001
publish_port: ?
```

# Motivation
[motivation]: #motivation

We are trying to deploy salt master using kubernetes, and kubernetes-like systems allocate network resources highly dynamically to use the limited resources efficiently. To leverage the system's network environment (dynamically allocate ports to expose container's ports to the outer network), `publish_port` and `ret_port` of salt masters of a multi-master environment can be assigned as different ports like the above setting.

# Design
[design]: #detailed-design

Current salt minion's master config
```
master:
  1.1.1.1:RET_PORT (MASTER_PORT)
  1.1.1.2:RET_PORT (MASTER_PORT)
publish_port: PUBLISH_PORT
```

Desired salt minion's master config
```
master_uri_format: connection_dict
master:
  - host: 1.1.1.1
    master_port: 30001
    publish_port: 30002
  - host: 1.1.1.2
    master_port: 30008
    publish_port: 30009
```

## Alternatives
[alternatives]: #alternatives

Uses nested to parse ip, master port, publish port, (inspired by @isbm's comment)

```
master_uri_format: nested
master:
- master: [2001:0db8:85a3:0000:0000:8a2e:0370:7334]:3001
  publish_port: 3002
- master: 123.123.123.123:3001
  publish_port: 3002
- master: 123.123.123.123  # master port will be set as 4506 (default port)
  publish_port: 3002
  master_uri_format: ip_only
- master: 123.123.123.123  # master port will be set as 4506, publish port will be set as 4505 (default port)
```

## Unresolved questions
[unresolved]: #unresolved-questions

Format of the new `master_uri_format` option. should it be nested style? or should it be simple structured dictionary style? is there any other option to represent this kinds of information better?

# Drawbacks
[drawbacks]: #drawbacks

- Backward compatibility, how to support both formats (old format, and new format) of master connection information of salt minion config?
- Implementation cost, we should find all being affected points in the minion code, and patch it to accept the new form of salt master connection config.
- Documentation

Adding a new `master_uri_format` is a simple job for the current version of minion. The only point that we should modify is the function `prep_ip_port`.
Make the function can handle this new `master_uri_format`, then it will work well without any further modifications.
