#
# Simple makefile for building at LinkedIn
#

.DEFAULT: help
DEFAULT: help

build:
	python setup.py build

install:
	sudo python setup.py install

help:
	@echo "Enter a target:"
	@echo "	build	Runs 'setup.py build'"
	@echo "	install	Runs 'sudo setup.py install'"
	@echo "	help	This message."

# End of file.
