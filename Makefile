up:
	docker-compose up --build

migrate:
	alembic upgrade head

test:
	pytest -q
