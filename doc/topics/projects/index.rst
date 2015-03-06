===================
Salt Based Projects
===================

A number of unofficial open source projects, based on Salt, or written to
enhance Salt have been created.

Salt Sandbox
============

Created by Aaron Bull Schaefer, aka "elasticdog".

https://github.com/elasticdog/salt-sandbox

Salt Sandbox is a multi-VM Vagrant-based Salt development environment used
for creating and testing new Salt state modules outside of your production
environment. It's also a great way to learn firsthand about Salt and its
remote execution capabilities.

Salt Sandbox will set up three separate virtual machines:

- salt.example.com - the Salt master server
- minion1.example.com - the first Salt minion machine
- minion2.example.com - the second Salt minion machine

These VMs can be used in conjunction to segregate and test your modules based
on node groups, top file environments, grain values, etc. You can even test
modules on different Linux distributions or release versions to better match
your production infrastructure.