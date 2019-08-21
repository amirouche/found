.PHONY: help doc

init: ## Prepare the host sytem for development
	wget https://www.foundationdb.org/downloads/6.1.12/ubuntu/installers/foundationdb-clients_6.1.12-1_amd64.deb
	sudo dpkg -i foundationdb-clients_6.1.12-1_amd64.deb
	wget https://www.foundationdb.org/downloads/6.1.12/ubuntu/installers/foundationdb-server_6.1.12-1_amd64.deb
	sudo dpkg -i foundationdb-server_6.1.12-1_amd64.deb
	pip3 install --upgrade pipenv
	pipenv install --dev --skip-lock
	pipenv run python setup.py develop
	pipenv run pre-commit install
	@echo "\033[95m\n\nYou may now run 'pipenv shell'.\n\033[0m"

check: ## Run tests
	make database-clear
	pipenv run py.test -vv --capture=no tests.py
	pipenv check
	pipenv run bandit --skip=B101 -r found/
	@echo "\033[95m\n\nYou may now run 'make lint' or 'make check-coverage'.\n\033[0m"

check-coverage: ## Code coverage
	make database-clear
	pipenv run py.test -vv --cov-config .coveragerc --cov-report term --cov-report html --cov-report xml --cov=found/ tests.py


help: ## This help.
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

lint: ## Lint the code
	pipenv run pylint found/

doc: ## Build the documentation
	cd doc && make html
	@echo "\033[95m\n\nBuild successful! View the docs homepage at doc/build/html/index.html.\n\033[0m"

clean: ## Clean up
	git clean -fX

database-clear:  ## Remove all data from the database
	fdbcli --exec "writemode on; clearrange \x00 \xFF;"

todo: ## Things that should be done
	@grep -nR --color=always TODO found/

xxx: ## Things that require attention
	@grep -nR --color=always --before-context=2  --after-context=2 XXX found/

release:  ## Prepare a release
	python setup.py sdist bdist_wheel
	@echo "\033[95m\n\nBuild successful! You can now run 'python setup.py sdist upload'.\n\033[0m"
