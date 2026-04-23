import logging
import requests
import redis

logger = logging.getLogger(__name__)

ML_SERVICE_URL = "http://ml-service:8001"
QUEUE_KEY = "embedding_queue"

redis_client = redis.Redis(host="redis", port=6379, db=0)


class BatchEmbeddingService:
    @staticmethod
    def enqueue(profile_id: str):
        """Add a profile ID to the pending embedding queue."""
        redis_client.rpush(QUEUE_KEY, str(profile_id))

    @staticmethod
    def queue_length() -> int:
        return redis_client.llen(QUEUE_KEY)

    @staticmethod
    def dequeue_batch(batch_size: int) -> list[str]:
        """Pull up to batch_size profile IDs from the queue."""
        pipe = redis_client.pipeline()
        for _ in range(batch_size):
            pipe.lpop(QUEUE_KEY)
        results = pipe.execute()
        return [r.decode() for r in results if r is not None]

    @staticmethod
    def get_embeddings(texts: list[str]) -> list[list[float]]:
        resp = requests.post(
            f"{ML_SERVICE_URL}/batch_embed",
            json={"texts": texts},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]

    @staticmethod
    def process_batch(batch_size: int = 32) -> int:
        """
        Pull one batch from the queue, generate embeddings, write back to DB.
        Returns the number of profiles processed.
        """
        from core.models import Profile

        profile_ids = BatchEmbeddingService.dequeue_batch(batch_size)
        if not profile_ids:
            return 0

        profiles = list(Profile.objects.filter(id__in=profile_ids).select_related("user"))
        if not profiles:
            return 0

        skills = [p.skills_text for p in profiles]
        intents = [p.intent_text for p in profiles]

        try:
            skill_embeddings = BatchEmbeddingService.get_embeddings(skills)
            intent_embeddings = BatchEmbeddingService.get_embeddings(intents)
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            # Re-enqueue failed IDs for retry
            for pid in profile_ids:
                BatchEmbeddingService.enqueue(pid)
            raise

        for profile, skill_emb, intent_emb in zip(profiles, skill_embeddings, intent_embeddings):
            profile.skill_embedding = skill_emb
            profile.intent_embedding = intent_emb

        Profile.objects.bulk_update(profiles, ["skill_embedding", "intent_embedding"])
        logger.info(f"Processed {len(profiles)} embeddings from queue")
        return len(profiles)
