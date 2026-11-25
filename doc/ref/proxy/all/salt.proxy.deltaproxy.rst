salt.proxy.deltaproxy
=====================

The control proxy routes publications to its children using each child's target
matcher. With ``transport: tcp``, the master forwards targeted publications to
authenticated control proxies. With ``transport: zeromq`` and
``zmq_filtering: true``, the control proxy subscribes to the ID topics of children
that finish initialization. Ordinary ID, glob, list, regular expression, and
compound targets can therefore reach children through the shared connection.

.. automodule:: salt.proxy.deltaproxy
    :members:
