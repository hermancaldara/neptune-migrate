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

## setups the project
setup:
	python setup.py develop
	pip install -r requirements-local.txt
	pre-commit install

## runs all tests
test:
	pytest .

## cleans garbage left by builds and installation
clean:
	rm -rf build/ dist/ neptune_migrate.egg-info/ ; \
	find . -type d -name '__pycache__' -exec rm -rf {} \;

## builds the package locally
build:
	python setup.py build

## creates a source distribution
dist:
	python setup.py sdist

## publishs the package to PyPI
publish:
	python setup.py sdist upload
