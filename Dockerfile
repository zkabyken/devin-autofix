FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY orchestrator ./orchestrator
COPY playbooks ./playbooks
COPY fixtures ./fixtures

RUN useradd --create-home --uid 10001 autofix \
    && mkdir -p /app/out \
    && chown -R autofix /app
USER autofix

ENTRYPOINT ["python", "-m", "orchestrator"]
