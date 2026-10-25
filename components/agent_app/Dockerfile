FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY components/shared /src/shared
COPY components/country_packs /src/country_packs
COPY components/rag /src/rag
COPY components/router /src/router
COPY components/agent_app /src/agent_app
RUN pip install --no-cache-dir /src/shared /src/country_packs /src/rag /src/router /src/agent_app
COPY components/country_packs/countries /app/country_packs/countries
COPY components/country_packs/models.yaml /app/country_packs/models.yaml
COPY components/rag/data/policies /app/policies
COPY components/router/routing.yaml /app/routing.yaml
ENV COUNTRY_PACKS_DIR=/app/country_packs \
    RAG_POLICIES_DIR=/app/policies \
    ROUTING_CONFIG_PATH=/app/routing.yaml
USER app
EXPOSE 8000
CMD ["uvicorn", "agent_app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
