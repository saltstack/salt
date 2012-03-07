=========================
File Server Configuration
=========================

The Salt file server is a high performance file server written in ZeroMQ. It
manages large files quickly and with little overhead, and has been optomized
to handle small files in an extreamly efficient manner.

The Salt file server is an environment aware file server, this means that 
files can be allocated within many root directories and accessed by
specifying both the file path and the environment to search. The
individual environments can also be spanned across mutiple directory roots
to crate overlays and to allow for files to be orginaized in many flexible
ways.

Environments
============

The Salt file server defaults to the mandatory ``base`` environment. This
environment MUST be defined and is used to download files when no
environment is specified.

Environments allow for files and sls data to be logically seperated, but
environments are not isolated from each other. This allows for logical
isolation of environments by the engineer using Salt, but also allows
for information to be used in multiple environments for maximum flexibility.
