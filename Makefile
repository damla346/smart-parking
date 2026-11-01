# Sahip: Damla
.PHONY: up down reset install mocks core gateway web test lint seed

up:                ## postgres + redis ayağa kaldır
	docker compose up -d

down:              ## konteynerleri durdur
	docker compose down

reset:             ## veritabanını sıfırla (volume dahil)
	docker compose down -v && docker compose up -d

install:           ## üç paketin bağımlılıkları
	pip install -e ./services/core[dev] -e ./services/gateway[dev]
	cd web && npm install

mocks:             ## gün 0 sahteleri: mock_core:8101 + mock_gateway:8100
	python infra/mocks/mock_core.py & \
	python infra/mocks/mock_gateway.py

# contracts/ kurulabilir bir paket değil, depo kökünden import ediliyor. pytest bunu
# pyproject'teki pythonpath ile, alembic ise alembic.ini'deki prepend_sys_path ile
# çözüyor; uvicorn'un karşılığı yok, o yüzden PYTHONPATH burada veriliyor. Olmazsa
# servis "No module named 'contracts'" ile açılmıyor.
core:              ## Damla
	cd services/core && PYTHONPATH=../.. uvicorn core.main:app --reload --port 8001

gateway:           ## Berat
	cd services/gateway && PYTHONPATH=../.. uvicorn gateway.main:app --reload --port 8000

web:               ## Esra
	cd web && npm run dev

test:
	cd services/core && pytest -q
	cd services/gateway && pytest -q
	cd web && npm run typecheck

lint:
	ruff check services/ infra/ contracts/

seed:              ## demo verisi (havuz görevi #1)
	python infra/seed/seed_data.py
