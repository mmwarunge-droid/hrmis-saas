import argparse
import logging
import signal
import time

from app import create_app
from app.services.signature_evidence_service import (
    claim_signature_evidence_jobs,
    process_signature_evidence,
)


logger = logging.getLogger(__name__)
stopping = False


def _stop(_signum, _frame):
    global stopping
    stopping = True


def run(*, once=False):
    app = create_app()

    with app.app_context():
        poll_seconds = int(app.config.get(
            'SIGNATURE_EVIDENCE_WORKER_POLL_SECONDS',
            5,
        ))

        while not stopping:
            request_ids = claim_signature_evidence_jobs()

            for request_id in request_ids:
                result = process_signature_evidence(request_id)
                logger.info(
                    'Evidence job %s finished with status %s',
                    request_id,
                    result.evidence_status,
                )

            if once:
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
