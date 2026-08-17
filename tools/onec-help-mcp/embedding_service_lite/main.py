import logging
import time
from typing import Dict, Any

from fastapi import FastAPI, HTTPException

from .config import get_settings
from .dense_backend import DenseEncoder
from .bm25_backend import bm25_manager
from .models import (
    EmbedHelpRequest,
    EmbedSparseRequest,
    Bm25BuildCorpusRequest,
    EmbedResponse,
    EmbedSparseResponse,
    Bm25BuildCorpusResponse,
    HealthResponse,
    ModelInfoResponse,
    SparseEmbedding,
)


settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("embedding_service_lite")

app = FastAPI(title="Embedding Service Lite for 1C Help")


_dense_encoder = DenseEncoder()


@app.post("/embed", response_model=EmbedResponse)
async def embed_handler(request: EmbedHelpRequest) -> Dict[str, Any]:
    """
    POST /embed: {texts, task} -> {embeddings}.
    Генерирует dense эмбеддинги для списка текстов.
    """
    if not request.texts:
        return {"embeddings": []}

    if len(request.texts) > settings.max_batch_size:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Batch size {len(request.texts)} exceeds maximum allowed "
                f"{settings.max_batch_size}"
            ),
        )

    start_time = time.time()
    embeddings = await _dense_encoder.encode_batch(request.texts)
    elapsed = time.time() - start_time

    logger.info(
        "Batch embedding completed: %s texts, %.2fs (%.1fms per text)",
        len(request.texts),
        elapsed,
        elapsed / len(request.texts) * 1000.0,
    )

    return {"embeddings": embeddings}


@app.post("/embed/sparse", response_model=EmbedSparseResponse)
async def embed_sparse_handler(request: EmbedSparseRequest) -> Dict[str, Any]:
    """
    POST /embed/sparse: {texts, collection_name} -> {embeddings: [{indices, values}, ...]}.
    Генерирует sparse (BM25) эмбеддинги для списка текстов с учётом коллекции.
    """
    if not request.texts:
        return {"embeddings": []}

    if len(request.texts) > settings.max_batch_size:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Batch size {len(request.texts)} exceeds maximum allowed "
                f"{settings.max_batch_size}"
            ),
        )

    start_time = time.time()
    try:
        embeddings = []
        for text in request.texts:
            vec = bm25_manager.calculate_sparse_vector(request.collection_name, text)
            embeddings.append(SparseEmbedding(**vec))
        elapsed = time.time() - start_time

        logger.info(
            "Batch sparse embedding completed: %s texts, collection '%s', "
            "%.2fs (%.1fms per text)",
            len(request.texts),
            request.collection_name,
            elapsed,
            elapsed / len(request.texts) * 1000.0,
        )

        return {"embeddings": embeddings}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/bm25/build-corpus", response_model=Bm25BuildCorpusResponse)
async def bm25_build_corpus_handler(
    request: Bm25BuildCorpusRequest,
) -> Dict[str, Any]:
    """
    POST /bm25/build-corpus: {corpus, collection_name} -> 200 OK.
    Строит BM25 корпус для указанной коллекции.
    """
    if len(request.corpus) > settings.max_corpus_size:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Corpus size {len(request.corpus)} exceeds maximum allowed "
                f"{settings.max_corpus_size}"
            ),
        )

    start_time = time.time()
    try:
        ok = bm25_manager.build_corpus(request.collection_name, request.corpus)
    except Exception as e:  # pragma: no cover - защитный код
        logger.exception("BM25 build_corpus failed")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build BM25 corpus: {e!s}",
        ) from e
    elapsed = time.time() - start_time

    if not ok:
        raise HTTPException(
            status_code=500,
            detail="Failed to build BM25 corpus (empty or no valid documents)",
        )

    logger.info(
        "BM25 corpus built: collection '%s', %s documents, %.2fs",
        request.collection_name,
        len(request.corpus),
        elapsed,
    )

    return {
        "status": "ok",
        "collection_name": request.collection_name,
        "documents": len(request.corpus),
    }


@app.get("/health", response_model=HealthResponse)
async def health_handler() -> Dict[str, Any]:
    info = _dense_encoder.get_backend_info()
    return {
        "status": "ok",
        "backend": info.get("backend", "sentence-transformers"),
        "model": info.get("model", ""),
        "device": info.get("device", "cpu"),
    }


@app.get("/model-info", response_model=ModelInfoResponse)
async def model_info_handler() -> Dict[str, Any]:
    info = _dense_encoder.get_backend_info()
    return {
        "model": info.get("model", ""),
        "dimension": info.get("dimension") or 0,
        "device": info.get("device", "cpu"),
        "backend": info.get("backend", "sentence-transformers"),
        "extra": {},
    }

