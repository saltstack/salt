- Feature Name: Salt Capabilities on Minions
- Start Date: 2018-06-15
- RFC PR: (leave this empty)
- Salt Issue: (leave this empty)

# Summary
[summary]: #summary

Bring a mechanism to figure out if certain Salt feature/capability is available on the minion.

# Motivation
[motivation]: #motivation

Since Salt is growing and growing, new features and functionalities are added through the different versions. In a common scenario, the user has multiple Salt version and releases installed across all the the different minions, making hard to know whether a Salt minion installation provides certain capability or not.

This RFC suggests the introduction of the "Salt Capabilities" to allow easily checking of capabilities on the Salt minion side via Grains.

An initial POC is already implemented [here](https://github.com/openSUSE/salt/commit/b30ad404ed3a4a54a283b2a7809d415d99b2b776), where a set of pre-calculated capabilities are injected as `grains['salt_capabilities']` on the minion.

This would allow defining Salt states as following:

```yaml
apply_SUSE-SLE-SERVER-12-SP3-2018-964_patch:
{% if "ZYPPER_PATCH_INSTALLATION" in grains.get('salt_capabilities', []) %}
  pkg.patch_installed:
    - advisory_ids:
      - SUSE-SLE-SERVER-12-SP3-2018-964
{% else %}
  pkg.installed:
    - pkgs:
      - libpython2_7-1_0: 2.7.13-28.3.2
      - python: 2.7.13-28.3.2
      - python-base: 2.7.13-28.3.2
      - python-curses: 2.7.13-28.3.2
      - python-xml: 2.7.13-28.3.2
{% endif %}
```

# Design
[design]: #detailed-design

There is still not detailed design, but these are some ideas:

- Salt capabitilies should be as Grains on the Minion.
- The capabilities should be calculated only once.
- Ideally, an auto-discovery mechanism can run as part of `setup.py` execution to inspect and gather all available capabilities from all the Salt code.
- Alternatively, a set of fixed capabilities could be provided at packaging time.

## Alternatives
[alternatives]: #alternatives

What other designs have been considered? What is the impact of not doing this?

## Unresolved questions
[unresolved]: #unresolved-questions

- What happen with the custom modules? How to gather capabilities from there?

# Drawbacks
[drawbacks]: #drawbacks

There are tradeoffs to choosing any path. Attempt to identify them here.
