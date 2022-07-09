PYTHON=python3
PIP=pip3

PIPFLAGS=$$([ -z "$$VIRTUAL_ENV" ] && echo --user) --upgrade

.PHONY: test
test:
	$(PYTHON) -m unittest

.PHONY: type
type:
	mypy feini

.PHONY: lint
lint:
	pylint -j 0 feini

.PHONY: check
check: type test lint

.PHONY: deps
deps:
	$(PIP) install $(PIPFLAGS) -r requirements.txt

.PHONY: deps-dev
deps-dev:
	$(PIP) install $(PIPFLAGS) -r requirements-dev.txt

.PHONY: release
release:
	scripts/release.sh

.PHONY: clean
clean:
	rm -rf $$(find . -name __pycache__) doc/build doc/micro

# TODO remove
.PHONY: help
help:
	@echo "test:            Run all unit tests"
	@echo "test-ext:        Run all extended/integration tests"
	@echo "test-ui:         Run all UI tests"
	@echo "                 BROWSER:       Browser to run the tests with. Defaults to"
	@echo '                                "firefox".'
	@echo "                 WEBDRIVER_URL: URL of the WebDriver server to use. If not set"
	@echo "                                (default), tests are run locally."
	@echo "                 TUNNEL_ID:     ID of the tunnel to use for remote tests"
	@echo "                 PLATFORM:      OS to run the remote tests on"
	@echo "                 SUBJECT:       Text included in subject of remote tests"
	@echo "watch-test:      Watch source files and run all unit tests on change"
	@echo "lint:            Lint and check the style of the code"
	@echo "check:           Run all code quality checks (test and lint)"
	@echo "deps:            Update the dependencies"
	@echo "deps-dev:        Update the development dependencies"
	@echo "doc:             Build the documentation"
	@echo "sample:          Set up some sample data. Warning: All existing data in the"
	@echo "                 database will be deleted."
	@echo "                 REDISURL: URL of the Redis database. See"
	@echo "                           python3 -m {package} --redis-url command line"
	@echo "                           option."
	@echo "show-deprecated: Show deprecated code ready for removal (deprecated for at"
	@echo "                 least six months)"
	@echo "release:         Make a new release"
	@echo "                 FEATURE: Corresponding feature branch"
	@echo "                 VERSION: Version number"
	@echo "micro-link:      Link micro from a local repository. Useful when simultaneously"
	@echo "                 editing micro."
	@echo "                 MICROPATH: Location of local micro repository"
	@echo "clean:           Remove temporary files"
