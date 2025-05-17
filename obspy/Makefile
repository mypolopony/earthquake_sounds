# Project Name
IMAGE_NAME=obspy-producer
TAG=latest

# Docker Platform (uncomment if you're on ARM Mac and targeting x86)
# PLATFORM=--platform=linux/amd64

# Docker build context
BUILD_CONTEXT=.

# Default target
.PHONY: all
all: build

# Build the Docker image using multi-stage Dockerfile
.PHONY: build
build:
	docker build $(PLATFORM) -t $(IMAGE_NAME):$(TAG) $(BUILD_CONTEXT)

# Run the Docker container
.PHONY: run
run:
	docker run --rm $(IMAGE_NAME):$(TAG)

# Run with arguments passed to Python (e.g., make run-args ARGS="--count 20")
.PHONY: run-args
run-args:
	docker run --rm $(IMAGE_NAME):$(TAG) poetry run python produce.py $(ARGS)

# Push to a container registry (optional)
.PHONY: push
push:
	docker push $(IMAGE_NAME):$(TAG)

# Clean up intermediate and dangling images
.PHONY: clean
clean:
	docker system prune -f

# Show logs from the last container
.PHONY: logs
logs:
	docker logs `docker ps -lq`