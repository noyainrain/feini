PYTHON=python3
PIP=pip3

PIPFLAGS=$$([ -z "$$VIRTUAL_ENV" ] && echo --user) --upgrade

.PHONY: test
test:
	$(PYTHON) -m unittest

.PHONY: test-ext
test-ext:
	$(PYTHON) -m unittest discover --pattern="ext_test*.py"

.PHONY: type
type:
	mypy feini scripts

.PHONY: lint
lint:
	pylint feini scripts

.PHONY: check
check: type test test-ext lint

.PHONY: deps
deps:
	$(PIP) install $(PIPFLAGS) --requirement requirements.txt

.PHONY: deps-dev
deps-dev:
	$(PIP) install $(PIPFLAGS) --requirement requirements-dev.txt

.PHONY: release
release:
	scripts/release.sh

.PHONY: clean
clean:
	rm --recursive --force $$(find . -name __pycache__) .mypy_cache
