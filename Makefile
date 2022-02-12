.SILENT:

.DEFAULT_GOAL = help

COLOR_RESET = \033[0m
COLOR_GREEN = \033[32m
COLOR_YELLOW = \033[33m

PROJECT_NAME = `basename $(PWD)`

## prints this help
help:
	printf "\n${COLOR_YELLOW}${PROJECT_NAME}${COLOR_RESET}\n\n"
	awk '/^[a-zA-Z0-9.%_-]+:/ { \
		helpMessage = match(lastLine, /^## (.+)/); \
		if (helpMessage) { \
			helpCommand = substr($$1, 0, index($$1, ":")); \
			helpMessage = substr(lastLine, RSTART + 3, RLENGTH); \
			printf "${COLOR_GREEN}$$ make %s${COLOR_RESET} %s\n", helpCommand, helpMessage; \
		} \
	} \
	{ lastLine = $$0 }' $(MAKEFILE_LIST)
	printf "\n"

## cleans garbage left by builds and installation
clean:
	@echo "Cleaning..."
	@rm -rf build dist neptune_migrate.egg-info *.pyc **/*.pyc *~
	@#removing test temp files
	@rm -rf `date +%Y`*

## compiles .py files (just to check for syntax errors)
compile: clean
	@echo "Compiling source code..."
	@rm -rf neptune_migrate/*.pyc
	@rm -rf tests/*.pyc
	@python -tt -m compileall neptune_migrate
	@python -tt -m compileall tests

## executes all simple-virtuoso-migrate tests
test: compile
	@make clean
	@echo "Starting tests..."
	@pytest .
	@make clean

## install simple-virtuoso-migrate
install:
	python setup.py develop
	pip install -r requirements-local.txt
	pre-commit install

## builds without installing simple-virtuoso-migrate
build:
	@/usr/bin/env python ./setup.py build

## creates egg for distribution
dist: clean
	@python setup.py sdist

## publishs the package to PyPI
publish: dist
	@python setup.py sdist upload
