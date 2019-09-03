=====================
Venafi Tools for Salt
=====================

Introduction
~~~~~~~~~~~~

Before using these modules you need to register an account with Venafi, and
configure it in your ``master`` configuration file.

First, you need to add configuration to the ``master`` file. This is because
all fuctions in the module require configured ``api_key`` (for Cloud) or
``ttp_user``, ``tpp_password`` and ``base_url`` (for Trust Platform) settings.
Open up ``/etc/salt/master`` and add:

.. code-block:: yaml

    venafi:
      base_url: "https://tpp.example.com/"
      tpp_user: admin
      tpp_password: "Str0ngPa$$w0rd"

or

.. code-block:: yaml

    venafi:
      api_key: abcdef01-2345-6789-abcd-ef0123456789
      base_url: "https://cloud.venafi.example.com/" (optional)

To enable the ability for creating keys and certificates it is necessary to enable the
external pillars.  Open the ``/etc/salt/master`` file and add:

.. code-block:: yaml

    ext_pillar:
      - venafi: True

To modify the URL being used for the Venafi Certificate issuance modify the file
in ``/etc/salt/master`` and add the base_url information following under the
``venafi`` tag:

.. code-block:: yaml

    venafi:
      base_url: http://newurl.venafi.com


Example Usage
~~~~~~~~~~~~~
Request certificate from Venafi Cloud or Trust Platform, using the ``Internet``
zone for minion ``minion.example.com``:

.. code-block:: bash
    salt-run venafi.request minion.example.com www.example.com zone=Internet


Runner Functions
~~~~~~~~~~~~~~~~

request
-------

Request a new certificate. Analogous to:

.. code-block:: bash

    salt-run venafi.request minion.example.com minion.example.com country=US \
    state=California loc=Sacramento org=CompanyName org_unit=DevOps \
    zone=Internet password=SecretSauce

:param str minion_id: Required.

:param str dns_name: Required.

:param str zone="Default": Optional. The zone in Venafi Cloud
    or Venafi Trust Platform that the certificate request will be submitted to.

:param str country=None: Optional. The two-letter ISO abbreviation for your
    country.

:param str state=None: Optional. The state/county/region where your
    organisation is legally located. Must not be abbreviated.

:param str loc=None: Optional. The city where your organisation is legally
    located.

:param str org=None: Optional. The exact legal name of your organisation. Do
    not abbreviate your organisation name.

:param str org_unit=None: Optional. Section of the organisation, can be left
    empty if this does not apply to your case.

:param str password=None: Optional. Password for the private key.

:param str company_id=None: Optional, but may be configured in ``master`` file
    instead.


show_cert
-----------------

Show last issued certificate for domain ``test.example.com``

.. code-block:: bash

  salt-run venafi.show_cert test.example.com

:param str dns_name: Required. The id of the certificate to look up.


list_domain_cache
-----------------

List domains that have been cached on this master.

.. code-block:: bash

  salt-run venafi.list_domain_cache


del_cached_domain
-----------------

Delete a domain from this master's cache.

.. code-block:: bash

  salt-run venafi.del_cached_domain example.com

:param str domains: A domain name, or a comma-separated list of domain names,
    to delete from this master's cache.

Transfer certificate to pillar
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To transfer cached certificate to minion you can use venafi pillar.

Example state file:

.. code-block:: yml

    /etc/ssl/cert/minion.example.com.pem:
      file.managed:
          - contents_pillar: venafi:minion.example.com:cert
          - replace: True

    /etc/ssl/cert/minion.example.com.key.pem:
      file.managed:
          - contents_pillar: venafi:minion.example.com:pkey
          - replace: True