import os
from collections.abc import Callable, Sequence
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from agent_app.approval import ApprovalError, ApprovalService
from agent_app.budget import BudgetStateReader, blob_fetcher
from agent_app.chat import ChatService, RequestError
from agent_app.config import ConfigError, Settings
from agent_app.fakes import FAKE_MODE_ENV, build_fake_service
from agent_app.llm import GatewayChatClient, ModelError
from agent_app.routing import load_routing
from agent_app.schemas import (
    ApprovalRequest,
    ApproveResponse,
    ChatRequest,
    ChatResponse,
    CountryInfo,
    DocumentView,
    RejectResponse,
)
from agent_app.tools import ClaimsClient, RestrictedClaims
from country_packs import load_country_packs, load_model_catalog, prices_from_catalog
from rag import AzureSearchBackend, OpenAIEmbedder, Retriever, load_policy_documents
from router import BudgetState
from telemetry import app_env, configure


def build_service(settings: Settings) -> ChatService:
    packs = load_country_packs()
    catalog = load_model_catalog()
    if settings.chat_deployment not in catalog.deployments:
        raise ConfigError(
            f"AGENT_CHAT_DEPLOYMENT {settings.chat_deployment!r} is not in models.yaml; "
            f"known: {', '.join(sorted(catalog.deployments))}"
        )
    retriever = Retriever(
        AzureSearchBackend(settings.search_endpoint, settings.index_name),
        OpenAIEmbedder(
            settings.gateway_url,
            settings.gateway_keys,
            settings.embedding_deployment,
            settings.api_version,
            app="agent_app",
        ),
        packs,
        top_k=settings.top_k,
    )
    claims_client = ClaimsClient(settings.claims_api_url, api_key=settings.claims_api_key or None)
    restricted = RestrictedClaims(claims_client)
    return ChatService(
        env=app_env(),
        packs=packs,
        retriever=retriever,
        chat=GatewayChatClient(
            settings.gateway_url,
            settings.gateway_keys,
            settings.api_version,
            {name: d.tier for name, d in catalog.deployments.items()},
        ),
        claims=restricted,
        approvals=ApprovalService(
            restricted,
            claims_client,
            settings.approval_signing_key,
            ttl_seconds=settings.approval_ttl_seconds,
        ),
        deployment=settings.chat_deployment,
        max_output_tokens=settings.max_output_tokens,
        prices=prices_from_catalog(catalog),
        tiers={name: d.tier for name, d in catalog.deployments.items()},
        max_steps=settings.max_steps,
        documents={d.doc_id: d for d in load_policy_documents(packs=packs)},
        routing=load_routing(settings.routing_path, catalog.deployments),
        allow_tier_override=settings.allow_tier_override,
        budget_state=_budget_state(settings),
    )


def _budget_state(settings: Settings) -> Callable[[str], BudgetState]:
    if not settings.budget_state_account_url:
        return lambda country: "ok"
    return BudgetStateReader(
        blob_fetcher(settings.budget_state_account_url, settings.budget_state_container)
    )


DEFAULT_CORS_ORIGINS = ("http://localhost:5273", "http://localhost:5173")


def cors_origins_from_env() -> Sequence[str]:
    raw = os.environ.get("AGENT_CORS_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins or DEFAULT_CORS_ORIGINS


def create_app(
    service: ChatService | None = None, cors_origins: Sequence[str] | None = None
) -> FastAPI:
    def default_factory() -> ChatService:
        if os.environ.get(FAKE_MODE_ENV) == "1":
            fake_env = {
                "AGENT_GATEWAY_URL": "https://fake-mode.invalid",
                "GATEWAY_KEY_FAKE": "fake",
                "RAG_SEARCH_ENDPOINT": "https://fake-mode.invalid",
                **os.environ,
            }
            return build_fake_service(Settings.from_env(fake_env))
        return build_service(Settings.from_env())

    factory: Callable[[], ChatService] = (
        (lambda: service) if service is not None else default_factory
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        configure("agent_app")
        app.state.service = factory()
        yield

    app = FastAPI(
        title="Kalayaan Mutual claims assistant",
        version="0.1.0",
        lifespan=lifespan,
        generate_unique_id_function=lambda route: route.name if isinstance(route, APIRoute) else "",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins or cors_origins_from_env()),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/countries", response_model=list[CountryInfo])
    def countries() -> list[CountryInfo]:
        packs = app.state.service.packs
        return [
            CountryInfo(code=p.code, name=p.name, languages=list(p.languages))
            for p in sorted(packs.values(), key=lambda p: p.code)
        ]

    @app.get("/documents/{doc_id}", response_model=DocumentView)
    def document(doc_id: str) -> DocumentView:
        doc = app.state.service.documents.get(doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail=f"no document {doc_id!r}")
        return DocumentView(
            doc_id=doc.doc_id,
            title=doc.title,
            country=doc.country,
            language=doc.language,
            body=doc.body,
        )

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        service: ChatService = app.state.service
        try:
            return service.answer(request)
        except RequestError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ModelError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/approve", response_model=ApproveResponse)
    def approve(request: ApprovalRequest) -> ApproveResponse:
        service: ChatService = app.state.service
        try:
            claim = service.approvals.approve(request.claim_id, request.token)
        except ApprovalError as exc:
            raise _approval_http_error(exc) from exc
        return ApproveResponse(status="filed", claim=claim)

    @app.post("/reject", response_model=RejectResponse)
    def reject(request: ApprovalRequest) -> RejectResponse:
        service: ChatService = app.state.service
        try:
            claim_id = service.approvals.reject(request.claim_id, request.token)
        except ApprovalError as exc:
            raise _approval_http_error(exc) from exc
        return RejectResponse(status="rejected_by_user", claim_id=claim_id)

    return app


def _approval_http_error(exc: ApprovalError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail={"code": exc.code, "message": str(exc)})
