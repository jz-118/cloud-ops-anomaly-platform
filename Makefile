SHELL := /bin/bash
NAMESPACE ?= cloud-ops
RELEASE ?= cloud-ops
KUBECTL ?= kubectl
HELM ?= helm

.PHONY: check install-k3s install-monitoring secrets deploy verify test demo clean

check:
	./deploy/scripts/preflight.sh

install-k3s:
	./deploy/scripts/install-k3s.sh

install-monitoring:
	./deploy/scripts/install-monitoring.sh

secrets:
	./deploy/scripts/create-secrets.sh

deploy:
	./deploy/scripts/deploy.sh

verify:
	./deploy/scripts/verify.sh

test:
	python3 -m pytest anomaly-detector/tests demo-app/tests

demo:
	./deploy/scripts/run-demo.sh

clean:
	$(HELM) uninstall $(RELEASE) -n $(NAMESPACE)

