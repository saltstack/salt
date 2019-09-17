- Feature Name: Minion Capabilitles
- Start Date: 2018-11-22
- RFC PR: 
- Salt Issue:
- Keywords: capability capabilities introspect introspection

# Summary
[summary]: #summary

Mechanism to know if a minion is capable of doing something specific,
that wasnt known during the version update.

# Motivation
[motivation]: #motivation

Unlike client-less systems, Salt has should deal with the client
systems. These clients supposed to be compatible with the states, sent
from the master node. When updates are frequent, two versions
backward-compatibility sorts out this problem naturally. But there is
a number of use cases when this does not apply. Few examples:

- if an enterprise system is not updated often, even Salt client stays with
  old version or yet only required features are back-ported.

- if a new feature wasn't released to the older version but only
  back-ported by supporting vendor.

The use-case above makes such client unknown what precise features has
been back-ported and what was not. Any back-ported feature was
explicitly placed by exact request. That means, that on two outdated
minions can be features that are in common, but some might be missing
on both minions or just one. Consider the situation, when minions A, B and
C, where A has all new features 1, 2 and 3; B has only feature 2 and C
has feature 1 and 3.

Some features might be very subtle, e.g. package locking support
during their update or some extra parameter has been added to the
existing function or data is returned slightly different etc.

How do we _know_ that in the only SLS we're executing on all minions
at once?

# Design
[design]: #detailed-design

Introduce introspection variable to Jinja templates, called `capable`.
Its proposed design allows to "look inside" into any function or
corner of the minion, if needed, and then by its results SLS logic can
continue on decision what to do next.

This variable works like a tree and can match any of the branches. It
has following layout:

```
capable
  |
  +--- modules
  |      |
  |      +-- <modulename>.<function>
  |                          |
  |                          +-- name
  |                          |
  |                          +-- signature
  |                          |     |
  |                          |     +-- params
  |                          |     |
  |                          |     +-- args
  |                          |     |
  |                          |     +-- kwargs
  |                          |     |
  |                          |     +-- defaults
  |                          |     |
  |                          |     +-- spec
  |                          |
  |                          +-- doc
  |                                |
  |                                +-- has_parameter
  |                                |
  |                                +-- contains
  |
  +--- states
  |      |
  |      +-- <statename>.<function>
  |                         |
  |                         +-- ... (see modules)
  +--- config
  |
  +--- pillars

```

Such tree would be getting the information about particular
function. The `capable` variable would lazy-loading particular data on
demand when accessed.

This is an example how syntax would look like:


```jinja2
{% if 'host' in capable.modules.network.ping.signature.params %}
  {# do something with network.ping #}
{% endif %}
```

From this example, `capable` loads `network` module, introspects
`ping` function and reports if its signature contains accepted
parameter, called `host`.

However, since not always signature can be explicit. In case, when
parameters aren't enlisted explicitly, but are covered in `**kwargs`
or `*args`, they _have_ to be properly documented. And so the check
can be done by accessing function documentation:

```jinja2
{% if capable.modules.network.ping.doc.has_parameter('host') %}
  {# do something with network.ping #}
{% endif %}
```
Sometimes back-ported feature might only mention the change in
documentation of the function, without introducing any parameters to
the signature at all. For this can be introspected its content:

```jinja2
{% if capable.modules.network.ping.doc.contains('Performs at ICMP ping') %}
  {# do something with network.ping #}
{% endif %}
```

Note that `capable` is designed to never fail if wrong tree branch is
accessed. For example, this will just result to `False`:

```jinja2
{% if capable.who.knows.what.is.this %}
  ...
{% endif %}
```

Also iterations works the same way:

```jinja2
{% if 'something' in capable.who.knows.what.is.this %}
  ...
{% endif %}
```

...or hashes:

```jinja2
{% if capable.who.knows.what.is.this['something'] %}
  ...
{% endif %}
```

...or even crazy hashes:

```jinja2
{% if capable.who['knows'].what['is'].this['something'].there() %}
  ...
{% endif %}
```

## Bonus Feature

The `capable` variable essentially can replace-or-help to `grains`,
`salt['<function>']` and `pillar` dictionaries bringing lazy loading
to the data and syntax sugar. For example, we can get rid of calling
functions as a string keys of `salt` dictionary.

For example, this is a current way:

```jinja2
{% if salt['pillar.get']('something') == 'foo' %}
  {% set repos = salt['pkg.list_repos']() %}
{% endif %}
```

Since `capable` can be installed as `salt` filter, this can be done cleaner:

```jinja2
{% if salt.pillar.get('something') == 'foo' %}
  {% set repos = salt.pkg.list_repos() %}
{% endif %}
```

The second example works exactly as an example above, just no more
strings and hashing. Note that the old syntax is preserved as is and
can co-exist in parallel without problems.

To wrap this up, this can:

- Lazy load only what is needed at the moment
- Help reading and writing SLS much cleaner than before

## Alternatives
[alternatives]: #alternatives

There is not much alternatives to this.

Version tracking will not work, because if a particuar little change
has been made to the package, it is still unknown how version 1234.5.6
different from 1234.5.6 with a different build. Date/time of last
build time also is not helping, if there are specifically patched
minions for a particuar user.

Keeping a map of changes next to the version requires thorough
maintenance and is prone to errors.

## Unresolved questions
[unresolved]: #unresolved-questions

N/A

# Drawbacks
[drawbacks]: #drawbacks

This feature requires to be back-ported to all supported versions in
order to be in use.
