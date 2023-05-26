import logging

import ptscripts

ptscripts.register_tools_module("tools.changelog")
ptscripts.register_tools_module("tools.ci")
ptscripts.register_tools_module("tools.docs")
ptscripts.register_tools_module("tools.pkg")
ptscripts.register_tools_module("tools.pkg.repo")
ptscripts.register_tools_module("tools.pkg.build")
ptscripts.register_tools_module("tools.pkg.repo.create")
ptscripts.register_tools_module("tools.pkg.repo.publish")
ptscripts.register_tools_module("tools.precommit")
ptscripts.register_tools_module("tools.precommit.changelog")
ptscripts.register_tools_module("tools.precommit.workflows")
ptscripts.register_tools_module("tools.release")
ptscripts.register_tools_module("tools.testsuite")
ptscripts.register_tools_module("tools.testsuite.download")
ptscripts.register_tools_module("tools.vm")

for name in ("boto3", "botocore", "urllib3"):
    logging.getLogger(name).setLevel(logging.INFO)
