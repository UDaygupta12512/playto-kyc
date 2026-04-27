FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app/backend

# System deps for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Copy built React app into Django serving directory
COPY --from=frontend-build /app/frontend/dist ./frontend_dist

# Build steps
RUN python manage.py migrate --noinput \
    && python manage.py collectstatic --noinput \
    && python seed.py

EXPOSE 8000

ENV DEBUG=False

CMD ["gunicorn", "playto_kyc.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
