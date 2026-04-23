from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import numpy as np

app = FastAPI(title="TeamUp ML Service")

# Load model on startup (downloads ~80MB on first run, cached after)
model = None

@app.on_event("startup")
def load_model():
    global model
    print("Loading sentence transformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Model loaded successfully!")


class EmbedRequest(BaseModel):
    text: str

class EmbedResponse(BaseModel):
    embedding: list[float]

class SimilarityRequest(BaseModel):
    embedding_a: list[float]
    embedding_b: list[float]

class SimilarityResponse(BaseModel):
    score: float


@app.post("/embed", response_model=EmbedResponse)
def generate_embedding(request: EmbedRequest):
    """Generate a 384-dim embedding for the given text."""
    embedding = model.encode(request.text).tolist()
    return EmbedResponse(embedding=embedding)


@app.post("/similarity", response_model=SimilarityResponse)
def compute_similarity(request: SimilarityRequest):
    """Compute cosine similarity between two embeddings."""
    a = np.array(request.embedding_a)
    b = np.array(request.embedding_b)
    score = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    return SimilarityResponse(score=score)


class BatchEmbedRequest(BaseModel):
    texts: list[str]

class BatchEmbedResponse(BaseModel):
    embeddings: list[list[float]]

@app.post("/batch_embed", response_model=BatchEmbedResponse)
def batch_embed(request: BatchEmbedRequest):
    """Generate embeddings for a batch of texts in one model forward pass."""
    embeddings = model.encode(request.texts, batch_size=64, show_progress_bar=False).tolist()
    return BatchEmbedResponse(embeddings=embeddings)


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model is not None}