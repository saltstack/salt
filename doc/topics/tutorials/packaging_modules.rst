.. _tutorial-packaging-modules:

===================================
Packaging External Modules for Salt
===================================

External Modules Setuptools Entry-Points Support
================================================

The salt loader was enhanced to look for external modules by looking at the
`salt.loader` entry-point:

 https://setuptools.readthedocs.io/en/latest/pkg_resources.html#entry-points

`pkg_resources` should be installed, which is normally included in setuptools.

 https://setuptools.readthedocs.io/en/latest/pkg_resources.html

The package which has custom engines, minion modules, outputters, etc, should
require setuptools and should define the following entry points in its setup
function:

.. code-block:: python

    from setuptools import setup, find_packages

    setup(
        name=THE_NAME,
        version=THE_VERSION,
        description=THE_DESCRIPTION,
        author=THE_AUTHOR_NAME,
        author_email=THE_AUTHOR_EMAIL,
        url=" ... ",
        packages=find_packages(),
        entry_points="""
        [salt.loader]
        engines_dirs = <package>.<loader-module>:engines_dirs
        fileserver_dirs = <package>.<loader-module>:fileserver_dirs
        pillar_dirs = <package>.<loader-module>:pillar_dirs
        returner_dirs = <package>.<loader-module>:returner_dirs
        roster_dirs = <package>.<loader-module>:roster_dirs
        """,
    )


The above setup script example mentions a loader module. here's an example of
how `<package>/<loader-module>.py` it should look:

.. code-block:: python

    # -*- coding: utf-8 -*-

    # Import python libs
    import os

    PKG_DIR = os.path.abspath(os.path.dirname(__file__))


    def engines_dirs():
        """
        yield one path per parent directory of where engines can be found
        """
        yield os.path.join(PKG_DIR, "engines_1")
        yield os.path.join(PKG_DIR, "engines_2")


    def fileserver_dirs():
        """
        yield one path per parent directory of where fileserver modules can be found
        """
        yield os.path.join(PKG_DIR, "fileserver")


    def pillar_dirs():
        """
        yield one path per parent directory of where external pillar modules can be found
        """
        yield os.path.join(PKG_DIR, "pillar")


    def returner_dirs():
        """
        yield one path per parent directory of where returner modules can be found
        """
        yield os.path.join(PKG_DIR, "returners")


    def roster_dirs():
        """
        yield one path per parent directory of where roster modules can be found
        """
        yield os.path.join(PKG_DIR, "roster")
