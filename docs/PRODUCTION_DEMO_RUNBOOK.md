# Kinetic production demo runbook

This runbook is for a deliberately isolated demonstration deployment. It is not authorization to seed or reset a customer database.

## Environment boundary

Use a dedicated frontend hostname, API service, PostgreSQL database, Redis instance, object-storage namespace and secrets set. The demo environment must not share persistence with production customer workloads. `demo-reset` remains disabled when `APP_ENV=production`; prepare the dataset before promoting a snapshot, or operate a separately classified non-production demo service.

## Required release gates

1. Merge only a clean commit that passed `scripts/verify_release.sh`.
2. Apply all migrations through revision `019_goals_kpi_mvp`.
3. Confirm `/health` returns the intended release SHA and `/ready` reports both database and Redis as ready.
4. Configure exact HTTPS values for `FRONTEND_URL` and `CORS_ORIGINS`.
5. Generate independent `SECRET_KEY`, `JWT_SECRET_KEY`, MFA encryption keys and recovery-code pepper in a secret manager.
6. Use SMTP with TLS, private upload storage, encrypted database connections and automated backups.
7. Set `JSON_LOGS=true` and route logs to a retained, access-controlled collector.
8. Run `scripts/smoke_demo.sh` with a disposable employee account.
9. Complete the role matrix and mobile/desktop browser walkthrough.

## Deployment sequence

```bash
flask --app run.py db upgrade
flask --app run.py db current
curl --fail https://api-demo.example.com/health
curl --fail https://api-demo.example.com/ready
```

Deploy the API before the SPA when a migration is backward compatible. For a breaking change, use an expand-migrate-contract sequence instead of replacing database columns in one release.

## Backup and restore evidence

Before release, capture a database snapshot and record its identifier. Quarterly, restore the latest snapshot into an isolated verification database and run the backend suite plus a demo smoke test. A backup that has not been restored is not considered verified.

## Rollback

1. Stop new deployment traffic or restore the prior application revision.
2. Do not downgrade the database automatically unless the migration has been explicitly tested as reversible.
3. Validate `/ready`, login, goals, people, files, leave and attendance.
4. Record the release SHA, request IDs, timestamps and affected workflows.
5. Preserve logs and database evidence for incident review.

## Acceptance matrix

- Platform admin: MFA, organizations, active/suspended/archived lifecycle.
- Owner and consultant: dashboard, people, goals, documents, leave, onboarding and notifications.
- Manager: direct-report leave, goals and onboarding scope.
- Employee: profile, time off, attendance, files, goals and signature tasks.
- New hire: employee home and onboarding.
- Inactive user and suspended-workspace administrator: authentication rejected.

## Monitoring and incident triggers

Alert on sustained 5xx responses, readiness failures, database saturation, Redis errors, authentication lockout spikes, failed background evidence processing and upload-storage errors. Use `X-Request-ID` to correlate browser reports with API logs. Never include passwords, JWTs, MFA secrets, document contents or recovery codes in logs or tickets.
