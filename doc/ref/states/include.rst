===================
Include and Exclude
===================

Salt sls files can include other sls files and exclude sls files that have been
otherwise included. This allows for an sls file to easily extend or manipulate
other sls files.

Exclude
=======

The exclude statement, added in Salt 0.10.3 allows an sls to hard exclude
another sls file or a specific id. The component is excluded after the
high data has been compiled, so nothing should be able to override an
exclude.

Since the exclude can remove an id or an sls the type of component to
exclude needs to be defined. an exclude statement that verifies that the
running highstate does not contain the `http` sls and the `/etc/vimrc` id
would look like this:

.. code-block:: yaml

    exclude:
      - sls: http
      - id: /etc/vimrc
