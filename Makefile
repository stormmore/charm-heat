#!/usr/bin/make
PYTHON := /usr/bin/env python

lint:
	@echo Lint inspections and charm proof...
	@flake8 --exclude hooks/charmhelpers hooks tests unit_tests
	@charm proof

unit_test:
	@echo Unit tests...
	@$(PYTHON) /usr/bin/nosetests --nologcapture --with-coverage unit_tests

test: unit_test
	@# Bundletester expects unit tests here.

functional_test:
	@echo Starting all functional, lint and unit tests...
	@juju test -v -p AMULET_HTTP_PROXY --timeout 2700

bin/charm_helpers_sync.py:
	@mkdir -p bin
	@bzr cat lp:charm-helpers/tools/charm_helpers_sync/charm_helpers_sync.py \
	> bin/charm_helpers_sync.py

sync: bin/charm_helpers_sync.py
	@$(PYTHON) bin/charm_helpers_sync.py -c charm-helpers-hooks.yaml
	@$(PYTHON) bin/charm_helpers_sync.py -c charm-helpers-tests.yaml

publish: lint unit_test
	bzr push lp:charms/heat
	bzr push lp:charms/trusty/heat
