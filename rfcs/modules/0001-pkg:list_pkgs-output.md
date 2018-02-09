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

This is the bulk of the RFC. Explain the design in enough detail for somebody familiar
with the product to understand, and for somebody familiar with the internals to implement. It should include:

- Definition of any new terminology
- Examples of how the feature is used.
- Corner-cases
- A basic code example in case the proposal involves a new or changed API
- Outline of a test plan for this feature. How do you plan to test it? Can it be automated?

## Alternatives
[alternatives]: #alternatives

What other designs have been considered? What is the impact of not doing this?

## Unresolved questions
[unresolved]: #unresolved-questions

What parts of the design are still TBD?

# Drawbacks
[drawbacks]: #drawbacks

Why should we *not* do this? Please consider:

- Implementation cost, both in term of code size and complexity
- Integration of this feature with other existing and planned features
- Cost of migrating existing Salt setups (is it a breaking change?)
- Documentation (would Salt documentation need to be re-organized or altered?)


There are tradeoffs to choosing any path. Attempt to identify them here.
