# Future Production Deployment Architecture (AWS)

> **IMPORTANT — READ BEFORE PROCEEDING**
>
> This document describes AWS services as **potential future production deployment
> options only**.  None of the AWS services listed here are implemented,
> configured, called, benchmarked, or evaluated anywhere in this codebase.
> No AWS SDK (`boto3` or equivalent) is installed.  No AWS credentials or
> resource ARNs appear in any configuration file.
>
> All experiments, metrics, and results presented in the POC reports are
> generated entirely from the **local implementation** described in
> [`architecture.md`](./architecture.md).  Any claim that an AWS service was
> tested or that its performance was measured in this POC would be false.

---

## Why document this at all?

The Review-1 report for this project references several AWS services as part of
a proposed production architecture.  This document records that mapping for
future reference so that a production deployment team has a clear starting
point — without implying those services have been built, tested, or integrated
in the POC.

---

## Local → AWS Component Mapping

The table below maps each local POC component to its potential AWS production
replacement.  The "AWS status" column applies to **this repository only**.

| Local POC component | AWS production option | AWS status in this repo |
|---|---|---|
| Supervisor's intent classification step (LangGraph) | **AWS Lex V2** (managed NLU / intent recognition) | ❌ Future option — not implemented |
| Local Python email-parsing function | **AWS Lambda** (serverless function execution) | ❌ Future option — not implemented |
| Local disk (`data/raw_docs/`) + PostgreSQL | **Amazon S3** (object storage for structured JSON and raw documents) | ❌ Future option — not implemented |
| APScheduler (in-process reminders) | **Amazon EventBridge** (scheduled events) + **Amazon SNS** (notification delivery) | ❌ Future option — not implemented |
| Process-level auth (none needed locally) | **AWS IAM** (identity & access management, cross-service roles) | ❌ Future option — not implemented |
| Local structured logging (stdout + rotating file) | **Amazon CloudWatch Logs** (centralised log aggregation & alerting) | ❌ Future option — not implemented |
| Docker Compose (local orchestration) | **Amazon ECS / EKS** (container orchestration) | ❌ Future option — not implemented |
| Local ChromaDB directory | **Amazon OpenSearch Service** or a hosted vector DB | ❌ Future option — not implemented |

---

## What a production migration would involve

This section is informational only — it describes work that would need to be
done **after** the POC is complete and validated.

### 1. AWS Lex V2 — NLU / intent recognition

The local POC uses the LangGraph Supervisor agent to classify user intent
(company research, planning, progress check, notification).  In production,
AWS Lex V2 could handle initial intent capture and slot filling before routing
to the appropriate agent.

**Migration considerations:**
- Lex V2 intents would need to be defined to match the four agent categories.
- The Supervisor's prompt-based classification could be retained as a fallback
  or replaced by Lex entirely.
- IAM roles would be required to allow the FastAPI service to call the Lex
  runtime API.

### 2. AWS Lambda — background processing

The local scheduler (`app/scheduler/notifier.py`, backed by APScheduler)
triggers reminders and background tasks in-process.  In production, these
could be implemented as Lambda functions invoked by EventBridge schedules.

**Migration considerations:**
- Each scheduled task (e.g., deadline reminder, progress nudge) becomes a
  separate Lambda function or a single Lambda with a dispatch table.
- Lambda deployment packages would need to include the relevant agent and DB
  logic, or the Lambda could call the FastAPI service via an internal API.

### 3. Amazon S3 — document and artefact storage

Raw documents currently live in `data/raw_docs/` on local disk.  PostgreSQL
stores chunk metadata.  In production, S3 could serve as the primary
document store, with pre-signed URLs for secure access.

**Migration considerations:**
- Ingestion pipeline (`app/rag/ingest.py`) would read from S3 instead of the
  local filesystem; the abstraction in that module is designed to accommodate
  this swap.
- Versioning and immutability requirements for evaluation datasets (master plan
  Section 10) map naturally to S3 versioning + Object Lock.

### 4. EventBridge + SNS — scheduling and notifications

APScheduler runs in-process and is suitable for a single-instance POC.  For
production HA deployments, EventBridge cron rules trigger Lambda functions, and
SNS delivers notifications to email / SMS / SQS targets.

### 5. IAM — cross-service authentication

No cross-service authentication is needed in the local POC (everything runs in
the same process or Docker network).  In production, every service-to-service
call (FastAPI → Lex, Lambda → S3, Lambda → RDS, etc.) would require IAM roles
and policies following the principle of least privilege.

### 6. CloudWatch — logging and monitoring

The local POC emits structured logs to stdout and a rotating file.  In
production, the application container would ship logs to CloudWatch Logs via
the CloudWatch agent or the `awslogs` Docker logging driver.  CloudWatch
Metrics and Alarms would replace the manual log inspection used during the POC.

---

## Checklist before starting a production migration

- [ ] POC experiments completed and findings documented in `docs/research_summary.md`
- [ ] AWS account and billing budget established
- [ ] IAM role structure designed (least privilege)
- [ ] Network architecture decided (VPC, subnets, security groups)
- [ ] Data residency and compliance requirements reviewed
- [ ] CI/CD pipeline designed for container + Lambda deployments
- [ ] Monitoring and alerting plan (CloudWatch dashboards, alarms, runbooks)
- [ ] Cost estimate for production traffic volume

---

*Last updated: Phase 0 scaffold — no AWS components implemented.*
