salt.states.ini_manage
======================

Strict mode behavior
--------------------

When ``strict: True`` is used with ``ini.options_present``, the ini file is
pruned to match the ``sections`` dictionary:

- keys not listed at the top level are removed
- keys not listed inside a section are removed
- sections not listed are removed entirely

Example:

.. code-block:: yaml

    /etc/app/config.ini:
      ini.options_present:
        - strict: True
        - sections:
            service:
              enabled: true
            network:
              port: 1234

.. automodule:: salt.states.ini_manage
    :members:
