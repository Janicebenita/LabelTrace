FROM python:3.12.11-slim
WORKDIR /app
COPY backend/requirements-lock.txt /app/backend/requirements-lock.txt
RUN pip install --no-cache-dir -r backend/requirements-lock.txt
COPY backend /app/backend
COPY migrations /app/migrations
COPY alembic.ini manage.py /app/
COPY fixtures /app/fixtures
RUN mkdir -p /app/artifacts /app/data
EXPOSE 8000
