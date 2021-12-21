:orphan:

.. _version-numbers:

===============
Version Numbers
===============

Salt uses a major and patch based systems for version numbers.  Version numbers are
in the format ``MAJOR.PATCH``.

.. note::

    Prior to the ``3000`` release, Salt used a date based system for version numbers.
    Version numbers were in the format ``YYYY.MM.R``. The year (``YYYY``) and month
    (``MM``) reflected when the release was created. The bugfix release number (``R``)
    increments within that feature release.

.. note::

    Prior to the ``2014.1.0`` release, the typical semantic versioning was
    still being used. Because of the rolling nature of the project, this did not
    make sense. The ``0.17`` release was the last of that style.

Code Names
----------

To distinguish future releases from the current release, code names are used.
The periodic table is used to derive the next codename. The first release in
the date based system was code named ``Hydrogen``, each subsequent release will
go to the next `atomic number <https://en.wikipedia.org/wiki/List_of_elements>`_.

Assigned codenames:

- Hydrogen: ``2014.1.0``
- Helium: ``2014.7.0``
- Lithium: ``2015.5.0``
- Beryllium: ``2015.8.0``
- Boron: ``2016.3.0``
- Carbon: ``2016.11.0``
- Nitrogen: ``2017.7.0``
- Oxygen: ``2018.3.0``
- Fluorine: ``2019.2.0``
- Neon: ``3000``
- Sodium: ``3001``
- Magnesium: ``3002``
- Aluminium: ``3003``
- Silicon: ``3004``
- Phosphorus: ``3005``
- Sulfur: ``3006``
- Chlorine:  ``3007``
- Argon: ``3008``
- Potassium: ``3009``

The complete list of upcoming codenames is available in the
`source code <https://github.com/saltstack/salt/blob/76e50885b07621e9e4c16bc3f1ebc16c93983b90/salt/version.py#L65-L182>`_.

Example
-------

An example might help clarify how this all works.

The current code name is ``Iodine``. A release is ready to be cut and the previous
release was ``3053``. This would make the new release number ``3054``. After three
patch releases, the release number would be ``3054.3``.

After the release is cut, new features would be worked on under the ``Xenon``
code name and the process repeats itself.


Version numbers, Git and salt --version
---------------------------------------

The salt version, for programmers, is based on ``git describe`` and presented to
end-users with ``salt --version``.

Example arguments for ``git checkout``:

  +------------+----------------------------------------------------------------------------+
  |  Argument  |                                           Comment                          |
  +============+============================================================================+
  | master     | **Master branch** Actively developed bug-fixes and new features            |
  +------------+----------------------------------------------------------------------------+
  | v3000      | Tag signaling the commit for 3000 release.                                 |
  +------------+----------------------------------------------------------------------------+
  | v3000.1    | Tag signaling the commit for a 3000.1 patch fix.                           |
  +------------+----------------------------------------------------------------------------+

Influence of the ``git checkout`` argument on ``git describe``:

  +------------+----------------------------+-----------------------------------------------+
  | Checkout   | Describe                   |               Comment                         |
  +============+============================+===============================================+
  | v3000      | v3000                      | (tag is fixed point in time)                  |
  +------------+----------------------------+-----------------------------------------------+
  | v3000.1    | v3000.1                    | (tag is fixed point in time)                  |
  +------------+----------------------------+-----------------------------------------------+
  | master     | v3000.1-9-g10d5dec         | Commit of most recent tag in master           |
  +------------+----------------------------+-----------------------------------------------+

Some details of v3000.1-9-g10d5dec (from ``git describe`` after ``git checkout master``):

  +---------------+-------------------------------------------------------------------------+
  |     Part      |                       Comment                                           |
  +===============+=========================================================================+
  |v3000.1        | git describe finds the most recent tag on the 2016.11 branch            |
  +---------------+-------------------------------------------------------------------------+
  |9              | Commits on top of the most recent tag, relative to your local git fetch |
  +---------------+-------------------------------------------------------------------------+
  |gf2eb3dc       | 'g' + git SHA ("abbreviated name") of the most recent commit            |
  +---------------+-------------------------------------------------------------------------+
