Translating Documentation
=========================

If you wish to help translate the Salt documentation to your language, please 
head over to the `Transifex`_ website and `signup`__ for an account.

Once registered, head over to the `Salt Translation Project`__, and either 
click on **Request Language** if you can't find yours, or, select the language 
for which you wish to contribute and click **Join Team**.

`Transifex`_ provides some useful reading resources on their `support 
domain`__, namely, some useful articles `directed to translators`__.


.. __: https://www.transifex.com/signup/
.. __: https://www.transifex.com/projects/p/salt/
.. __: http://support.transifex.com/
.. __: http://support.transifex.com/customer/portal/topics/414107-translators/articles


Building A Localized Version of the Documentation
-------------------------------------------------

While you're working on your translation on `Transifex`_, you might want to 
have a look at how it's rendering.

There's a little script which simplifies the download process of the 
translations(which isn't that complicated in the first place).
So, let's assume you're translating ``pt_PT``, Portuguese(Portugal). To 
download the translations, execute from the ``doc/`` directory of your Salt 
checkout:

.. code-block:: bash


    make download-translations SPHINXLANG=pt_PT


To download ``pt_PT``, Portuguese(Portugal) and ``nl``, Dutch, you can use the 
helper script directly:

.. code-block:: bash

    .scripts/download-translation-catalog pt_PT nl


After the download process finishes, which might take a while, the next step is 
to build a localized version of the documentation.
Following the ``pt_PT`` example above:

.. code-block:: bash

    make html SPHINXLANG=pt_PT


Open your browser, point it to the local documentation path and check the 
localized output you've just build.


.. _`Transifex`: https://www.transifex.com
