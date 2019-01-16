- Feature Name: `change_requisite_handling`
- Start Date: 2019-01-15
- RFC PR: (leave this empty)
- Salt Issue: (leave this empty)

# Summary
[summary]: #summary

We want to change how requisites and excludes work together to build the highstate. This proposal requests that when we have an exclude that would break a requisite, that the exclude take precedence over the requisite.

# Motivation
[motivation]: #motivation

In the past we've had [at least a few people](https://github.com/saltstack/salt/issues/6237) expect that if they exclude a state, the require would go away. Because this behavior is not well documented and unexpected, it causes frustration for people.

We want *happy* users. :slightly_smiling_face:

# Design
[design]: #detailed-design

The expectation of the users on #6237 is that exclude simply plucks the states out of everywhere they're referenced - state files, requirements, etc.

The proposal here is that we change Salt to line up with the user expectations. The way this could work is that during the `apply_exclude` process, anything that can be excluded will be removed, as if it never existed. Here is a simple example state that currently does not work:

    test1:
      test.nop

    test2:
      test.nop:
        - require:
          - test: test1

    exclude:
      - id: test1

This fails because when it tries to run test2, the require still exists, but refers to a state that is no longer there.

While there are some obvious ways to handle this case, a slightly more subtle example was also encountered:

    test1:
      test.nop

    test2:
      test.nop:
        - require_in:
          - test: test1

    exclude:
      - id: test2

In this case, it feels quite odd if you're not super familiar with the requisites because you're excluding a state, but part of that state has already affected another one.

In these cases, the behavior that Salt's users expect is that the exclude will take precedence, resulting in these states:

    test2:
      test.nop

And

    test1:
      test.nop

In order to preserve backwards compatibility, we [should make this configurable][1]. The following command line argument should be added to (TODO what cli? Also, too wordy?):

    --exclude-before-requisites

We should also add the same setting to the config files:

    exclude_before_requisites: True

When these flags are set to `True`, excludes should work as proposed. When the flags are set to `False`, current behavior should be kept, though we should add an explicit message that the exclude would remove a required state.

At first glance, it's *possible* that this code change is as simple as moving the `apply_excludes` line in `state.py` a couple of lines earlier before the `requisite_in` calls. Further tests indicate there's more considerations.

The test cases are pretty straight forward, though it's possible that it breaks some existing tests.

Test cases:

- when the flag is not set, excluding a requisite should produce a helpful error message (`'Warning: excluding {thing} that is required by {other_thing}'`, for example)
- exclude with no requires still excludes
- exclude with [each requisite](https://docs.saltstack.com/en/latest/ref/states/requisites.html#direct-requisite-and-requisite-in-types) properly excludes when the required state, or the requiring state is excluded

## Alternatives
[alternatives]: #alternatives

There are a couple of alternative approaches:

1. Do nothing - everything is fine.
2. Add documentation to either requisites and/or includes that mentions that this is considered an anti-pattern, and provide some patterns to follow for people who think they want to take this approach.
3. Codify the existing behavior by adding a proper error/exception when exclude excludes something that was required (should still require documentation updates).

## Unresolved questions
[unresolved]: #unresolved-questions

I know this applies to states - do we have similar problems when there are entire files? What about includes/requires across state files? Can pillars/grains/??? suffer from the same issues?

Are there issues with require/exclude cycles?

# Drawbacks
[drawbacks]: #drawbacks

- Implementation and opportunity cost of actually building/testing/etc.
- <strike>This could cause *serious* issues if someone excluded something that ended out having a greater impact than they thought it should have. For example, it's possible that I exclude a state that looks simple, but it ends out to have a cascading effect, eliminating half of my states. That would be undesirable.</strike> By requiring opt-in to this new behavior, it will not break any existing setups. Since we'll already be introducing some changes, we can update the existing behavior to provide a more helpful error if there is a conflict between exclude and require.


[1]: https://github.com/saltstack/salt/pull/51183#issuecomment-454646418
