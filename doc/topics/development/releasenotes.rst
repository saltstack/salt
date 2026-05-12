.. _releasenotes:

=============
Release Notes
=============

You can edit the release notes to highlight a new feature being added
to a given release. The release notes are templatized with Jinja and
are generated at release time.


.. _edit-release-note:

How do I edit the release notes
-------------------------------

To edit the release notes you need to look in doc/topics/releases/templates
for your given release and edit the template. Do not edit the release note
files in doc/topics/releases/, as this will be written over with the content
in the template file. For example, if you want to add content to the 3006.0
release notes you would edit the doc/topics/releases/templates/3006.0.md.template
file. Do not edit the changelog portion of the template file, since that is
auto generated with the content generated for the changelog for each release.


How to generate the release notes
---------------------------------

This step is only used when we need to generate the release notes before releasing.
You should NOT need to run these steps as they are ran in the pipeline, but this
is documented so you can test your changes to the release notes template.

To generate the release notes requires the `tools` command. The instructions below
will detail how to install and use `tools`.


Installing `tools`
..................

.. code-block: bash

    python -m pip install -r requirements/static/ci/py3.10/tools.txt


To view the output the release notes will produce before generating them
you can run `tools` in draft mode:

.. code-block:: bash

    tools changelog update-release-notes --draft

To generate the release notes just remove the `--draft` argument:

.. code-block:: bash

    tools changelog update-release-notes


To specify a specific Salt version you add that version as an argument:

.. code-block:: bash

    tools changelog update-release-notes 3006.0


To only generate the template for a new release


.. code-block:: bash

    tools changelog update-release-notes --template-only
