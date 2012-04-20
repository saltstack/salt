==================
Salt Stack Roadmap
==================

Salt is the core of a more complete goal, the Salt Stack. The Salt Stack is a
complete infrastructure management system which is comprised of many
components all functioning on top of Salt.

The majority of the functionality of the Salt Stack happens directly inside
Salt, but the information derived from Salt needs to be used to create a
transparent view of the infrastructure as a whole.

The information used in Salt States will be matched via a higher interface
and the low salt data will be visualized. This will allow the state data to
appear in the web interface.

The features listed here are only listed based on major version releases, the
plan is to have a clear long term goal but not to overly dictate the flow
of development. The project needs to be flexible enough to be able to receive
new features at a moment's notice. This model should spur ideas and make
allowing new community developers to join without issue. So just because
something is slated for a later reason does not mean that a developer is
going to have their code rejected or stalled.

1.0.0
=====

1.0.0 requires that remote execution is stable and that states are ready to
complete. We mostly just need to clean things up for 1.0.0.

Clean up code base
------------------

Go through the code, clean up PEP 8 violations and make sure we have
Python 3 compatible code.

Module Cross Calls
``````````````````

Many instances of using functions when we should be using module cross calls
exist in the code. Mostly from modules which were written before cross calls
were around. The big thing to look for are subprocess calls, since they should
all be running with the cmd module.

State Return Data Cleanup
`````````````````````````

The return structures in the state modules need to be uniform in how they are
declared, before we get too much of a following we should have as consistent
modules as possible. We want to hit the gate with very clean code!

States and Modules
------------------

More states need to be available.

User State
``````````

The user state needs to be expanded to support password setting and managing
the finger component

Clean up Bugs
-------------

We are finding a number of bugs in the new state system as we get more testers
there are a few bugs that been attention:

#66

We need to keep pushing through testing states on live systems and find as
many bugs as possible before 1.0, we have found too many 0 day bugs.

Documentation
-------------

The documentation has gotten a LOT better, but we still need more work in a
few places

Clean up formatting
```````````````````

The 1.0 PDF needs to be a document that we can publish to the world with pride

Expand the State Tutorial
`````````````````````````

We are learning a lot about how to teach states, we need to take this knowledge
and improve the states tutorial. We want people to be able to get going with
states in no time at all

Module Built in Docs
````````````````````
Double check all of the module built in docs for consistency. Make sure things
are clear and accurate.

Proposal System
---------------

I would like to have a proposal system in place for Salt, so that
community members can submit proposals for feature development for
review. Using Github's new issue system with support for tags
(blocker, feature...) seems like a good choice.

Workflow
--------

Gitflow not only makes for a good branching model everybody can
understand and work with but also scales well and just works (tm).
Let's start using it!

2.0.0
=====

2.0.0 will require a number of serious additions and overhauls. We wand to make
the transport layer much cleaner and clean up the crypto dependencies.
Figure out how to get more speed out of Salt and make it more memory
efficient. The security system needs some additions to make it more
secure.

There are also a number of features that should be pulled out of their classes
and made to stand alone. Also we want to MASSIVELY improve platform support and
module/state penetration.

This is only a subset of what we can expect 2.0.0 to be!

With 1.0.0 salt is a great option, with 2.0.0, using anything else is just plain
dumb!

Python 3 Support
----------------

The goal so far has been to write Salt with 3.0 in mind, but with 2.0
we want it to be a reality. This will mostly require that the
requirements are met.

Refine Security
---------------

Make the iv explicit
````````````````````

Right now the iv is implied by the length of the AES key, we want the iv to be
randomly applied and sent with the AES key.

Master Signatures
``````````````````

There is a theoretical vulnerability in the validation of transit messages, they
need to have a master private key signature somewhere.

Change Network Serialization
````````````````````````````

Right now it is pickle, this needs to be changed to something more
standard like JSON or maybe even something simpler/faster such as
tnetstrings as used by Mongrel2. We also need to change how messages
are formatted to speed up the serialization and lower network usage
more. A new model will be proposed.

State Generator
---------------

Since the state system is based on data structures we can generate them from
a uniform API, this needs to be available in renderer modules.

Separate out the File Server
----------------------------

Te built in file server should be less built in. We will make a standalone file
server from the existing built in one that is more powerful and can be used
with and without encryption and authentication. The updated file server should
also be faster, so that large files can be downloaded more quickly.

The salt-cp command needs to be moved to use the file server as well, so that
it can be used to copy large files as well.

Support for more Platforms
--------------------------

Platform support means a few things, primarily that we have support for the major
modules pertinent to the platforms and that Salt will run on these platforms at
least as a minion.

Solaris
Gentoo
Suse
Slackware
OpenBSD
NetBSD
AIX
HPUX
Windows

Language Library Modules and States
------------------------------------

Modules and States that support installing programming language packages.
Here is the list to start with:

pypi
rubygem
cpan
lua
haskell?

Firewall Support
----------------

This is going to be rather serious, this is a collection of modules for
iptables, pf, and the subsequent subsystems for other platforms. But in the
end, we want seamless firewall support for at least opening up ports for
services.

Advanced Grains
---------------

The grains system still needs an overhaul, the problem is that grains should
have access to each other, but they should still only be run once. Some plans
are in place to pull this off, but they need to be implemented.

More Renderers!
---------------

The renderer system needs to support more templating engines and language
bindings. Adding support for XML, Cheetah, Tenjin etc. will be simple. But
the main goal here is to allow sls files to be written in Ruby, Lua, Perl or
basically anything.

Unit Tests
----------

Need unit tests in place for everything, we are planning on using
Unittest2 and pytest.
