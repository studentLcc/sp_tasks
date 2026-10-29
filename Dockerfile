FROM python:3.12-slim
WORKDIR /app
COPY bridge /app/bridge
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "bridge.app"]

