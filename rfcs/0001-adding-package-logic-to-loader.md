- Feature Name: adding_package_logic_to_loader
- Start Date: 2018-06-29
- RFC PR:
- Salt Issue:

# Summary
[summary]: #summary

The loader is kind of dumb, and has no sense of heirarchy for modules other than the order that is hard coded into `_module_dirs`.  Salt should be able to be more configurable over what should be loaded.

# Motivation
[motivation]: #motivation

Salt has a ton of modules to load.  Not all of those modules belong in the main releases of Salt, which slows down the our ability to make releases for stuff that is essential, like a new release of Tornado or fixing other bugs in the internals of Salt, because all of the tests for the modules also need to pass.

The eventual goal is to be able to move modules out of the core of salt into other packages but in order to do that, salt needs to be able to determine the heirarchy of modules for these different modules.

# Design
[design]: #detailed-design

Right now, Salt creates a list of of directories using `salt.loader._module_dirs` and passes it to the LazyLoader to load search for those modules when they are being called.  These modules should be "tagged" with which package they are from, or how they are loaded.  The packages and modules should also be assigned priorities so that the order to load them can be declared.

- core salt modules
  - Priority 1
  - These are the first modules to be loaded, everything else can overwrite them.
- Python package modules
  - Priority 2-9
  - Salt provided package modules
  - The priority isn't really important here, we should probably have them all set as a 2, and just maintain that no two modules can have the same name in this space.
- extmod dynamic module directories
  - Priority: 10-19
  - This would be the priority for any of the _modules directories, and spm packages would fit in here somewhere.
- Other Packages
  - Priority: 20-98
  - These would be community/user provided packages

There should not be any complexity to add this to existing Salt Setups, because it should still be the same interface to interact with the modules once they are loaded from the loader.  Though, the ability to specify the package to use the module from should be added.  `<package>:<module>.<func>` instead of just `<module>.<func>` like we currently do, but that format should not be required.

## Alternatives
[alternatives]: #alternatives

We have not discussed any other alternatives to making the loader aware of packages.

## Unresolved questions
[unresolved]: #unresolved-questions

# Drawbacks
[drawbacks]: #drawbacks

- This will add some complexity to the Loader, just because the different packages have to be handled.
- This will almost certainly add some time to the loader for loading the modules, but it should be negligible, as it should just be new directories to look in, and most of the cost should just be upfront when starting the salt-minion.
