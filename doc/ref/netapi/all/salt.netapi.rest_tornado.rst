=============
rest_tornado
=============

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
    :members: GET, POST

``/login``
----------

.. autoclass:: Login
    :members: GET, POST

``/logout``
-----------

.. autoclass:: Logout
    :members: POST

``/minions``
------------

.. autoclass:: Minions
    :members: GET, POST

``/jobs``
---------

.. autoclass:: Jobs
    :members: GET

``/run``
--------

.. autoclass:: Run
    :members: POST

``/events``
-----------

.. autoclass:: Events
    :members: GET

``/ws``
-------

.. autoclass:: WebsocketEndpoint
    :members: GET

``/hook``
---------

.. autoclass:: Webhook
    :members: POST

``/stats``
----------

.. autoclass:: Stats
    :members: GET
