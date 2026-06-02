FROM python:3.12-slim
RUN pip install --no-cache-dir h2==4.1.0
WORKDIR /app
COPY h2_probe.py /app/h2_probe.py
ENTRYPOINT ["python", "/app/h2_probe.py"]
