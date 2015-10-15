=============
rest_cherrypy
=============

.. automodule:: salt.netapi.rest_cherrypy.app

.. automodule:: salt.netapi.rest_cherrypy.wsgi

REST URI Reference
==================

.. py:currentmodule:: salt.netapi.rest_cherrypy.app

.. contents::
    :local:

``/``
-----

.. autoclass:: LowDataAdapter
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

``/hook``
---------

.. autoclass:: Webhook
    :members: POST

``/keys``
---------

.. autoclass:: Keys
    :members: GET, POST

``/ws``
-------

.. autoclass:: WebsocketEndpoint
    :members: GET

``/stats``
----------

.. autoclass:: Stats
    :members: GET