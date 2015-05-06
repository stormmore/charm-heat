#!/usr/bin/make
PYTHON := /usr/bin/env python

lint:
	@echo -n "Running flake8 tests: "
	@flake8 --exclude hooks/charmhelpers hooks
	@flake8 unit_tests
	@echo "OK"
	@echo -n "Running charm proof: "
	@charm proof
	@echo "OK"

bin/charm_helpers_sync.py:
	@mkdir -p bin
	@bzr cat lp:charm-helpers/tools/charm_helpers_sync/charm_helpers_sync.py \
	> bin/charm_helpers_sync.py

sync: bin/charm_helpers_sync.py
	@$(PYTHON) bin/charm_helpers_sync.py -c charm-helpers.yaml

unit_test:
	@$(PYTHON) /usr/bin/nosetests --nologcapture --with-coverage  unit_tests

test:
	@echo "Running amulet tests: "
	@for f in tests/*; do $$f; done

all: unit_test lint
