.. _changelog:

=========
Changelog
=========

Salt's ``CHANGELOG.md`` follows the `keepachangelog`_ format. The file itself
is generated at release time by `towncrier`_ from per-PR fragment files in
the ``changelog/`` directory. This avoids the merge conflicts we used to hit
when contributors edited ``CHANGELOG.md`` directly.

The format was adopted in `SEP 01`_.


.. _add-changelog:

How to add a changelog entry
============================

Create a file in the ``changelog/`` directory named
``<issue-or-pr-number>.<type>.md``. For a security fix tied to a CVE, name it
``cve-<cve-number>.security.md``.

For example, fixing issue 1234:

.. code-block:: bash

    echo "Fixed sys.doc reporting when no minions return." > changelog/1234.fixed.md

The file body is one or two short sentences describing the change from the
user's perspective. Markdown is allowed but rarely needed.

If your PR does not have an issue, use the PR number once it is opened. If
your PR does not change user-visible behavior (a refactor, a CI tweak, an
internal-only test) you do not need a changelog entry.

.. _changelog-types:

Entry types
-----------

Pick the type that best describes the change. These match the
`keepachangelog`_ sections:

``added``
    A new feature, module, or public API.

``changed``
    A change to existing user-visible behavior that is not a bug fix.

``deprecated``
    Behavior or APIs marked for future removal. Pair this with a
    ``.. deprecated::`` directive in the source. See
    :ref:`deprecations` for the worked example.

``removed``
    Features or APIs that have been deleted in this release.

``fixed``
    Bug fixes. Most contributor changelog entries are this type.

``security``
    Fixes for CVEs. Use the ``cve-<cve-number>.security.md`` filename
    form. Coordinate disclosure through the process documented in
    `SECURITY.md <https://github.com/saltstack/salt/blob/master/SECURITY.md>`__
    before opening a public PR.

.. note::

   Updates to runtime requirements files (``requirements/static/pkg/*.txt``,
   ``requirements/base.txt``, and so on) also need a fragment, normally
   ``.fixed`` for a routine bump or ``.security`` for a CVE bump. Testing-only
   requirements (``requirements/static/ci/...``) do not.


How the maintainers check it
----------------------------

The ``check-changelog-entries`` pre-commit hook validates the filename
format against ``pyproject.toml``'s towncrier config and rejects fragments
with an unknown type. Run it locally before pushing:

.. code-block:: bash

    pre-commit run check-changelog-entries --all-files

If you forget the fragment, the same check runs in CI and the PR will be
marked failing.


.. _generate-changelog:

How the changelog is generated at release time
==============================================

This section is for the release manager. Day-to-day contributors should
**not** run towncrier on their PR.

The release PR uses the ``tools changelog`` wrapper, which installs
towncrier into a managed virtualenv and invokes it for you:

.. code-block:: bash

    python -m pip install -r requirements/static/ci/py3.10/tools.txt

Preview what towncrier would emit, without consuming any fragment files:

.. code-block:: bash

    tools changelog update-changelog-md --draft 3008.1

When the draft looks right, generate it for real. ``tools changelog
update-changelog-md`` passes ``--yes`` automatically so towncrier deletes
the consumed fragments:

.. code-block:: bash

    tools changelog update-changelog-md 3008.1

The release PR commits the updated ``CHANGELOG.md`` and the now-empty
``changelog/`` directory together.

If you need to call towncrier directly:

.. code-block:: bash

    towncrier --draft --version=3008.1
    towncrier --yes --version=3008.1


.. _`SEP 01`: https://github.com/saltstack/salt-enhancement-proposals/pull/2
.. _`keepachangelog`: https://keepachangelog.com/en/1.0.0/
.. _`towncrier`: https://pypi.org/project/towncrier/
