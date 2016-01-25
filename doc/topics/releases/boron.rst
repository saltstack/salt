:orphan:

===================================
Salt Release Notes - Codename Boron
===================================

Core Changes
============

- The onchanges requisite now fires if _any_ watched state changes. Refs #19592.
- The ``ext_pillar`` functions **must** now accept a minion ID as the first 
  argument. This stops the deprecation path started in Salt 0.17.x. Before this 
  minion ID first argument was introduced, the minion ID could be retrieved 
  accessing ``__opts__['id']`` loosing the reference to the master ID initially 
  set in opts. This is no longer the case, ``__opts__['id']`` will be kept as 
  the master ID.


Cloud Changes
=============

- Refactored the OpenNebula driver and added numerous ``--function``s and ``--action``s to enhance Salt support for
  image, template, security group, virtual network and virtual machine management in OpenNebula.
