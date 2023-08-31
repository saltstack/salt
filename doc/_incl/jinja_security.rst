.. important::

   :ref:`Jinja <understanding-jinja>` supports a `secure, sandboxed template execution environment
   <https://jinja.palletsprojects.com/en/2.11.x/sandbox/>`__ that Salt
   takes advantage of. Other text :ref:`renderers` do not support this
   functionality, so Salt highly recommends usage of ``jinja`` / ``jinja|yaml``.
