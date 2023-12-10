- Feature Name: API interface
- Start Date: 2018-10-30)
- RFC PR:
- Salt Issue:

# Summary
[summary]: #summary

Salt Module Interface (SMI) concept introduction for virtual modules.

# Motivation
[motivation]: #motivation

Any salt module has couple of specific properties we dealing every day
with:

- Fixed set of functions
- Known functions signatures
- Known structure of return

This is true but for virtual modules. The virtual module covering
several "fixed" or "physical" modules and behaves like that would be
one module. But differences between those physical modules on
different platforms makes such virtual module a moving target and
unpredictable.

Virtual modules concept is missing crucial part in the design:
interfaces. The interface should define how module looks like and what
APIs can be called to it. Interface should move module that is
_called_ differently on heterogeneous environments to a module that
_reports_ differently on heterogeneous environments.


# Design
[design]: #detailed-design

*DISCLAIMER*: The SMI is not that classic understanding of typical
interface one may find in languages like Java. It is also not as same
as Zope Interface package or Python Abstract Base Classes (ABC).

The SMI should describe the following properties of the module:

- Functions
- Signatures
- Lowest common denominator of the function output format (or minimum
  required default output structure)

SMI only describes functions of the module and is there to make sure
that any virtual module is always called exactly the same way, regardless
what operating system minion is running on.

## Declaration
[declaration]: #declaration

SMI are declared just as regular Python classes. Salt's "module to
functions" map is Salt's "interface to methods" map. Therefore `self`
parameter in the SMI class is not a part of a function signature.

Example of SMI definition for module `pkg`:

```python
from salt.interfaces import Interface

class PkgInterface(Interface):
    __modulename__ = 'pkg'

    def list_installed(self, *names, **kwargs):
        '''
	    List installed packages.
	    '''
        return {}

    def upgrade_available(self, name, **kwargs):
        '''
        List available upgrades.
		'''
        return {}

    @Interface.supported(os=['weirdlinux', 'beos', 'frogbsd'], os_family=['linux'])
    def salute_fireworks(self, name):
        '''
        Launch some fireworks
        '''
        return {}
```

In above incomplete interface example, the list of methods should
reflect exact names and signatures as in the module, except `self`
parameter. Rules apply:

- If a method is not in the SMI class, but function is implemented in
  the module, then such function is marked as "deprecated".

- If a method is in the SMI class but not in the module, then such
  function is marked as "not implemented".

- If a method has a decorator `@Interface.supported`, only on specified
  systems unimplemented method will be reported as "not
  implemented", otherwise "not supported". This decorator accepts
  any grains possible. It then matches them if _any_ specified grain
  is in proposed lists. From the example above, missing
  `salute_fireworks` will be reported as "not implemented" if
  `os_family` grain equals `linux` **or** `os` grain equals
  `weirdlinux` or `beos` or `frogbsd`.



## Usage
[usage]: #usage

Once SMI class defined, the usage should be very simple:

```python
from salt.interfaces.pkg_module import PkgInterface

__virtualname__ = PkgInterface(__name__)()

```

The code above does the following:

- Ensures that the `__virtualname__` is properly set according to the
  interface.
- Performs check for the entire module and automatically unifies it to
  the rules in the "Declaration" section above by adding stub
  functions that would raise corresponding exceptions or wrap/decorate
  existing "illegal" functions as "deprecated".


## Effect
[effect]: #effect

Essentially, the SMI works as automatic checker/corrector for the
module on the moment it is lazy-loaded.

What PkgInterface does in the example above, it takes the current
module and examines if the exported functions are there. Once nothing
found, a stub is placed. That means, if module `pkg` requires,
e.g. function `lock` and there is implemented `hold`, then function
`lock`will be _also_ added as "not implemented" (or "unsupported",
depends on decorator in the Interface declaration).

SMI will also mark existing functions that are not inside the
interface as subject to retirement, by automatically placing a warning
decorator to them. That said, if an interface class does not describes
`hold` function, but that function is still physically implemented,
calling that function will also raise a warning in the log file that
this function is deprecated and is subject to be removed in a future.


## Not applicable functions
[notapplicable]: #notapplicable

On some operating systems certain functions aren't applicable. In this
case they should be decorated with the proposed function decorator:

```python
class SomeModuleInterface(Interface):
    @Interface.not_applicable(osfamily=['Windows', 'NetBSD'])
    def foo(self, name, *args):
        return {}
```

The decorator would support _any_ kind of grains keys with any of the
values to compare with. Once certain grain matches in the list of the
given values, decorator is triggered.

In this case method `foo` will be still added on Windows and NetBSD
minions, despite the fact that the code below adds it only on RedHat
Linux. However it will only return specified structure and debug log
will inform that not applicable function has been called.

Such decorator deals with the cases, where function is being added to
the module only on certain conditions, e.g.:

```python
if __grains__['osfamily'] == 'RedHat':
    def foo(name, *args):
        return {}
```

## Return Structure Definition
[returnstruct]: #returnstruct

Return structure in virtual modules is another pitfall. Dynamically
replaced module suddenly renders virtual module to return "something else"
than is usually expected. This is widely affects API and integration.
To the only way to avoid this, is to know what kind of platform minion
is dealing with. In this case integration code usually looks like
this (pseudo-code):

```
if this_is_debian {
  function_call({'disabled': False})
else {
  function_call({'enabled': True})
}
```

There is a catch: some operating systems/platforms _must_ return
specific properties that aren't available on other systems. Therefore
return structure should be always defined from two blocks:

- *Minimal common data.* This comes from every platform, even if this is
  only one value. This data should be available on _all Salt
  supported_ platforms. This group must be defined in the Interface.
- *Extra specific data.* This comes from a specific platform that
  is not be available on _all other_ platforms, even if this data might
  be _also available_ on other platforms. This group is always
  coming additionally to the basic one and is _not_ part of the interface.

SMI class should define return structure from the defined method. This
structure is very similar to `config/__init__.py::_validate_opts()`
function.

SMI also should take care of return structure definition so all virtual
modules returns by default the same structure.

However, the migration and adoption of the same structure from
different physical modules is not easy. Modules are also called
through the states and there is already specific structure is
used. The usage would not change, but the implementation would be to
wrap all functions with a decorator, which would validate the default
output.

This RFC is not to cover the detailed output structure part, but only
foresee a placeholder for it the in current design of the Interface
concept.

## Unresolved questions and known possible solutions
[unresolved]: #unresolved-questions

- Should be confugrable function deprecation while aligning module with the interface?

If some function happens to be an alien to the interface, question is
how to react on this. Muting and do not report function is obsolete is
still asking for a problem. Because if we know that in N
years/releases function is going to be retired, simply just do not use
it or move away from it. But if this is configured and can be muted,
such option will bring more harm than help.

- Which path do we choose here to make sure interface is used all the time?

One of the possibility is to expect Interface class instance in
`__virtualname__` variable, instead of a string. In this case
`__call__` is not performed right in the module, but LazyLoader
instead gets the `__modulename__` variable content.

Another possibility is to adjust PyLint to it and make sure each
`__virtualname__` has Interface assigned instead of a string.

Alternatively, not to force Interface usage. But this has drawback of
setting the interface overall optional, which will eventually be optional
everywhere, unfortunately.


## Hints
[hints]: #hints

To generate an interface out of the signatures of some package, it is
just enough to take a reference package and do something like this:


    cat zypper.py | grep '^def [a-z]' | sed -e 's/(/(self, /g' | sed -e 's/def/    def/g'


It will create ready to copy signatures, based on `zypper.py` as a reference.


# Strategy
[strategy]: #strategy

Implementation of this concept must be done in two phases:

1. Implementation of the very mechanism.
2. Migrating module by module in a transparent way.

On the second phrase corner cases might force the implementation
details to be minor changed. The result, however should be the same:
modules should just work as they worked before while used in real systems.

The structure definition and migration should be done as well
gradually. This should be covered in a separate RFC.
