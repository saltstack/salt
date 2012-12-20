==============================
Introduction to Extending Salt
==============================

Salt is made to be used, and made to be extended. The primary goal of Salt is
to provide a foundation which can be used to solve problems. And the goal of
Salt is to not assume what those problems might be.

One of the greatest benefit of developing Salt has been the vast array of ways
in which people have wanted to use it, while the original intention was as a
communication layer for a cloud controller Salt has been extended to facilitate
so much more.

Client API
----------

The primary interface used to extend Salt, is to simply use it. Salt executions
can be called via the Salt client api, making programming master side solutions
with Salt is easy.

Adding Loadable Plugins
-----------------------

Salt is comprised of a core platform that loads many types of easy to write
plugins. The idea is to enable all of the breaking points in the Salt processes
to have a point of pluggable interaction. This means that all of the main
features of Salt can be extended, modified or used.

The breaking points and helping interfaces span from convenience master side
executions to manipulating the flow of how data is handled by Salt.

Minion Execution Modules
````````````````````````

The minion execution modules or just ``modules`` are the core to what Salt is
and does. These modules are found in:

:blob:`salt/modules`

These modules are what is called by the Salt command line and the salt client
API. Adding modules is done by simply adding additional Python modules to the
*modules* directory and restarting the minion.

Grains
``````

Salt grains, or "grains of truth" are bits of static information that are
generated when the minion starts. This information is useful when determining
what package manager to default to, or where certain configuration files are
stored on the minion.

The Salt grains are the interface used for auto detection and dynamic assignment
of execution modules and types to specific Salt minions.

The code used to generate the Salt grains can be found here:

:blob:`salt/grains`

States
``````

Salt supports state enforcement, this makes Salt a high speed and very efficient
solution for system configuration management.

States can be easily added to Salt by dropping a new state module in:

:blob:`salt/states`

Renderers
`````````

Salt states are controlled by simple data structures, these structures can be
abstracted in a number of ways. While the default is to be in a yaml file
wrapped in a jinja template, any abstraction can be used. This means that any
format that can be dreamed is possible, so long as a renderer is written for
it.

The existing renderers can be found here:

:blob:`salt/renderers`

Returners
`````````

The Salt commands all produce a return value, that return value is sent to the
Salt master by default, but it can be sent anywhere. The returner interface
makes it programmatically possible for the information to be sent to anything
from an SQL or NoSQL database, to a custom application made to use Salt.

The existing returners can be found here:

:blob:`salt/returners`

Runners
```````

Sometimes a certain application can be made to execute and run from the
existing Salt command line. This is where the Salt runners come into play.
The Salt Runners what is called by the Salt-run command and are meant to
act as a generic interface for encapsulating master side executions.

Existing Salt runners are located here:

:blob:`salt/runners`
