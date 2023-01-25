import logging

import tools.ci
import tools.pkg
import tools.vm
import tools.changelog
import tools.docs

for name in ("boto3", "botocore", "urllib3"):
    logging.getLogger(name).setLevel(logging.INFO)
