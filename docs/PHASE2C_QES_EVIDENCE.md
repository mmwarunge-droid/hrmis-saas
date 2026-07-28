# Phase 2C — QES evidence ingestion

This phase completes the operational evidence lifecycle for Dropbox Sign
eID-backed requests.

## Completion boundary

A provider callback that says a request is downloadable does **not**
complete the ACE workflow. It queues an evidence job. The request becomes
`completed` only after ACE has:

1. retrieved the final signed PDF and provider audit trail;
2. matched the provider request and signer to the ACE request;
3. checked that both artifacts are PDFs;
4. calculated and persisted SHA-256 hashes;
5. stored the artifacts in tenant-scoped private storage; and
6. persisted an evidence verification record.

`assurance_confirmed` deliberately remains `false`. The verification is an
operational provider-package integrity and mapping check. It is not an
independent legal opinion or certificate-chain validation.

## Evidence lifecycle

- `awaiting_provider`
- `pending`
- `processing`
- `retry_scheduled`
- `verified`
- `failed`

Dropbox Sign `409`, rate-limit, timeout, and server failures are retried
with bounded exponential backoff. Invalid archives, mismatched request IDs,
mismatched signers, and conflicting stored hashes fail closed.

## Worker

Run one batch locally:

```bash
cd backend
source .venv/bin/activate
python signature_evidence_worker.py --once
```

Run continuously:

```bash
python signature_evidence_worker.py
```

Only one worker service is required initially. Database row locking with
`SKIP LOCKED` allows safe horizontal scaling later.

## Storage

Development and isolated tests may use:

```text
SIGNATURE_EVIDENCE_STORAGE=local
SIGNATURE_EVIDENCE_FOLDER=/absolute/private/path
```

Production Dropbox Sign activation requires S3-compatible private object
storage because the Render web service and a background worker do not share
a local persistent disk:

```text
SIGNATURE_EVIDENCE_STORAGE=s3
SIGNATURE_EVIDENCE_S3_BUCKET=...
SIGNATURE_EVIDENCE_S3_PREFIX=signature-evidence
SIGNATURE_EVIDENCE_S3_REGION=...
SIGNATURE_EVIDENCE_S3_ENDPOINT_URL=...
SIGNATURE_EVIDENCE_S3_ACCESS_KEY_ID=...
SIGNATURE_EVIDENCE_S3_SECRET_ACCESS_KEY=...
SIGNATURE_EVIDENCE_S3_SSE=AES256
```

Use a private bucket, block public access, enable versioning, configure
retention according to policy, and restrict both the web and worker
credentials to the evidence prefix.

## Render deployment

Do not activate Dropbox Sign yet. After validation:

1. configure the S3 variables on the web service;
2. create a Render background worker using the same repository and
   production environment variables;
3. use `python signature_evidence_worker.py` as its start command;
4. set the same database, Redis, Dropbox Sign, mail, MFA, and evidence
   storage variables on both services;
5. run migration `013_qes_evidence_ingestion`;
6. execute a provider sandbox/UAT evidence cycle;
7. only then change `SIGNATURE_PROVIDER` from `internal` to
   `dropbox_sign`.

## Administrative endpoints

- `GET /api/signature-requests/<id>/evidence`
- `POST /api/signature-requests/<id>/evidence/retry`
- `GET /api/signature-requests/<id>/artifacts/<artifact-id>/download`

All routes require document approval permission and tenant-scoped request
access.
