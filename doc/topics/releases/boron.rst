===================================
Salt Release Notes - Codename Boron
===================================

Core Changes
============

- The onchanges requisite now fires if _any_ watched state changes. Refs #19592.


Cloud Changes
=============

- Refactored the OpenNebula driver and added numerous ``--function``s and ``--action``s to enhance Salt support for
  image, template, security group, virtual network and virtual machine management in OpenNebula.
