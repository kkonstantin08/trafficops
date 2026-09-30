.PHONY: bootstrap deploy verify test build

bootstrap:
	sudo ./scripts/bootstrap.sh

deploy:
	./scripts/deploy.sh

verify:
	./scripts/verify.sh

test:
	python3 -m unittest discover -s tests -p 'test_*.py'

build:
	docker build --tag trafficops-demo:0.1.0 --file Dockerfile .
