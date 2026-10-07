# Evidence worker scheduled execution

Scope: HRMIS evidence execution only. No Redis, PostgreSQL, API, storage, mail, or unrelated cron changes. The existing background worker is retained until the replacement has passed live verification, then suspended rather than deleted.

## Exact service change

| Setting | Value |
|---|---|
| Existing worker | `srv-d9kh4efavr4c73d000c0`, `hrmis-saas-evidence-worker` |
| New service | `hrmis-saas-evidence-cron`, separate Render cron job |
| Runtime / region / plan | Python / Frankfurt / Starter (0.5 CPU, 512 MiB) |
| Repository / root | `mmwarunge-droid/hrmis-saas` / `backend` |
| Build | `pip install -r requirements.txt` |
| Start | `python signature_evidence_worker.py --once` |
| Schedule | `*/5 * * * *` (UTC) |
| Source | Worker-only release branch; exact revision recorded in execution checkpoint |
| Disk / migration / predeploy | None |

A background worker is a different Render service type; the update-service API does not expose a service-type conversion. Use a parallel cron service to preserve rollback. Do not rename/change the existing worker into a cron or apply the whole application Blueprint. `backend/render-evidence-cron.yaml` describes only the replacement. Existing shared services are references, not new infrastructure.

Copy the existing worker's effective environment securely, without printing values or rotating keys. Required groups of variables: application environment and Python version; `DATABASE_URL`; `REDIS_URL`, `RATELIMIT_STORAGE_URI` and authentication settings needed by application startup; existing `SECRET_KEY`, `JWT_SECRET_KEY`, MFA keys/pepper; frontend/CORS/account URL settings; existing mail settings; `SIGNATURE_PROVIDER`, Dropbox Sign settings; S3 evidence bucket/prefix/region/endpoint/access key/secret/SSE; retry, attempt, lease and batch configuration. Preserve current values. This deployment does not require creating or modifying an environment group. Preserve any existing group links or copy their effective values when resolving parity. Compare keys and values in memory, never log credentials.

The evidence queue and retry state remain in PostgreSQL. `--once` processes one batch of up to ten due jobs and exits; it is not a drain-until-empty command. No new migration or dependency is required. Empty batches now produce a completion log. Completed jobs retain elapsed/process-CPU timing. Unexpected failures produce a nonzero exit after remaining claimed jobs have been attempted; provider retries remain successful durable state transitions.

## Concurrency protection

Processing holds the request row lock throughout provider I/O and persistence. Other PostgreSQL claimers use `SKIP LOCKED`, including when the time lease has expired. After failure rollback, processing reacquires the lock and checks the attempt number before updating retry/failure state, preventing an old attempt from overwriting a newly claimed attempt. Duplicate completion returns the verified result without generating artifacts/events again. SIGTERM/process termination releases database locks; the committed lease remains recoverable after its timeout.

The row transaction can last as long as provider/storage I/O and can delay callbacks updating the same request. This is deliberate per-request exclusion, not a table lock. Never disable provider timeouts. Render serializes scheduled runs of one cron; application/database protection also covers the old worker or other runners during transition.

## Acceptance evidence

- Production read-only aggregate job at 2026-10-07 04:42:44 UTC: evidence backlog **0**. One historical QES request has workflow status `failed`, evidence status `not_required`, and no downloadable callback. No production HR data was changed.
- Targeted acceptance exercises one job and duplicate rerun; eleven jobs across two batches; retrieval-not-ready, no early retry, successful retry and exhaustion; fresh lease exclusion and abandoned lease recovery; concurrent runners with both fresh and expired leases.
- PostgreSQL overlap tests use a real disposable PostgreSQL 16 instance, independent sessions and a download held open while another runner claims work. The expected result is one provider download, two artifacts, one completion event and one attempt.
- Final worker suite: 14 targeted tests passed, including PostgreSQL cases and scheduler exit-code tests; an additional rollback/reclaim race test is validated separately. 28 related provider/QES/seal tests passed.
- Local measured one-job execution: 0.280 seconds; ten-job batch: 0.206 seconds. These use simulated provider responses and local artifact storage; they do not certify external provider or S3 latency.
- Three fresh `python signature_evidence_worker.py --once` processes against an empty migrated local PostgreSQL database exited 0 and logged `claimed=0`: 1.088, 1.159 and 1.227 seconds (mean 1.158 seconds). Render startup duration is measured separately.
- Ruff and diff whitespace checks pass. No browser changes are involved.

## Latency and capacity

For an immediately due job in the first batch, normal start delay is up to five minutes plus Render startup/dispatch. Completion additionally includes preceding jobs in the batch and its own provider/storage time. Ten sequential jobs per tick means a job at queue position N needs up to `ceil(N / 10)` ticks when batches finish before the next tick and no new earlier-priority work intervenes. Position 11 can wait roughly ten minutes, plus startup and processing. A five-minute schedule is appropriate for the observed empty queue; these are conditional bounds, not a hard five-minute completion SLA.

Retries retain backoff of 30, 60, 120, 240, 480, 960 and 1,800 seconds before attempts 2–8. Each retry may wait almost one extra five-minute interval after its due time. The seven backoffs total 61.5 minutes; allowing up to five minutes of tick alignment for each of eight attempts gives a conservative bound of 101.5 minutes plus execution/startup to reach the eighth attempt, assuming no backlog, missed ticks or prolonged runs. An abandoned 900-second lease can wait up to roughly 20 minutes from claim before the next eligible tick, plus dispatch delay (the stale comparison is strict). A job still holding its processing lock is not reclaimed just because its timestamp ages.

There is no finite worst-case completion time under provider outage, exhausted retries, a missed schedule, long-running jobs or unbounded backlog. Alert on failed cron execution, no successful runs for 15 minutes, terminal `failed` evidence and oldest due work exceeding ten minutes. Use `python scripts/evidence_queue_status.py` for a read-only aggregate cutover gate (exit 1 means backlog exists); it does not process or repair data.

## Cutover and rollback

1. Publish the tested worker-only revision without deploying other services. Recheck live backlog using the read-only command; investigate any nonzero result.
2. Create the separate cron with environment parity, same resources and five-minute schedule. Retain the current worker unchanged during initial verification.
3. Verify exact deployed revision, command, schedule and environment parity. At an idle boundary trigger one cron execution, verify exit 0 and job/batch logs; also observe an automatic scheduled run. Do not manually trigger an already-running cron: Render cancels its active execution.
4. Recheck backlog and absence of processing jobs. Suspend the original worker; do not delete it. Verify the cron continues to succeed after suspension and no unexpected errors/backlog appear.
5. Savings begin only once the paid always-on worker is suspended. Preserve its original branch/configuration and the tested replacement revision.

Rollback: suspend the cron at an idle boundary; if it is active, allow it to finish rather than triggering another run. Confirm no processing lock is active, then resume the retained worker. A terminated job's lease is recovered after its timeout; never clear leases manually or delete queue rows/artifacts. Verify backlog drains and inspect retries. No database downgrade or data restoration is needed. If retaining overlap protections on rollback, deploy the tested worker revision to the retained worker before resuming it; the legacy revision lacks expired-lease I/O exclusion.

Expected ongoing worker cost: about $1/month cron minimum instead of $7/month always-on, **approximately $6/month or $72/year saved**. At 8,640 ticks per 30-day month and $0.00016/minute, the $1 floor holds while mean billed runtime is below about 43.4 seconds. Active jobs can increase usage. Brief parallel verification incurs both services' charges.

Provider references: [cron behavior and billing](https://render.com/docs/cronjobs), [service update API](https://api-docs.render.com/reference/update-service), [pricing](https://render.com/pricing).

## Execution checkpoint

Pending final acceptance and replacement deployment. This document does not itself claim the original worker has been suspended or any savings realized.
