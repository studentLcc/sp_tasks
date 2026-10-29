FROM python:3.12-slim

WORKDIR /app
COPY bridge /app/bridge

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BRIDGE_HOST=127.0.0.1 \
    BRIDGE_PORT=8787 \
    TZ=Asia/Shanghai

RUN useradd --create-home --uid 10001 bridge
USER bridge

EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('BRIDGE_PORT', '8787') + '/health', timeout=3)"]

CMD ["python", "-m", "bridge.app"]
