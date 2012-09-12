===========================
salt.returners.mongo_return
===========================

.. automodule:: salt.returners.mongo_return
    :members:

This returner will send data from the minions to a MongoDB server. To 
configure the settings for your MongoDB server, add the following lines
to the minion config files::

    mongo.db: <database name>
    mongo.host: <server ip address>
    mongo.user: <MongoDB username>
    mongo.password: <MongoDB user password>
    mongo.port: 27017
