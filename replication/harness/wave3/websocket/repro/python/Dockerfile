FROM python:3.13-slim
RUN pip install --no-cache-dir 'uvicorn[standard]==0.32.1' starlette==0.41.3 websockets==13.1
WORKDIR /app
COPY server.py /app/server.py
EXPOSE 8000
CMD ["python","-m","uvicorn","server:app","--host","0.0.0.0","--port","8000","--no-access-log","--log-level","warning","--ws","websockets"]
