import logging

import tools.changelog
import tools.ci
import tools.docs
import tools.pkg
import tools.vm

for name in ("boto3", "botocore", "urllib3"):
    logging.getLogger(name).setLevel(logging.INFO)
