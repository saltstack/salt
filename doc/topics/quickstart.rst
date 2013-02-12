========
salt-api Quickstart
========

Getting started with salt-api is fast and easy. When you are done with this 
document you will have basic salt-api interface using the cherrypy netapi 
module. This document describes a setup that should be used for testing purposes
only. Addtional configuration is needed before moving to a production 
enviroment.

Instalation
-----------------
# Download and install cherrypy as a dependancy
# Download salt-api
  # :command:`git clone https://github.com/saltstack/salt-api.git`
# Change dirctory to the salt-api folder and install salt-api
  # :command:`python setup.py install`
# Run salt-api by issuing :command:`salt-api`

Configuration
-----------------
# Setup `external_auth`_ in Salt master configuration file
# Include the rest_cherrypy in your master configureation file:command:

   `rest_cherrypy:
     port: 8000
     debug: True`

.. _`external_auth`: http://docs.saltstack.org/en/latest/topics/eauth/index.html


Reference
=========

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
* :ref:`glossary`
