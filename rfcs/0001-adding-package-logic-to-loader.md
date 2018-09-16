- Feature Name: adding_python_package_logic_to_loader
- Start Date: 2018-06-29
- RFC PR:
- Salt Issue:

# Summary
[summary]: #summary

Add support for python packages to the loader. Instead of just having
apache.py, we would have `salt/modules/apache/__init__.py`, and all the other
modules under that directory loaded in the `apache.<function>` namespace that
we already have.

# Motivation
[motivation]: #motivation

Split modules out into different git repositories, and allow the community more control to help maintain them.

# Design
[design]: #detailed-design

This should be pretty straight forward, we should be able to use the same
_module_dirs that we are using now, and iterate over the files, and if they are
a directory, then we load all of the modules underneath it into the namespace
of the directory.

Heirarchy would be alphabetical, and we would need to log messages if the
function exists in an earlier file that has been loaded.

## Alternatives
[alternatives]: #alternatives

## Unresolved questions
[unresolved]: #unresolved-questions

# Drawbacks
[drawbacks]: #drawbacks
