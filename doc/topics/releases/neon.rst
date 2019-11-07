:orphan:

==================================
Salt Release Notes - Codename Neon
==================================

XML Module
==========

A new state and execution module for editing XML files is now included. Currently it allows for
editing values from an xpath query, or editing XML IDs.

.. code-block:: bash

  # salt-call xml.set_attribute /tmp/test.xml ".//actor[@id='3']" editedby "Jane Doe"
  local:
      True
  # salt-call xml.get_attribute /tmp/test.xml ".//actor[@id='3']"
  local:
      ----------
      editedby:
          Jane Doe
      id:
          3
  # salt-call xml.get_value /tmp/test.xml ".//actor[@id='2']"
  local:
      Liam Neeson
  # salt-call xml.set_value /tmp/test.xml ".//actor[@id='2']" "Patrick Stewart"
  local:
      True
  # salt-call xml.get_value /tmp/test.xml ".//actor[@id='2']"
  local:
      Patrick Stewart

.. code-block:: yaml

    ensure_value_true:
      xml.value_present:
        - name: /tmp/test.xml
        - xpath: .//actor[@id='1']
        - value: William Shatner
