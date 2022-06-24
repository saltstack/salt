PWD := $(shell pwd)
# What python version will be installed
PYTHON_VERSION := 3.8.13
# The target where we will install python
TARGET_DIR := $(PWD)/build/salt
# The scripts directory which will contain Salt's scripts
SCRIPTS_DIR := $(TARGET_DIR)
# This interpreter will be used for the shebang in Salt's scripts. Properly
# escape forward slashes to be used with sed
PYBIN := bin\/python3
# The names of Salt's scripts
SCRIPTS ?= salt salt-api salt-call salt-cloud salt-cp salt-key salt-master salt-minion salt-proxy salt-run salt-ssh salt-syndic spm
