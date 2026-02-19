FROM python:3.11-slim

WORKDIR /app

# tini for proper signal handling in CI (optional but nice)
RUN apt-get update && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY doc_quality /app/doc_quality

RUN pip install --no-cache-dir .

WORKDIR /work
ENTRYPOINT ["/usr/bin/tini", "--", "doc-quality"]
