.. _faq-py2-deprecation:

Python 2 Deprecation FAQ
========================

.. contents:: FAQ

Why are we deprecating Python 2?
--------------------------------

Python 2.7.18 was the final release of Python2, released in April 2020.
At this point, Python 2 will no longer receive any unpaid support. The
Python core developers are focusing their efforts on improving and
enhancing Python 3. Additionally, many libraries that Salt depends on
have also dropped Python 2 support.

To take advantage of continued support and improvements, Salt is joining
the ranks of projects that are dropping legacy Python support in favor
of Python 3.

Was this announced/decided before making the change?
----------------------------------------------------

`SEP
5 <https://github.com/saltstack/salt-enhancement-proposals/blob/master/accepted/0005-retire-py2-support.md>`__
was approved in April, 2019.

Can I contribute Python 2 code?
-------------------------------

For several years, Salt has been a Python 2/3 codebase, requiring Python
3 support for all contributions. The only changes contributors can
expect to this process is that we will now accept Python 3-only code
changes.

While there *is* a significant subset of Python that is compatible with
both Python 3 and legacy Python, changes requiring ``six`` or otherwise
removing Python 3-only code will not be accepted.

What if my OS does not include Python 3 packages? Or, how do I upgrade from Salt on Python 2 to Salt on Python 3?
-----------------------------------------------------------------------------------------------------------------

There are several options to upgrade to Python 3.

On Modern Platforms
~~~~~~~~~~~~~~~~~~~

At this point, most modern Linux distributions have Python 3 packages.
Ubuntu 20.04 LTS has moved to Python 3.8 as it’s default system Python.

On Other Platforms
~~~~~~~~~~~~~~~~~~

Build Your Own
^^^^^^^^^^^^^^

If your current distribution does not have Python 3 it’s `pretty simple
to use Salt <https://www.youtube.com/watch?v=Zq0XXtIKx_Q>`__ to build
and distribute Python 3 on your own. Installing Python 3 and pip
installing Salt gives you the most control over your distribution.

``pop-build`` distributions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Another approach is to use the ``pop-build`` distribution of Salt. With
the Sodium release we will begin releasing packages for Salt using
``pop-build``, in tandem with our normal build process. The
``pop-build`` distribution will contain Salt, Python, and any necessary
dependencies, which will make it trivial to have a completely supported
version of Salt.

Will you support a Python 3 master with an older Python 2 minion?
-----------------------------------------------------------------

Yes! Our policy of keeping newer masters backwards compatible with *at
least* the most recent minion version is not changing. You should be
able to run modern Salt Masters on Python 3 with slightly older minions
running on legacy Python. Of course, if you want your minions to be able
to take advantage of the newest features in Salt, upgrading to Python 3
will be necessary.

Will you support Python 2 master with a new Python 3 minion?
------------------------------------------------------------

In keeping with our existing policy, we make no guarantees about older
masters with newer minions. It *may* work, but breakages are common and
should be expected.

How does this impact Salt-SSH support?
--------------------------------------

Salt-SSH will need Python 3 on the target minions. We will be upgrading
Salt-SSH to provide instructions or recommendations on adding Python3 if
it is not detected.

What is your plan for removing Python 2 code?
---------------------------------------------

Legacy Python code will be gradually removed from the Salt codebase.

While we could remove most of it at once, that introduces a high level
of risk. Instead, beginning with the Sodium (v3001) release, Salt will
simply drop support for Python 2. PRs will no longer be required to
support Python 2 before merging.

Over time, as modules are changed, ``six`` and other legacy Python
syntax will be removed. It may be at some point in the future it becomes
necessary to remove the last vestiges of legacy Python from Salt, but
currently the plan is to take a more measured approach.

Will Salt continue to package for Python 2?
-------------------------------------------

No. Beginning with Sodium (v3001), Salt will no longer release packages
for, or support Python 2.
