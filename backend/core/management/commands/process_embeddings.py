import logging
import time

from django.core.management.base import BaseCommand

from core.services.batch_embedding_service import BatchEmbeddingService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process pending profile embedding queue using the ML batch endpoint"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size", type=int, default=32,
            help="Number of profiles to embed per batch (default: 32)",
        )
        parser.add_argument(
            "--loop", action="store_true",
            help="Keep running until queue is empty, then exit",
        )
        parser.add_argument(
            "--sleep", type=float, default=5.0,
            help="Seconds to sleep between batches when --loop is set (default: 5)",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        loop = options["loop"]
        sleep_secs = options["sleep"]

        self.stdout.write(f"Starting embedding processor (batch_size={batch_size}, loop={loop})")

        total_processed = 0
        start = time.time()

        while True:
            queue_len = BatchEmbeddingService.queue_length()
            if queue_len == 0:
                if loop:
                    time.sleep(sleep_secs)
                    continue
                else:
                    break

            self.stdout.write(f"Queue: {queue_len} pending. Processing batch of {batch_size}...")
            try:
                n = BatchEmbeddingService.process_batch(batch_size)
                total_processed += n
                elapsed = time.time() - start
                throughput = total_processed / elapsed if elapsed > 0 else 0
                self.stdout.write(
                    f"  Processed {n} profiles. Total: {total_processed} "
                    f"({throughput:.1f} profiles/s)"
                )
            except Exception as e:
                self.stderr.write(f"  Batch failed: {e}")
                time.sleep(sleep_secs)

            if not loop and BatchEmbeddingService.queue_length() == 0:
                break

        elapsed = time.time() - start
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Processed {total_processed} profiles in {elapsed:.1f}s"
            )
        )
