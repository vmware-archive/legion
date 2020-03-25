requirements_in := $(wildcard requirements*.in)
requirements_out := $(subst in,txt,$(requirements_in))

py_files := $(shell find . -type f -name "*.py")

IMG ?= docker.artifactory.saltstack.net/salt-legion
TAG ?= latest

black: $(py_files)
	@black $?

docker-build:
	docker build -t $(IMG):$(TAG) .

docker-push:
	docker push $(IMG):$(TAG)

$(requirements_out): $(requirements_in)
	pip-compile $(subst txt,in,$@)
