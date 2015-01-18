============
rest_tornado
============

.. automodule:: salt.netapi.rest_tornado.saltnado

.. automodule:: salt.netapi.rest_tornado.saltnado_websockets

REST URI Reference
==================

.. py:currentmodule:: salt.netapi.rest_tornado.saltnado

.. contents::
    :local:

``/``
-----

.. autoclass:: SaltAPIHandler
    :members: get, post, disbatch

``/login``
----------

.. autoclass:: SaltAuthHandler
    :members: get, post

``/minions``
------------

.. autoclass:: MinionSaltAPIHandler
    :members: get, post

``/jobs``
---------

.. autoclass:: JobsSaltAPIHandler
    :members: get

``/run``
--------

.. autoclass:: RunSaltAPIHandler
    :members: post

``/events``
-----------

.. autoclass:: EventsSaltAPIHandler
    :members: get

``/hook``
---------

.. autoclass:: WebhookSaltAPIHandler
    :members: post