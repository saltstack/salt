:orphan:

==================================
Salt Release Notes - Codename Neon
==================================


Unless and onlyif Enhancements
==============================

The ``unless`` and ``onlyif`` requisites can now be operated with salt modules.
The dictionary must contain an argument ``fun`` which is the module that is
being run, and everything else must be passed in under the args key or will be
passed as individual kwargs to the module function.

.. code-block:: yaml

  install apache on debian based distros:
    cmd.run:
      - name: make install
      - cwd: /path/to/dir/whatever-2.1.5/
      - unless:
        - fun: file.file_exists
          path: /usr/local/bin/whatever

.. code-block:: yaml

  set mysql root password:
    debconf.set:
      - name: mysql-server-5.7
      - data:
          'mysql-server/root_password': {'type': 'password', 'value': {{pillar['mysql.pass']}} }
      - unless:
        - fun: pkg.version
          args:
            - mysql-server-5.7
