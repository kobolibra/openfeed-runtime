FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements-runtime.lock ./
RUN pip install --no-cache-dir -r requirements-runtime.lock && useradd -u 10001 -m openfeed && mkdir -p /data && chown 10001:10001 /data
COPY openfeed/ ./openfeed/
COPY static/ ./static/
USER openfeed
EXPOSE 8765
CMD ["uvicorn", "openfeed.app:app", "--host", "0.0.0.0", "--port", "8765", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
