import logging
import requests

logger = logging.getLogger(__name__)

ML_SERVICE_URL = "http://ml-service:8001"


class MLService:
    @staticmethod
    def get_embedding(text):
        try:
            response = requests.post(
                f"{ML_SERVICE_URL}/embed",
                json={"text": text},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            logger.error(f"ML service error: {e}")
            raise Exception(f"Failed to generate embedding: {str(e)}")

    @staticmethod
    def compute_similarity(embedding_a, embedding_b):
        try:
            response = requests.post(
                f"{ML_SERVICE_URL}/similarity",
                json={
                    "embedding_a": embedding_a,
                    "embedding_b": embedding_b,
                },
                timeout=10,
            )
            response.raise_for_status()
            return response.json()["score"]
        except Exception as e:
            logger.error(f"ML similarity error: {e}")
            return 0.0