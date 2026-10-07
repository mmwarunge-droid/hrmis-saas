"""Poll provider evidence jobs whose leases are committed before external I/O.
SIGTERM/SIGINT stop future loop iterations; service retry state survives restart."""

import argparse
import signal
import time

from app import create_app
from app.services.signature_evidence_service import (
    claim_signature_evidence_jobs,
    process_signature_evidence,
)


stopping = False


def _stop(_signum, _frame):
    global stopping
    stopping = True


def run(*, once=False):
    app = create_app()
    # The factory configures this logger, not the script's __main__ logger.
    # Emit timings only for actual jobs so idle polling does not create log spend.
    logger = app.logger

    with app.app_context():
        poll_seconds = int(app.config.get(
            'SIGNATURE_EVIDENCE_WORKER_POLL_SECONDS',
            5,
        ))

        while not stopping:
            try:
                request_ids = claim_signature_evidence_jobs()
                crashed = False

                for request_id in request_ids:
                    started = time.perf_counter()
                    cpu_started = time.process_time()
                    try:
                        result = process_signature_evidence(
                            request_id,
                        )
                        logger.info(
                            'Evidence job %s finished with status %s '
                            'duration_seconds=%.3f cpu_seconds=%.3f',
                            request_id,
                            result.evidence_status,
                            time.perf_counter() - started,
                            time.process_time() - cpu_started,
                        )
                    except Exception:
                        crashed = True
                        logger.exception(
                            'Evidence job %s crashed outside the '
                            'service retry boundary '
                            'duration_seconds=%.3f cpu_seconds=%.3f',
                            request_id,
                            time.perf_counter() - started,
                            time.process_time() - cpu_started,
                        )
            except Exception:
                logger.exception(
                    'Evidence worker iteration failed; retrying',
                )

                if once:
                    raise

                time.sleep(poll_seconds)
                continue

            if once:
                if crashed:
                    raise RuntimeError('Evidence batch contains unhandled job failures')
                logger.info('Evidence batch finished claimed=%d', len(request_ids))
                return

            if not request_ids:
                time.sleep(poll_seconds)


def main():
    parser = argparse.ArgumentParser(
        description='Process queued QES evidence packages.',
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Process one available batch and exit.',
    )
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    run(once=args.once)


if __name__ == '__main__':
    main()
