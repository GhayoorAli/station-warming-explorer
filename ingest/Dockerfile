FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY swe_ingest ./swe_ingest
RUN pip install --no-cache-dir .
COPY nightly.sh ./
CMD ["python", "-m", "swe_ingest.cli", "--help"]
