# Disposable PostgreSQL for the DB-marked tests (TEST_DATABASE_URL).
#
#   docker build -t acciones-ud-test-db tests/db
#   docker run --rm -d --name acciones-ud-test-db -p 55432:5432 acciones-ud-test-db
#
# The suite creates and drops its own schema (alembic upgrade head, then
# downgrade base on teardown), so this container must never point at a shared
# database. No volume on purpose: the container is disposable.
FROM postgres:16-alpine

ENV POSTGRES_USER=postgres \
    POSTGRES_DB=postgres

# POSTGRES_PASSWORD is supplied at run time (see README): never bake secrets
# into the image.
EXPOSE 5432

HEALTHCHECK --interval=2s --timeout=3s --retries=30 \
    CMD pg_isready -U postgres -d postgres || exit 1
