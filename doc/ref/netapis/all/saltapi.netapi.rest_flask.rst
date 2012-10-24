==========
rest_flask
==========

.. automodule:: saltapi.netapi.rest_flask

.. py:currentmodule:: saltapi.netapi.rest_flask

.. _rest-flask-minions:

Run commands and view minion details
====================================

.. autoclass:: MinionsView

List minion grains and functions
--------------------------------

.. http:get:: /minions
.. http:get:: /minions/(mid)

    .. automethod:: MinionsView.get

    **Example request**::

        % curl -i localhost:8000/minions

    .. code-block:: http

        GET /minions HTTP/1.1
        Host: localhost:8000
        Accept: application/json

    **Example response**:

    .. code-block:: http

        HTTP/1.0 200 OK
        Content-Type: application/json

        {
            "ms-1": {
                "grains.items": {
                    ...
                },
                "sys.list_functions": [
                    ...
                ]
            },
            "ms-2": {
                ...
            }
        }

    :param mid: (optional) a :conf_minion:`minion id <id>` to only return
            data from a single minion
    :status 200: success
    :status 404: no minion with the specified :conf_minion:`id`

Run execution module functions
------------------------------

.. http:post:: /minions

    .. automethod:: MinionsView.post

    **Example request**::

        curl -iL localhost:8000/minions -d tgt='*' -d fun='test.ping' -d arg

    .. code-block:: http

        POST /minions HTTP/1.1
        Host: localhost:8000
        Accept: application/json
        Content-Length: 23
        Content-Type: application/x-www-form-urlencoded

        tgt=*&fun=test.ping&arg

    **Example response**:

    .. code-block:: http

        HTTP/1.0 302 FOUND
        Content-Type: text/html; charset=utf-8
        Location: http://localhost:8000/jobs/20121016113250762338

    :form tgt: the Salt target
    :form expr: the matcher (default glob)
    :form fun: the Salt execution module and function to run; this option may
        be specified multiple times
    :form arg: (*required*) corresponding arguments to pass to fun; this
        option must be passed even if empty; this option may be specified
        multiple times
    :status 302: success; redirects to :http:get:`/jobs/(jid)`
    :status 400: missing form parameters or mismatched ``fun`` and ``arg``
        parameters


.. ............................................................................

.. _rest-flask-jobs:

Job returns and previously run jobs
===================================

.. autoclass:: JobsView

List jobs, view a job
---------------------

.. http:get:: /jobs
.. http:get:: /jobs/(jid)

    .. automethod:: JobsView.get

    **Example request**::

        % curl -i localhost:8000/jobs

    .. code-block:: http

        GET /jobs HTTP/1.1
        Host: localhost:8000
        Accept: application/json

    **Example response**:

    .. code-block:: http

        HTTP/1.0 200 OK
        Content-Type: application/json

        {
            "20121016122040904159": {
                "Function": [
                    "sys.list_functions",
                    "grains.items"
                ],
                "Target": "*",
                "Target-type": "glob",
                "Start Time": "2012, Oct 16 12:20:40.904159",
                "Arguments": [
                    [],
                    []
                ]
            },
            "20121016013506244851": {
                ...
            }
        }

    :param jid: (optional) a job ID; return the output from a specific job
    :status 200: success
    :status 404: no job with the specified ID

.. ............................................................................

.. _rest-flask-runners:

List and execute runner commands
================================

.. autoclass:: RunnersView

List availble runners
---------------------

.. http:get:: /runners

    .. automethod:: RunnersView.get

    **Example request**::

        % curl -i localhost:8000/runners

    .. code-block:: http

        GET /runners HTTP/1.1
        Host: localhost:8000
        Accept: application/json

    **Example response**:

    .. code-block:: http

        HTTP/1.0 200 OK
        Content-Type: application/json

        {
            "runners": [
                "network.wol",
                "manage.down",
                "jobs.print_job",
                "jobs.active",
                "network.wollist",
                "manage.up",
                "launchd.write_launchd_plist",
                "jobs.lookup_jid",
                "jobs.list_jobs"
            ]
        }

Execute runner functions
------------------------

.. http:post:: /runners

    .. automethod:: RunnersView.post

    **Example request**::

        % curl -iL localhost:8000/runners -d fun='manage.up' -d arg

    .. code-block:: http

        POST /runners HTTP/1.1
        Host: localhost:8000
        Accept: application/json
        Content-Length: 17
        Content-Type: application/x-www-form-urlencoded

        fun=manage.up&arg

    **Example response**:

    .. code-block:: http

        HTTP/1.0 200 OK
        Content-Type: application/json
        Content-Length: 84
        Server: Werkzeug/0.8.3 Python/2.7.3
        Date: Tue, 16 Oct 2012 21:56:07 GMT

        {
            "return": [
                "ms-0",
                "ms-1",
                "ms-2",
                "ms-3",
                "ms-4"
            ]
        }

    :form fun: the Salt runner function to execute
    :form arg: (*required*) corresponding arguments to pass to fun; this
        option must be passed even if empty
    :status 200: success
    :status 400: missing form parameters or mismatched ``fun`` and ``arg``
        parameters
