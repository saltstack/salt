- Feature Name: pkg.list_pkgs new output
- Start Date: Fri 9 Feb, 2018
- RFC PR:
- Salt Issue:

# Summary
[summary]: #summary

New output structure for `pkg.list_pkgs` function.

# Motivation
[motivation]: #motivation

The function `pkg.list_pkgs` is used across different platforms with
various local peculiar qualities that affect the output in many
ways. This function has additional parameters, like `attr` or
`versions_as_list` etc that additionally changes the output structure.

The structure itself has couple of limitations that affects efficient
work through the API on a mixed environments.

The reason to reorganise this function output is to avoid these
limitations and have an efficient API workflow.

# Design
[design]: #detailed-design

### Current Design

Currently `pkg.list_pkgs` is returned as a map. Example:

```
"package-name": [
    {
        "release": "0.00",
        "install_date": "YYYY-MM-DDT00:00:00Z",
        "version": "0.0.0",
        "arch": "000",
        "install_date_time_t": 00000000000000
    }
],
...
```

The parameter `attr` can affect the amount of keys in the nested
dictionary, which is assigned to a key as the name of the package.

Issues arises when it comes to a multiple packages with the same name
and/or architecture. For example, if there is a package with the same
name, but is installed twice with a different architecture, the
architecture is prepended in ad-hoc way with a dot separator (RedHat,
SUSE, CentOS etc) or a colon (Debian, Ubuntu, Mint etc).

Take a look at this snippet of output:

```
"xz-libs.i686": [
	{
		"release": "1.el7",
		"install_date": "2017-06-24T10:51:34Z",
		"version": "5.2.2",
		"arch": "i686",
		"install_date_time_t": 1498301494
	}
],
"xz-libs": [
	{
		"release": "1.el7",
		"install_date": "2017-06-24T10:51:34Z",
		"version": "5.2.2",
		"arch": "x86_64",
		"install_date_time_t": 1498301494
	}
	],
...
```

Package `xz-libs` is installed twice with the same exact version,
except the difference is that it has a different architecture
available on the same hardware. Since all the fields in the nested
dictionary except the version are optional as well as the structure
requires a unique key for mapping, the architecture is prepended to
the name with the `.` (dot) delimeter. Such output is only valid on
RPM-based systems (SUSE, RedHat, CentOS etc). On systems, based on
dpkg/deb (Debian, Ubuntu, Mint etc) the delimeter is a `:` (colon),
since dot can be in the name.

Once this API is used programmatically against the mixed environments,
this leads to the following problems:

- API caller should already know what system it is targeting (is this
  RPM based or not). Unless this information is already known, another
  additional call for grains is required.

- The format is not the same across all the distributions and
  operating systems, while it should be.

- The fact that it is built on top of the mapping on top of keys as
  the name already brings by-design limitaions for the packages with
  the same name. To overcome it -- an architecture prepending.

- No guarantee that there will not be any dots or colons in the names
  in a future in _any possible_ distribution.

Additionally, the format is a "moving target" and is transforming from
one to another way. Some values can be a string, but sometimes a
list. In some cases list is not really a list, but a comma-separated
string... Example:

```
"kernel-default": "4.4.103-92.56.1,4.4.21-69.1",
```

This is equal to the following output with just `attr=version,release`
parameters:

```
"kernel-default": [
	{
		"release": "92.56.1",
		"version": "4.4.103"
	},
	{
		"release": "69.1",
		"version": "4.4.21"
	}
], 
```

Expanded example:

```
"kernel": [
	{
		"release": "693.2.2.el7",
		"install_date": "2017-10-03T14:23:59Z",
		"version": "3.10.0",
		"arch": "x86_64",
		"install_date_time_t": 1507040639
	},
	{
		"release": "693.11.6.el7",
		"install_date": "2018-01-15T14:13:44Z",
		"version": "3.10.0",
		"arch": "x86_64",
		"install_date_time_t": 1516025624
	},
	{
		"release": "693.1.1.el7",
		"install_date": "2017-10-03T14:21:47Z",
		"version": "3.10.0",
		"arch": "x86_64",
		"install_date_time_t": 1507040507
	}
],
...	
```

So obviously API consumer should _know ahead_ the following properties
of the called system:

- Distribution
- Version format
- Parsing options on the client side

### Proposed Design

Proposed change is to follow _any_ Package Manager spirit: just return
a list of packages. The new approach seeing the current re-mixing such
list into a map only as a (custom/app)-level format and actually
avoids this.

Structural example would be as follows:

```
[
	{
		"name": "package-name",
		"key": "value",
	}
]
```

That is, it would be just a list of dictionaries with the standard
keys inside. Reworked output from the examples above would be like
this:

```
[
	{
		"name": "xz-libs",
		"release": "1.el7",
		"install_date": "2017-06-24T10:51:34Z",
		"version": "5.2.2",
		"arch": "i686",
		"install_date_time_t": 1498301494
	},
	{
		"name": "xz-libs",
		"release": "1.el7",
		"install_date": "2017-06-24T10:51:34Z",
		"version": "5.2.2",
		"arch": "x86_64",
		"install_date_time_t": 1498302356
	}
],

```

In case with the less attributes as follows:

```
[
	{
		"name": "kernel-default",
		"release": "92.56.1",
		"version": "4.4.103"
	},
	{
		"name": "kernel-default",
		"release": "69.1",
		"version": "4.4.21"
	}
], 

```

This would by design invalidate all the issues with the naming,
architecture and parsing all that accordingly. API consumer do not
need anymore what exactly system it works with, as there would be a
standard format across everywhere.

The rest of the functinality would stay the same.

### Notes

Important to have a common validator decorator that would make sure
_all the keys_ are always the same across all the operating systems.

## Alternatives
[alternatives]: #alternatives

Alternatively it would be possible to just add parameter `delimeter`
to the existing code and so the API consumer would not need to know
which system it is talking to, in order to separate prepended part
(architecture). For example, add a `/` (slash), so the return is like:

```
"xz-libs/i686": ....
"xz-libs": ....
```

However, this does not solve two issues:

1. There is no mention in the name what is the default architecture,
   unless explicitly requested, since prepended architecture is only
   different from the default. We only _assume_ that _most of the
   time_ it is `x86_64` architecture which is capable running `i686`
   or older.

2. It is still needs to know there were no slashes introduced in the
   naming of the packages to that particular operating system flavour.

3. It will likely lead to a funny random delimeters.

All this more like a workaround of the problem, instead of actally
solving it.

## Unresolved questions
[unresolved]: #unresolved-questions

N/A

# Drawbacks
[drawbacks]: #drawbacks

- This change should not go to the prepared Oxygen release, but only in
`develop` branch.

- Implementation should be done using deprecation model system
  (decorators we already have in Salt core).

- The old version should stay for two releases (standard retention time)

- Systems that want new version should turn it on in the Minion
  config: `use_superceded: modules.pkg.list_pkgs`

