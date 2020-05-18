.. _changelog:

=========
Changelog
=========

With the addition of `SEP 01`_ the `keepachangelog`_ format was introduced into
our CHANGELOG.md file. The Salt project is using the `towncrier`_ tool to manage
the CHANGELOG.md file. The reason this tool was added to manage the changelog
was because we were previously managing the file manually and it would cause
many merge conflicts. This tool allows us to add changelog entries into separate
files and before a release we simply need to run ``towncrier --version=<version>``
for it to compile the changelog correctly.


.. _add-changelog:

How do I add a changelog entry
------------------------------

To add a changelog entry you will need to add a file in the `changelog` directory.
The file name should follow the syntax ``<issue #>.<type>``.

The types are in alignment with keepachangelog:

  removed:
    any features that have been removed

  deprecated:
    any features that will soon be removed

  changed:
    any changes in current existing features

  fixed:
    any bug fixes

  added:
    any new features added

For example if you are fixing a bug for issue number #1234 your filename would
look like this: changelog/1234.fixed. The contents of the file should contain
a summary of what you are fixing. If there is a legitimate reason to not include
an issue number with a given contribution you can add the PR number as the file
name (``<PR #>.<type>``).

If your PR does not align with any of the types, then you do not need to add a
changelog entry.

.. _generate-changelog:

How to generate the changelog
-----------------------------

This step is only used when we need to generate the changelog right before releasing.
You should NOT run towncrier on your PR, unless you are preparing the final PR
to update the changelog before a release.

You can run the `towncrier` tool directly or you can use nox to help run the command
and ensure towncrier is installed in a virtual environment. The instructions below
will detail both approaches.

If you want to see what output towncrier will produce before generating the change log
you can run towncrier in draft mode:

.. code-block:: bash

    towncrier --draft --version=3001

.. code-block:: bash

    nox -e 'changelog(draft=True)' -- 3000.1

Version will need to be set to whichever version we are about to release. Once you are
confident the draft output looks correct you can now generate the changelog by running:

.. code-block:: bash

    towncrier --version=3001

.. code-block:: bash

    nox -e 'changelog(draft=False)' -- 3000.1

After this is run towncrier will automatically remove all the files in the changelog directory.


.. _`SEP 01`: https://github.com/saltstack/salt-enhancement-proposals/pull/2
.. _`keepachangelog`: https://keepachangelog.com/en/1.0.0/
.. _`towncrier`: https://pypi.org/project/towncrier/
