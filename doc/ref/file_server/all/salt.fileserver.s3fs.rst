.. _salt-fileserver-s3fs:

==============
salt.fileserver.s3fs
==============

The S3 fileserver backend allows Salt to serve files from AWS S3 buckets.

Configuration
=============

To use the S3 fileserver backend, add the following to the Salt master configuration:

.. code-block:: yaml

    fileserver_backend:
      - s3fs

    s3.buckets:
      - my-bucket

To authenticate, you can use AWS instance profiles (if running on EC2), or provide explicit credentials via ``s3.keyid``, ``s3.key``, and ``s3.role_arn``.

Regional Endpoints
==================

If your S3 bucket was created in a region other than ``us-east-1``, you may need to set the regional endpoint explicitly. Without this setting, Salt may incorrectly try to access the bucket via the global endpoint, resulting in ``AccessDenied`` errors.

To configure, add the following to your Salt configuration:

.. code-block:: yaml

    s3.service_url: s3.<region>.amazonaws.com

For example, for a bucket in ``us-west-2``:

.. code-block:: yaml

    s3.service_url: s3.us-west-2.amazonaws.com

This is especially important when using instance profile credentials, as the global endpoint may not resolve correctly for regional buckets.

For more details, see the `AWS S3 endpoints documentation <https://docs.aws.amazon.com/general/latest/gr/s3.html>`_.
