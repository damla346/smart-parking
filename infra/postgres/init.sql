-- Sahip: Damla. Konteyner ilk kez oluşturulurken bir kez koşar.
-- Şema Alembic ile yönetilir; burası yalnız uzantılar ve kodlama içindir.

CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- plaka araması için (SessionLog filtresi)
