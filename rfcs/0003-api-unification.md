- Feature Name: API interface
- Start Date: 2018-10-30)
- RFC PR:
- Salt Issue:

# Summary
[summary]: #summary

Modules with `__virtual__` should yield to the common interface.

# Motivation
[motivation]: #motivation

Virtual modules behaves differently on different Linux distributions
and different operating systems. So if one is query `pkg` module, on
one system there is `lock` package, on other is `hold` package, on
another this feature is not even there. And so on...

To solve this chaos, virtual modules, that represents a module per se,
should also have the same standard interface. So we no longer have a
module that is _called_ differently on different operating systems,
however we will have a module that _reports_ differently on
heterogeneous environments.


# Design
[design]: #detailed-design

Interface is a list of functions in the module and is to make sure
that any virtual module is always called exactly the same, regardless
what operating system minion is running on.

Interface does not define the function output format. It only defines
the name of the function and its signature.


## Declaration

Salt interfaces are declared just as classes. Salt's module to
functions is Salt's interface to methods. Therefore `self` in the
class is not a part of a function signature. Example:

```
from salt.interfaces import Interface

class PkgInterface(Interface):
    def list_installed(self, *names, **kwargs):
        '''
	    List installed packages.
	    '''

    def upgrade_available(self, name, **kwargs):
        '''
        List available upgrades.
		'''
```

Basically, the list of methods should reflect exact names and
signatures as in the module, except `self` parameter.


## Usage

Since Salt calls functions from the modules, therefore the interface
can be run inside the module on `__virtual__` function as follows:

```
from salt.interfaces.pkg_module import PkgInterface


def __virtual__():
	PkgInterface(__name__)()
    ...
```
This should be that simple.


## Effect

What PkgInterface does in the example above, it takes the current
module and examines if the exported functions are there. Once nothing
found, a stub is placed. That means, if module `pkg` requires,
e.g. function `lock` and there is implemented `hold`, then function
`lock`will be _also_ added. But if this function is called, it will
raise an error "Function is not implemented yet" (different exception
type from "function not found").

But the interface will also mark existing functions that are not
inside the interface as subject to retirement, by automatically
placing a warning decorator to them. That said, if an interface class
does not implement `hold` function, but that function is still
implemented, using that function will also raise a warning in the log
file that this function is deprecated and is subject to be removed in
a future.


## Not applicable functions

On some operating systems certain functions aren't applicable. In this
case they should be decorated with the proposed function decorator:

```
class SomeModuleInterface(Interface):
    @Interface.not_applicable('Windows', 'NetBSD')
    def foo(self, name, *args):
	    pass
```

In this case method `foo` will be still added on Windows and NetBSD
minions, however it will only return `False` and debug log will inform
that not applicable function has been called.

## Unresolved questions
[unresolved]: #unresolved-questions

Which path do we choose here to make sure interface is used all the time?


### Easy implementation

Just _force_ the interface over _every_ module that implements
`__virtualname__`. As long as `__virtualname__` is there and no
interface -- such module is rejected to be loaded. Period. Drawback
here is that we will need to write an interface for every module with
the `__virtualname__` if it is used merely to rename the
module. However, writing an interface also does not have to be a
problem: it is merely to copy function signatures. To generate
an interface out of the signatures of some package, it is just enough
to take a reference package and do something like this: 


    cat zypper.py | grep '^def [a-z]' | sed -e 's/(/(self, /g' | sed -e 's/def/    def/g'


It will create ready to copy interface, to which only `pass` needs
to be added after each line. The `Interface` class, from which
`PkgInterface` class is subclassed will alter its code so every time
one is calling any method from the `PkgInterface` directly, will raise
an exception "Function is not yet implemented".


### Not so easy implementation

It includes easy implementation from the above, plus some extra
work. The easy implementation just bluntly forcing the interface
requirement. In this case this is happening only if module with
`__virtualname__` is using more than once. But that should be verified
at Salt component startup. As long as there is a module that has no
interface but has the same `__virtualname__` twice or more, such
module is blacklisted for EasyLoader in future calls.


# Drawbacks
[drawbacks]: #drawbacks

Implementation of another sibling module will be a bit more complex.
