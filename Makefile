#
# Copyright 2013, Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

# general variables
VENV=test_env
SRC=resultsdb

# Variables used for packaging
SPECFILE=$(SRC).spec
BASEARCH:=$(shell uname -i)
DIST:=$(shell rpm --eval '%{dist}')
VERSION:=$(shell rpmspec -q --queryformat="%{VERSION}\n" $(SPECFILE) | uniq)
RELEASE:=$(subst $(DIST),,$(shell rpmspec -q --queryformat="%{RELEASE}\n" $(SPECFILE) | uniq))
NVR:=$(SRC)-$(VERSION)-$(RELEASE)
GITBRANCH:=$(shell git rev-parse --abbrev-ref HEAD)
TARGETDIST:=fc27
BUILDTARGET=fedora-27-x86_64

.PHONY: test
test: $(VENV)
	sh -c "set -e; . $(VENV)/bin/activate; python setup.py develop; \
	       TEST='true' py.test --cov-report=term-missing --cov $(SRC); deactivate"

.PHONY: test-ci
test-ci: $(VENV)
	sh -c "set -e; . $(VENV)/bin/activate; python setup.py develop; \
	       TEST='true' py.test --cov-report=xml --cov $(SRC); deactivate"

.PHONY: pylint
pylint:
	pylint -f parseable $(SRC) | tee pylint.out

.PHONY: pep8
pep8:
	pep8 $(SRC)/*.py $(SRC)/*/*.py | tee pep8.out

.PHONY: ci
ci: test-ci pylint pep8

.PHONY: docs
docs:
	sphinx-build  -b html -d docs/_build/doctrees docs/source docs/_build/html

.PHONY: clean
clean:
	rm -rf dist
	rm -rf resultsdb.egg-info
	rm -rf build
	rm -f pep8.out
	rm -f pylint.out

.PHONY: archive
archive: $(SRC)-$(VERSION).tar.gz

.PHONY: $(SRC)-$(VERSION).tar.gz
$(SRC)-$(VERSION).tar.gz:
	git archive $(GITBRANCH) --prefix=$(SRC)-$(VERSION)/ | gzip -c9 > $@

.PHONY: mocksrpm
mocksrpm: archive
	mock -r $(BUILDTARGET) --buildsrpm --spec $(SPECFILE) --sources .
	cp /var/lib/mock/$(BUILDTARGET)/result/$(NVR).$(TARGETDIST).src.rpm .

.PHONY: mockbuild
mockbuild: mocksrpm
	mock -r $(BUILDTARGET) --no-clean --rebuild $(NVR).$(TARGETDIST).src.rpm
	cp /var/lib/mock/$(BUILDTARGET)/result/$(NVR).$(TARGETDIST).noarch.rpm .

#.PHONY: kojibuild
#kojibuild: mocksrpm
#	koji build --scratch dist-6E-epel-testing-candidate $(NVR).$(TARGETDIST).src.rpm

.PHONY: nvr
nvr:
	@echo $(NVR)

.PHONY: cleanvenv
cleanvenv:
	rm -rf $(VENV)

.PHONY: virtualenv
virtualenv: $(VENV)

.PHONY: $(VENV)
$(VENV):
	virtualenv --system-site-packages $(VENV)
	sh -c "set -e; . $(VENV)/bin/activate; \
	       pip install -r requirements.txt; deactivate"
