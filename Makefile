.PHONY: build up down restart logs logs-flask logs-nginx logs-gunicorn shell clean prune ps reset run-dev help

# Default target
all: help

# Build the Docker images
build:
	docker-compose build

# Start the services
up:
	docker-compose up -d

# Stop the services
down:
	docker-compose down

# Restart the services
restart:
	docker-compose restart

# View logs from all services
logs:
	docker-compose logs -f

# View logs from Flask application only
logs-flask:
	docker-compose logs -f flask_app

# View logs from Nginx only
logs-nginx:
	docker-compose logs -f nginx

# View Gunicorn logs (inside the container)
logs-gunicorn:
	docker exec -it flask_app cat /var/log/gunicorn/access.log
	@echo "\n--- Error Logs ---\n"
	docker exec -it flask_app cat /var/log/gunicorn/error.log

# Open a shell in the Flask container
shell:
	docker-compose exec flask_app /bin/bash

# Remove containers and networks
clean:
	docker-compose down

# Deep clean - remove containers, networks, and volumes
prune:
	docker-compose down -v
	docker system prune -f

# View running containers
ps:
	docker-compose ps

# Reset everything and start fresh
reset: prune build up
	@echo "Application has been reset and is now running"

# Run the app in development mode (without Docker)
run-dev:
	FLASK_APP=app.py FLASK_ENV=development flask run --host=0.0.0.0 --port=5000

# Help command
help:
	@echo "Flask Transportation Scheduler Makefile Commands:"
	@echo "make build       - Build the Docker images"
	@echo "make up          - Start the application"
	@echo "make down        - Stop the application"
	@echo "make restart     - Restart the application"
	@echo "make logs        - View logs from all services"
	@echo "make logs-flask  - View Flask application logs"
	@echo "make logs-nginx  - View Nginx logs"
	@echo "make logs-gunicorn - View Gunicorn access and error logs"
	@echo "make shell       - Open a shell in the Flask container"
	@echo "make clean       - Remove containers and networks"
	@echo "make prune       - Deep clean (remove containers, networks, volumes)"
	@echo "make ps          - View running containers"
	@echo "make reset       - Reset everything and start fresh"
	@echo "make run-dev     - Run in development mode without Docker"