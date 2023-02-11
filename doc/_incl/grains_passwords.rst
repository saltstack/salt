.. warning::

   Grains can be set by users that have access to the minion configuration files on
   the local system, making them less secure than other identifiers in Salt. Avoid
   storing sensitive data, such as passwords or keys, on minions. Instead, make
   use of :ref:`pillar` and/or :ref:`sdb`.
