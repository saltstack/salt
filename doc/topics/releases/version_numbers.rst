:orphan:

.. _version-numbers:

===============
Version Numbers
===============

Salt uses a date based system for version numbers. Version numbers are in the
format ``YYYY.MM.R``. The year (``YYYY``) and month (``MM``) reflect when the
release was created. The bugfix release number (``R``) increments within that
feature release.

.. note:: Prior to the ``2014.1.0`` release, the typical semantic versioning was
   still being used. Because of the rolling nature of the project, this did not
   make sense. The ``0.17`` release was the last of that style.

Code Names
----------

To distinguish future releases from the current release, code names are used.
The periodic table is used to derive the next codename. The first release in
the date based system was code named ``Hydrogen``, each subsequent release will
go to the next `atomic number <https://en.wikipedia.org/wiki/List_of_elements>`.

Assigned codenames:

- Hydrogen: ``2014.1.0``
- Helium: ``2014.7.0``
- Lithium: ``2015.5.0``
- Beryllium: ``2015.8.0``
- Boron: ``2016.3.0``
- Carbon: ``2016.11.0``
- Nitrogen: ``TBD``
- Oxygen: ``TBD``

Example
-------

An example might help clarify how this all works.

It is the year ``2020`` and the current code name is ``Iodine``. A release is ready
to be cut and the month is ``June``. This would make the new release number
``2020.6.0``. After three bug fix releases, the release number would be
``2020.6.3``.

After the release is cut, new features would be worked on under the ``Xenon``
code name and the process repeats itself.


Version numbers, Git and salt --version
-------
The salt version, for programmers, is based on `git describe` and presented to end-users with `salt --version`.

Example arguments for `git checkout`
  +------------+----------------------------------------------------------------------------+
  |  Argument  |                                           Comment                          |
  +============+============================================================================+
  | develop    | **Develop branch** Actively developed new features                         |
  +------------+----------------------------------------------------------------------------+
  | 2016.11    | **Release branch** Actively developed bug-fixes for 2016.11.* releases     |
  +------------+----------------------------------------------------------------------------+
  | v2016.11   | Tag signaling the commit that the 2016.11.* releases are based on.         |
  +------------+----------------------------------------------------------------------------+
  | v2016.11.1 | Tag signaling the commit that the 2016.11.1 release is based on.           |
  +------------+----------------------------------------------------------------------------+
  
Further reading on `release branch and develop branch 
<https://docs.saltstack.com/en/latest/topics/development/contributing.html#which-salt-branch>`_.
  
Influence of the `git checkout` argument on `git describe`
  +------------+----------------------------+-----------------------------------------------+
  | Checkout   | Describe                   |               Comment                         |
  +============+============================+===============================================+
  | v2016.11   | v2016.11                   | (tag is fixed point in time)                  |
  +------------+----------------------------+-----------------------------------------------+
  | 2016.11    | v2016.11.1-220-g9a1550d    | Commit of most recent tag in 2016.11          |
  +------------+----------------------------+-----------------------------------------------+
  | v2016.11.1 | 2016.11.1                  | (tag is fixed point in time)                  |
  +------------+----------------------------+-----------------------------------------------+
  | develop    | v2016.11.1-1741-g10d5dec   | Commit of most recent tag in develop          |
  +------------+----------------------------+-----------------------------------------------+
    
  

Some details of v2016.11.1-220-g9a1550d (from `git describe` after `git checkout 2016.11`)
  +---------------+-------------------------------------------------------------------------+
  |     Part      |                       Comment                                           |
  +===============+=========================================================================+
  |v2016.11.1     | git describe finds the most recent tag on the 2016.11 branch            |
  +---------------+-------------------------------------------------------------------------+
  |220            | Commits on top of the most recent tag, relative to your local git fetch |
  +---------------+-------------------------------------------------------------------------+
  |gf2eb3dc       | 'g' + git SHA ("abbreviated name") of the most recent commit            |
  +---------------+-------------------------------------------------------------------------+