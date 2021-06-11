# What is this directory?

This directory contains python scripts which should be called by [invoke](https://pypi.org/project/invoke).

Instead of having several multi-purpose python scripts scatered through multiple paths in the salt code base,
we will now concentrate them under an invoke task.

## Calling Invoke

Invoke can be called in the following ways.

### Installed system-wide

If invoke is installed system-wide, be sure you also have `blessings` installed if you want coloured output, although
it's not a hard requirement.

```
inv docs.check
```

### Using Nox

Since salt already uses nox, and nox manages virtual environments and respective requirements, calling invoke is as
simple as:

```
nox -e invoke -- docs.check
```
