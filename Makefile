.PHONY: bootstrap bootstrap-dev deploy verify verify-scenario test build

bootstrap:
	sudo ./scripts/bootstrap.sh

bootstrap-dev:
	sudo ./scripts/bootstrap.sh --dev-ubuntu-22.04

deploy:
	./scripts/deploy.sh

verify:
	./scripts/verify.sh

verify-scenario:
	./scripts/verify-scenario.py

test:
	python3 -m unittest discover -s tests -p 'test_*.py'

build:
	docker build --tag trafficops-demo:0.1.0 --file Dockerfile .
