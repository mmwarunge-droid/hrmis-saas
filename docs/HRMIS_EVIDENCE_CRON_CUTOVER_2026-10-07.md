# HRMIS evidence cron production cutover — 7 October 2026

Scope is HRMIS evidence execution only. The user explicitly authorized a paid cron replacement, copying only its required environment, verification and suspension (not deletion) of the old worker. No Dundaa resources are included.

## Release and configuration

- New cron: `crn-db2tc1p42hec73fre5fg`, `hrmis-saas-evidence-cron`.
- Frankfurt, Starter, Python; root `backend`; build `pip install -r requirements.txt`.
- Command: `python signature_evidence_worker.py --once`.
- Schedule: `*/5 * * * *`, UTC.
- Deployed commit: `41767596bd90ea828de33abc6af1b335bf18663f`, including worker implementation `022c6ed`.
- Deployment: `dep-db2tc2942hec73fre6s0`, live at 05:18:39 UTC.
- Source branch: `ops/evidence-worker-cron`, auto-deploy off. Future code releases must deliberately deploy this service; later documentation commits do not replace the verified artifact.
- 41 required environment variables copied from the original worker and compared for exact equality in memory. The unused continuous-poll interval was excluded. Required application validation includes existing SMTP and authentication configuration. Secret values were not printed, logged, committed or written to audit files. No credentials were rotated and no new environment group was created.
- Original worker: `srv-d9kh4efavr4c73d000c0`, retained with its original configuration; suspension acknowledged at **05:28:11 UTC**, after manual and two automatic runs passed.

No Redis, database plan/storage/schema, API server, unrelated cron, provider credential or queue-record mutation was performed. The only platform mutations were creating/configuring the new cron, triggering its manual verification run, creating temporary diagnostic jobs and suspending the old worker. Temporary read-only diagnostic jobs performed aggregate SELECTs with database-enforced read-only transactions.

## Validation boundaries

Previously completed acceptance: **43 targeted/relevant backend tests passed**, including real PostgreSQL overlap, expired-lease exclusion, retry and rollback/reclaim tests. Full backend Ruff and whitespace checks passed. No application code changed during production cutover.

All observed production batches claimed zero jobs. Successful claims establish PostgreSQL connectivity and queue access, but do not demonstrate an actual live provider download or retry. Positive job processing, duplicates, lease expiry and retrieval failures are covered by the isolated acceptance suite; no production queue record or customer workflow was fabricated for testing.

The read-only baseline at 05:17:40 UTC found zero backlog. A second gate at 05:27:40 UTC found zero backlog, zero evidence attempts, zero locked timestamps, zero next-attempt timestamps and zero completed-evidence timestamps. The single historical QES record remains workflow `failed`, evidence `not_required`, without downloadable evidence. This is not an actionable evidence job. The same aggregate state was observed at 05:32:21 UTC after suspension.

## Live execution results

Durations are Render start-to-end event intervals, including provisioning/teardown; they are not provider processing durations or invoice measurements.

| Run | UTC start | UTC end | Seconds | Result |
|---|---|---|---:|---|
| Manual | 05:19:04 | 05:19:31 | 27.071 | successful; claimed=0 |
| Automatic, worker retained/running | 05:20:02 | 05:20:36 | 34.829 | successful; claimed=0 |
| Automatic, worker retained/running | 05:25:20 | 05:25:56 | 36.973 | successful; claimed=0 |
| Automatic, worker suspended | 05:30:19 | 05:31:17 | 58.873 | successful; claimed=0 |
| Automatic, worker suspended | 05:35:01 | 05:35:39 | 38.915 | successful; claimed=0 |

## Latency, cost and monitoring

Every observed scheduled tick launched automatically; record dispatch and runtime separately from queue processing. A job becoming due just after a tick normally waits almost five minutes plus startup and preceding jobs in its ten-job batch. Larger queues, retries and provider failures add delay; no finite completion guarantee applies during an outage. No actual job latency could be measured with the empty production queue.

Projected saving remains **approximately $6/month or $72/year**: $7 always-on worker replaced by roughly $1 scheduled execution. Cron runtime is usage-billed with a monthly minimum; variable startup and active jobs can increase cost. This is a projection, not a settled invoice, and brief parallel validation adds transient cost.

Monitor failed/missing runs, terminal evidence failures, oldest due work and batch saturation. Investigate no successful run for 15 minutes or oldest due work over ten minutes. These are operational thresholds, not a newly installed alerting integration. Preserve the database-backed retry/lease state; never clear it to hide a failure.

## Rollback

1. Suspend the new cron at an idle boundary; verify no run is active. Do not manually trigger while another run is active, because Render cancels the active run.
2. Resume `srv-d9kh4efavr4c73d000c0`; its original command, branch and configuration are retained. Verify successful startup, queue connectivity and backlog state.
3. If a job was interrupted, allow the durable lease timeout/retry path to recover it. Do not delete or edit queue rows, reset attempts, remove evidence or change provider credentials.
4. Avoid overlapping the legacy worker with an active cron download on rollback: the old artifact lacks the improved long-download row locking. If rollback must retain that improvement, explicitly deploy `4176759` to the retained worker before use.

No database restore, schema change or Redis change is needed. The old worker is retained, not deleted.

## Final verification

Final read-only snapshot at **05:36:28 UTC** (`job-db2tkiqjnfac7380a6l0`): backlog **0**; QES row count 1, total evidence attempts 0, locked timestamps 0, next-attempt timestamps 0, completed-evidence timestamps 0. These aggregates match the pre-suspension gate. Final service reread confirms the cron active and the old worker suspended.

Five runs succeeded: one manual plus four automatic, including two automatic cycles after old-worker suspension. All five logged `claimed=0`. Twenty runtime log records were scanned with zero warning/error/exception/traceback/failure markers. Render reported all runs successful; no crash or retry loop remained active. Command-start to empty-batch completion was approximately 5.0–6.4 seconds; total platform run time was 27.1–58.9 seconds. Scheduled starts were 1–20 seconds after their nominal ticks in this observation window.

The four automatic start-to-end intervals averaged 42.4 seconds. Applying the published per-minute rate to that small sample remains approximately the $1/month cron floor; startup variability or actual jobs may raise usage. Retain the approximately $6/month, $72/year savings projection with that limitation.

Production duplicate/lease conclusion: no claims or attempts occurred and the aggregate lease state remained unchanged. Positive duplicate/expired-lease behavior was validated in isolated PostgreSQL tests, not by manufacturing live jobs. Queue access and scheduling are verified live; real provider/S3 processing latency remains unmeasured in this empty-queue rollout.

Final recommendation: **GO — retain the verified five-minute cron and keep the old worker suspended as the rollback path.** Future monitoring must cover failed/missing runs and oldest due work. Do not delete the rollback worker in this task.
