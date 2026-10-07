"""Read-only aggregate cutover gate; never print request data or connection URLs."""
import json
import os

import psycopg2


def main():
    url = os.environ['DATABASE_URL'].replace(
        'postgresql+psycopg2://', 'postgresql://', 1,
    )
    with psycopg2.connect(
        url,
        connect_timeout=10,
        options='-c default_transaction_read_only=on -c statement_timeout=10000',
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT evidence_status, status,
                       (provider_downloadable_at IS NOT NULL), count(*)
                FROM signature_requests
                WHERE provider = 'dropbox_sign' AND assurance_level = 'qes'
                GROUP BY evidence_status, status,
                         (provider_downloadable_at IS NOT NULL)
                ORDER BY evidence_status, status
            """)
            print(json.dumps({'evidence_counts': cursor.fetchall()}))
            cursor.execute("""
                SELECT count(*) FROM signature_requests
                WHERE provider = 'dropbox_sign' AND assurance_level = 'qes'
                AND (
                    evidence_status IN ('pending', 'retry_scheduled', 'processing', 'failed')
                    OR (provider_downloadable_at IS NOT NULL
                        AND evidence_status IS DISTINCT FROM 'verified')
                )
            """)
            backlog = cursor.fetchone()[0]
            print(json.dumps({'evidence_backlog': backlog}))
    return 1 if backlog else 0


if __name__ == '__main__':
    raise SystemExit(main())
