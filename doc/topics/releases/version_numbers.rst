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
go to the next atomic number.

Example
-------

An example might help clarify how this all works.

It is the year ``2020`` and the current code name is ``Iodine``. A release is ready
to be cut and the month is ``June``. This would make the new release number
``2020.6.0``. After three bug fix releases, the release number would be
``2020.6.3``.

After the release is cut, new features would be worked on under the ``Xenon``
code name and the process repeats itself.
