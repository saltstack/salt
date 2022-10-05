.. _test-pipeline:

=============
Test Pipeline
=============

Salt's test suite is run on `jenkins`_. We have added the ``@pytest.mark.slow_test``
pytest decorator to help designate tests that take a significant amount of time to
run. These tests are only run on our branch tests, unless your PR is editing code
that requires running a specific slow test. When you submit a PR it will by default,
only run the tests that do not include the ``@pytest.mark.slow_test`` pytest decorator.


Process to Fix Test Failures on Branch Tests
--------------------------------------------

If there is a failure on the branch tests on `jenkins`_, this is the process to follow
to ensure it is fixed.

- Review the issues in Salt repo with the label ``Test-Failure`` to ensure there isn't
  an already open issue assigned to someone to fix.
- If there is not an issue open for the failing test, create a new issue in Salt's repo
- Select "Test Failure" and the issue will create the correct template you need.
- Include the name of the test that is failing in the title
- Include the jenkins URL to the test in the body and any additional information needed.
- When you create the issue it will automatically add the label ``Test-Failure``.
- If you are going to fix the test assign yourself to the issue.
- If you are not going to fix the test, there is nothing else to do. The core team will
  review these open issues and ensure they are assinged out to be fixed.


.. _jenkins: https://jenkins.saltproject.io
