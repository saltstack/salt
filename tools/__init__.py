import logging

import tools.changelog
import tools.ci
import tools.docs
import tools.pkg
import tools.pkgrepo
import tools.pre_commit
import tools.vm

for name in ("boto3", "botocore", "urllib3"):
    logging.getLogger(name).setLevel(logging.INFO)
