- Feature Name: Sunset Legacy Python 2 Support
- Start Date: 2019-01-04
- RFC PR: (leave this empty)
- Salt Issue: (leave this empty)

# Summary
[summary]: #summary

SaltStack is phasing out Python 2 support, with the develop branch of Salt Open
dropping Python 2 support effective immediately.

We will continue our policy of backporting bug fixes and security patches for
the last two releases, but starting with release (???) we will no longer
support legacy Python versions. For SaltStack, this means we will support
&gt;=Python 3.6.

Previous versions of SaltStack, that are able to run on legacy versions of
Python will continue to be available on http://repo.saltstack.com as well as
https://pypi.org.

Older platforms without native Python 3 packages (e.g. RedHat) will be provided SaltStack
packages that include Python 3.

# Motivation
[motivation]: #motivation

## Python 2 EOL

Python 2 will no longer be [officially supported][1] as of [January 1,
2020][2]. As an organization, we cannot in good faith continue supporting
Python 2 - any lingering bugs in unsupported Python versions could cause
problems with SaltStack, and thus, our users.

## Python 3

### New Features!

By eliminating Python 2 support, it means we will be able to take advantage of
modern Python features, like async/await, async generators, and asyncio (or
other async frameworks).

Additionally, all improvements to the Python language (speed, additional
features, etc.) will come to Python 3. By dropping Python 2 support, SaltStack
users will benefit from these improvements simply by keeping their Python
installation up-to-date.

### Simplify

In addition to the performance benefits, the modern Python features should
allow us to simplify our codebase. As SaltStack internally supports Python 3
already, this simplification includes the ability to eliminate our dependency
on [six][3].

Additionally, but having only Python 3 to support, we significantly decrease
the time it takes to run our tests (having only one version of the language to
run tests against). It also reduces the mental overhead of having to consider
multiple Python versions when writing code.

### Python 3 Minimum Version

In order to take advantage of the new features in Python 3, SaltStack's
baseline version of Python will be Python 3.6.

### Availability

In the past, native Python 3 packages were difficult to find - one usually
needed to compile it themselves. That has changed now with all modern OSes
shipping Python 3.

## Alternatives
[alternatives]: #alternatives

For those who are stuck with Python 2:

- Previous versions of SaltStack, with Python 2 support, will continue to be
  available on http://repo.saltstack.com, as well as https://pypi.org
- Enterprise SaltStack customers will be able to make special arrangements to
  continue to receive Python 2 support for certain platforms.

If SaltStack continues to bridge Python 2 and 3 we will continue to incur the
significant costs associated with maintaining and testing the combined
codebase. We will also suffer the opportunity cost of not being able to take
advantage of the more modern features being introduced with new Python 3
versions.

# Drawbacks
[drawbacks]: #drawbacks

This is a significant breaking change - many installations are on older
platforms, and some may have an inclination to not upgrade their systems.
Though this may be the tipping point that gives them the impetus to upgrade to
a more modern OS.

# Thank You, Python 2

It wouldn't be right to drop support Python 2 without first saying a hearty,
"Thank you!"

Python 2 was a wonderful language to program in, and has brought us all much
joy and success. Though newer versions of SaltStack will no longer run on
Python 2, we will all have fond memories of the improvements it made in our
life, and the improvements it allowed us to make in the lives of those around
us.

Python 2, so long, and thanks for all the fish!


[1]: https://www.python.org/dev/peps/pep-0373/#maintenance-releases
[2]: https://pythonclock.org/
[3]: https://pypi.org/project/six/
