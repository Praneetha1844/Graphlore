FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRAPHLORE_ONTOLOGY=/app/ontology/default.yaml \
    GRAPHLORE_GAZETTEER=/app/ontology/gazetteer.yaml

RUN useradd --create-home --uid 1000 graphlore
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY ontology ./ontology
RUN pip install --no-cache-dir .

USER graphlore
WORKDIR /workspace
ENTRYPOINT ["graphlore"]
CMD ["--help"]
