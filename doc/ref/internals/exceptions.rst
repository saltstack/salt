==========
Exceptions
==========

Salt-specific exceptions should be thrown as often as possible so the various
interfaces to Salt (CLI, API, etc) can handle those errors appropriately and
display error messages appropriately.

.. autosummary::
    :toctree:
    :template: autosummary.rst.tmpl

    salt.exceptions
