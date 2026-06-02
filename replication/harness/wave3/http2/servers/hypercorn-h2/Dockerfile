FROM python:3.12-slim
RUN pip install --no-cache-dir hypercorn==0.17.3 h2==4.1.0
WORKDIR /app
COPY app.py /app/app.py
EXPOSE 8000
# Plaintext bind; hypercorn auto-detects HTTP/1 or HTTP/2 client preface.
CMD ["hypercorn", "--bind", "0.0.0.0:8000", "--workers", "1", "app:app"]
