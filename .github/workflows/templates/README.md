# Workflow Templates

The templates are used to generate the actual workflows that run on GitHub Actions.
They use [Jinja2](https://jinja.palletsprojects.com) as the template engine.

## To Note

Let's try to keep the Jinja usage to the bare minimum because, as time passes,
the complexity just piles up making it harder to read and interpret the templates.

### Changes To Default Jinja Syntax

By default Jinja uses `{% ... %}`, `{{ ... }}`, `{# ... #}`, etc to do it's magic.
In order not to clash with the GitHub Actions syntax, and to also avoid having to
add bunch of `{% raw %} ... {% endraw %}` blocks, we changed some things:

* Instead of `{%` and `%}` use `<%` and `%>`
* Instead of `{{` and `}}` use `<{` and `}>`

The rest of Jinja2 defaults apply.
