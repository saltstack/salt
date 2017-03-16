=====================
Venafi Tools for Salt
=====================

Introduction
~~~~~~~~~~~~
Before using these modules you need to register an account with Venafi, and
configure it in your ``master`` configuration file.

First, you need to add a placeholder to the ``master`` file. This is because
the module will not load unless it finds an ``api_key`` setting, valid or not.
Open up ``/etc/salt/master`` and add:

.. code-block:: yaml

    api_key: None

Then register your email address with Venafi using the following command:

.. code-block:: bash

    salt-run venefi.register <youremail@yourdomain.com>

This command will not return an ``api_key`` to you; that will be send to you
via email from Venafi. Once you have received that key, open up your ``master``
file and set the ``api_key`` to it:

.. code-block:: yaml

    api_key: abcdef01-2345-6789-abcd-ef0123456789
Before using these modules you need to register an account with Venafi, and
configure it in your ``master`` configuration file.

First, you need to add a placeholder to the ``master`` file. This is because
the module will not load unless it finds an ``api_key`` setting, valid or not.
Open up ``/etc/salt/master`` and add:

.. code-block:: yaml

    api_key: None

Then register your email address with Venagi using the following command:

.. code-block:: bash

    salt-run venefi.register <youremail@yourdomain.com>

This command will not return an ``api_key`` to you; that will be send to you
via email from Venafi. Once you have received that key, open up your ``master``
file and set the ``api_key`` to it:

.. code-block:: yaml

    api_key: abcdef01-2345-6789-abcd-ef0123456789

Example Usage
~~~~~~~~~~~~~~~~
Generate a CSR and submit it to Venafi for issuance, using the 'Internet' zone:
salt-run venafi.request minion.example.com minion.example.com zone=Internet

Retrieve a certificate for a previously submitted request with request ID
aaa-bbb-ccc-dddd:
salt-run venafi.pickup aaa-bbb-ccc-dddd

Runner Functions
~~~~~~~~~~~~~~~~

gen_key
-------
Generate and return a ``private_key``. If a ``dns_name`` is passed in, the
``private_key`` will be cached under that name. 

The key will be generated based on the policy values that were configured
by the Venafi administrator. A default Certificate Use Policy is associated
with a zone; the key type and key length parameters associated with this value
will be used.

:param str minion_id: Required. The name of the minion which hosts the domain
    name in question.

:param str dns_name: Required. The FQDN of the domain that will be hosted on
    the minion.

:param str zone: Required. Default value is "default". The zone on Venafi that
    the domain belongs to.

:param str password: Optional. If specified, the password to use to access the
    generated key.


gen_csr
-------
Generate a csr using the host's private_key. Analogous to:

.. code-block:: bash

    VCert gencsr -cn [CN Value] -o "Beta Organization" -ou "Beta Group" \
        -l "Palo Alto" -st "California" -c US

:param str minion_id: Required.

:param str dns_name: Required.

:param str zone: Optional. Default value is "default". The zone on Venafi that
    the domain belongs to.

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

:param str password=None: Optional. Password for the CSR.


request
-------
Request a new certificate. Analogous to:

.. code-block:: bash

    VCert enroll -z <zone> -k <api key> -cn <domain name>

:param str minion_id: Required.

:param str dns_name: Required.

:param str zone: Required. Default value is "default". The zone on Venafi that
    the certificate request will be submitted to.

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

:param str password=None: Optional. Password for the CSR.

:param str company_id=None: Required, but may be configured in ``master`` file
    instead.

register
--------
Register a new user account

:param str email: Required. The email address to use for the new Venafi account.


show_company
------------
Show company information, especially the company id

:param str domain: Required. The domain name to look up information for.


show_csrs
---------
Show certificate requests for the configured API key.


show_zones
----------
Show zones for the specified company id.

:param str company_id: Required. The company id to show the zones for.


pickup, show_cert
-----------------
Show certificate requests for the specified certificate id. Analogous to the
VCert pickup command.

:param str id_: Required. The id of the certificate to look up.


show_rsa
--------
Show a private RSA key.

:param str minion_id: The name of the minion to display the key for.

:param str dns_name: The domain name to display the key for.


list_domain_cache
-----------------
List domains that have been cached on this master.


del_cached_domain
-----------------
Delete a domain from this master's cache.

:param str domains: A domain name, or a comma-separated list of domain names,
    to delete from this master's cache.
