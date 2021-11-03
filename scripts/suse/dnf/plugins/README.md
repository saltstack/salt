## What it is

Plugin which provides a notification mechanism to Salt, if DNF is
used outside of it.

## Installation

Configuration files are going to:

	`/etc/dnf/plugins/[name].conf`

Plugin itself goes to:

	`%{python_sitelib}/dnf-plugins/[name].py`
	The path to dnf-plugins directory is Python version dependant.

## Permissions

User:  root
Group: root
Mode:  644
