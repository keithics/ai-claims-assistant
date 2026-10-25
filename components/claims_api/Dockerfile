FROM python:3.12-slim
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY components/shared /src/shared
COPY components/claims_api /src/claims_api
RUN pip install --no-cache-dir /src/shared /src/claims_api
COPY components/claims_api/seed /app/seed
ENV CLAIMS_API_SEED_DIR=/app/seed
USER app
EXPOSE 8001
CMD ["uvicorn", "claims_api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]
