# -*- coding: utf-8 -*-
'''
Create and destroy S3 Buckets
=============================

Create and destroy S3 buckets. This interacts with Amazon's services, and so
may incur charges.

This differs from the raw s3 module in that it uses the awscli tool provided by
Amazon.  This can be downloaded from pip. Check the documentation for awscli
for configuration information.
'''
import json

# import salt libs
import salt.utils
from salt.utils import aws
