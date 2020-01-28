=====================
Venafi Tools for Salt
=====================

Introduction
~~~~~~~~~~~~

First, you need to configure the ``master`` file. This is because
all module functions require either a configured ``api_key`` (for Cloud) or
``a ttp_user`` with a ``tpp_password`` and a ``base_url`` (for Trust Platform).

For Venafi Cloud:

.. code-block:: yaml

    venafi:
      api_key: abcdef01-2345-6789-abcd-ef0123456789
      base_url: "https://cloud.venafi.example.com/"    (optional)

If you don't have a Venafi Cloud account, you can sign up for one on the `enrollment page`_.

.. _enrollment page: https://www.venafi.com/platform/cloud/devops

For Venafi Platform:

.. code-block:: yaml

    venafi:
      base_url: "https://tpp.example.com/"
      tpp_user: admin
      tpp_password: "Str0ngPa$$w0rd"
      trust_bundle: "/opt/venafi/bundle.pem"

*It is not common for the Venafi Platform's REST API (WebSDK) to be secured using a certificate issued by a publicly trusted CA, therefore establishing trust for that server certificate is a critical part of your configuration. Ideally this is done by obtaining the root CA certificate in the issuing chain in PEM format and copying that file to your Salt Master (e.g. /opt/venafi/bundle.pem). You then reference that file using the 'trust_bundle' parameter as shown above.*

For the Venafi module to create keys and certificates it is necessary to enable external pillars. This is done by adding the following to the ``/etc/salt/master`` file:

.. code-block:: yaml

    ext_pillar:
      - venafi: True


Runner Functions
~~~~~~~~~~~~~~~~

request
-------
This command is used to enroll a certificate from Venafi Cloud or Venafi Platform.

``minion_id``
    ID of the minion for which the certificate is being issued. Required.

``dns_name``
    DNS subject name for the certificate. Required if ``csr_path`` is not specified.

``csr_path``
    Full path name of certificate signing request file to enroll. Required if ``dns_name`` is not specified.

``zone``
    Venafi Cloud zone ID or Venafi Platform folder that specify key and certificate policy. Defaults to "Default". For Venafi Cloud, the Zone ID can be found in the Zone page for your Venafi Cloud project.

``org_unit``
    Business Unit, Department, etc. Do not specify if it does not apply.

``org``
    Exact legal name of your organization. Do not abbreviate.

``loc``
    City/locality where your organization is legally located.

``state``
    State or province where your organization is legally located. Must not be abbreviated.

``country``
    Country where your organization is legally located; two-letter ISO code.

``key_password``
    Password for encrypting the private key.

The syntax for requesting a new certificate with private key generation looks like this:

.. code-block:: bash

    salt-run venafi.request minion.example.com dns_name=www.example.com \
    country=US state=California loc=Sacramento org="Company Name" org_unit=DevOps \
    zone=Internet key_password=SecretSauce

And the syntax for requesting a new certificate using a previously generated CSR looks like this:

.. code-block:: bash

    salt-run venafi.request minion.example.com csr_path=/tmp/minion.req zone=Internet


show_cert
---------
This command is used to show last issued certificate for domain.

``dns_name``
    DNS subject name of the certificate to look up.

.. code-block:: bash

  salt-run venafi.show_cert www.example.com


list_domain_cache
-----------------
This command lists domains that have been cached on this Salt Master.

.. code-block:: bash

  salt-run venafi.list_domain_cache


del_cached_domain
-----------------
This command deletes a domain from the Salt Master's cache.

``domains``
    A domain name, or a comma-separated list of domain names, to delete from this master's cache.

.. code-block:: bash

  salt-run venafi.del_cached_domain www.example.com


Transfer certificate to a minion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To transfer a cached certificate to a minion, you can use Venafi pillar.

Example state (SLS) file:

.. code-block:: yaml

    /etc/ssl/cert/www.example.com.crt:
      file.managed:
          - contents_pillar: venafi:www.example.com:cert
          - replace: True

    /etc/ssl/cert/www.example.com.key:
      file.managed:
          - contents_pillar: venafi:www.example.com:pkey
          - replace: True

    /etc/ssl/cert/www.example.com-chain.pem:
      file.managed:
          - contents_pillar: venafi:www.example.com:chain
          - replace: True