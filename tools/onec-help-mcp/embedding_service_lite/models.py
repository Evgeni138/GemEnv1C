from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field


class EmbedHelpRequest(BaseModel):
    """
    Запрос на генерацию dense эмбеддингов:
    {
      "texts": [...],
      "task": "passage" | ...
    }
    """

    texts: List[str] = Field(default_factory=list)
    task: Optional[str] = Field(default=None)


class EmbedSparseRequest(BaseModel):
    """
    Совместима с EmbedSparseRequest:
    {
      "texts": [...],
      "collection_name": "1c_help_8_3_26"
    }
    """

    texts: List[str] = Field(default_factory=list)
    collection_name: str


class Bm25BuildCorpusRequest(BaseModel):
    """
    Совместима с Bm25BuildCorpusRequest:
    {
      "corpus": [...],
      "collection_name": "1c_help_8_3_26"
    }
    """

    corpus: List[str] = Field(default_factory=list)
    collection_name: str


class SparseEmbedding(BaseModel):
    indices: List[int] = Field(default_factory=list)
    values: List[float] = Field(default_factory=list)


class EmbedResponse(BaseModel):
    embeddings: List[List[float]] = Field(default_factory=list)


class EmbedSparseResponse(BaseModel):
    embeddings: List[SparseEmbedding] = Field(default_factory=list)


class Bm25BuildCorpusResponse(BaseModel):
    status: str
    collection_name: str
    documents: int


class HealthResponse(BaseModel):
    status: str
    backend: str
    model: str
    device: str


class ModelInfoResponse(BaseModel):
    model: str
    dimension: int
    device: str
    backend: str
    extra: Dict[str, Any] = Field(default_factory=dict)

