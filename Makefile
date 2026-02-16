.PHONY: build up down restart shell logs clean

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart: down up

shell:
	docker compose exec dev bash

logs:
	docker compose logs -f dev

clean:
	docker compose down -v
	docker system prune -f

rebuild: clean build up
