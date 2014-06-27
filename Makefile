.PHONY: all
all: venv test

.PHONY: venv
venv:
	tox -e venv

.PHONY: tests test
tests: test
test:
	# TODO: why do namespace packages need --recreate?
	tox --recreate

.PHONY: clean
clean:
	find . -iname '*.pyc' | xargs rm -f
	rm -rf .tox
	rm -rf ./venv-*
