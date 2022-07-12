include config.mk
PYTHON_VERSION ?= 3.8.13
PY_SUFFIX ?= $(shell echo $(PYTHON_VERSION) | sed -r 's/([0-9]+)(\.[0-9]+)(\.[0-9]+)/\1\2/')
TARGET_DIRNAME := $(shell dirname $(TARGET_DIR))
TARGET_BASENAME := $(shell basename $(TARGET_DIR))

SALT_VERSION = $(shell $(TARGET_DIR)/salt --version | awk '{ print $$2 }')
ARCH := $(shell uname -m)


.PHONY: all $(SCRIPTS)

all: $(SCRIPTS_DIR)/salt

clean: ;
	rm -rf $(TARGET_DIRNAME)


onedir: salt-$(SALT_VERSION)_$(ARCH).tar.xz
	echo $(SALT_VERSION)

$(TARGET_DIR):
	mkdir -p $(TARGET_DIR)

$(TARGET_DIRNAME)/Python-$(PYTHON_VERSION).tar.xz: $(TARGET_DIR)
	curl https://www.python.org/ftp/python/$(PYTHON_VERSION)/Python-$(PYTHON_VERSION).tar.xz -o $(TARGET_DIRNAME)/Python-$(PYTHON_VERSION).tar.xz
	touch $@

$(TARGET_DIRNAME)/Python-$(PYTHON_VERSION): $(TARGET_DIRNAME)/Python-$(PYTHON_VERSION).tar.xz
	cd $(TARGET_DIRNAME); \
	tar xvf Python-$(PYTHON_VERSION).tar.xz; \
	touch $@; \
	cd $(PWD)

$(TARGET_DIR)/bin/python$(PY_SUFFIX):  $(TARGET_DIRNAME)/Python-$(PYTHON_VERSION)
	cd $(TARGET_DIRNAME)/Python-$(PYTHON_VERSION); \
	./configure --prefix=$(TARGET_DIR) ; \
	make -j4; \
	make install;

$(TARGET_DIR)/.onedir:
	pkg/fixlibs.sh $(TARGET_DIR)/lib
	touch $(TARGET_DIR)/.onedir

$(SCRIPTS_DIR)/salt-pip: $(TARGET_DIR)/bin/python$(PY_SUFFIX) $(TARGET_DIR)/.onedir
	cp $(PWD)/scripts/salt-pip $(SCRIPTS_DIR)/salt-pip
	sed -i 's/^#!.*$$/#!\/bin\/sh\n"exec" "`dirname $$0`\/$(PYBIN)" "$$0" "$$@"/' $@;

$(SCRIPTS_DIR)/salt: $(SCRIPTS_DIR)/salt-pip $(DYNLOAD) $(DYNLIB)
	$(SCRIPTS_DIR)/salt-pip install .


$(SCRIPTS): $(SCRIPTS_DIR)/salt
	mv $(TARGET_DIR)/bin/$@ $(SCRIPTS_DIR);
	sed -i 's/^#!.*$$/#!\/bin\/sh\n"exec" "`dirname $$0`\/$(PYBIN)" "$$0" "$$@"/' $(SCRIPTS_DIR)/$@;

$(TARGET_DIR)/install-salt:
	cp $(PWD)/scripts/install-salt $(SCRIPTS_DIR)/install-salt

$(TARGET_DIR)/uninstall-salt:
	cp $(PWD)/scripts/uninstall-salt $(SCRIPTS_DIR)/uninstall-salt

salt-$(SALT_VERSION)_$(ARCH).tar.xz: $(SCRIPTS) $(TARGET_DIR)/install-salt $(TARGET_DIR)/uninstall-salt
	find $(TARGET_DIR) -name '*.pyc' -exec rm -f {} \;
	# XXX: Should we keep this?
	#rm -rf $(TARGET_DIR)/include $(TARGET_DIR)/share
	tar cJvf salt-$(SALT_VERSION)_$(ARCH).tar.xz -C $(TARGET_DIRNAME) $(TARGET_BASENAME);
