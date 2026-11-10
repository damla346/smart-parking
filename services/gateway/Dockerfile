# Sahip: Berat (YOL_HARITASI.md §3, §10)
# Derleme bağlamı (build context): depo kökü (contracts/ erişimi için)
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY contracts /app/contracts
COPY services/gateway /app/services/gateway

RUN pip install --no-cache-dir /app/services/gateway

EXPOSE 8000

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
