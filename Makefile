.PHONY: help check lint format-check typecheck test fmt e2e docker-build docker-scan

DOMAINS_FILE ?= docs/domains.txt
OUTPUT_FILE ?= output.json
DETAILS_FILE ?= output.details.json
IMAGE ?= techscope:local

help:
	@echo 'check         lint, format check, type check and the offline tests'
	@echo 'fmt           format the code and apply safe lint fixes'
	@echo 'test          the offline test suite only'
	@echo 'e2e           live scan of $(DOMAINS_FILE), timed'
	@echo 'docker-build  build the $(IMAGE) image'
	@echo 'docker-scan   run the same scan inside the container'

check: lint format-check typecheck test

lint:
	uv run ruff check .

format-check:
	uv run ruff format --check .

typecheck:
	uv run mypy

test:
	uv run pytest -q

fmt:
	uv run ruff format .
	uv run ruff check --fix .

e2e:
	uv sync
	/usr/bin/time -p uv run techscope scan $(DOMAINS_FILE) -o $(OUTPUT_FILE) --details $(DETAILS_FILE) --log-level INFO

docker-build:
	docker build --target cli -t $(IMAGE) .

docker-scan:
	# --user keeps the bind-mounted output writable on Linux, where the host uid is preserved.
	# The scanner needs no capabilities and writes only to the mount, so it is given neither.
	docker run --rm --read-only --cap-drop ALL --security-opt no-new-privileges \
		--user "$$(id -u):$$(id -g)" -v "$(CURDIR):/data" $(IMAGE) \
		scan $(DOMAINS_FILE) -o $(OUTPUT_FILE) --details $(DETAILS_FILE) --log-level INFO
