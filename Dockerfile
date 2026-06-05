FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY orchestrator ./orchestrator
COPY playbooks ./playbooks
COPY fixtures ./fixtures

ENTRYPOINT ["python", "-m", "orchestrator"]
