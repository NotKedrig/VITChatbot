# Meridian FinTech — System Design Interview Guide for SDE-1 Candidates

## Why System Design at Fresher Level?

Meridian's engineering culture expects every engineer, including new graduates, to
understand how their code fits into a larger system. System design questions at the
SDE-1 level are scoped to service-level design — you will not be asked to design a
global-scale distributed database — but you are expected to reason about data flow,
API boundaries, and persistence choices.

The system design session is Session B of Round 3 (45 minutes). Candidates are
given a whiteboard or a shared digital canvas (draw.io or Miro). Talking through
your design in real time is expected; silence is penalised.

## Framework for System Design Answers

Use this four-step framework:

### Step 1: Requirements Clarification (5 minutes)

Ask questions to scope the problem:
- **Functional requirements**: What are the primary use cases? What can users do with
  the system?
- **Non-functional requirements**: How many users? What is the expected request rate?
  What are the latency and availability SLAs?
- **Out of scope**: Explicitly state what you are not designing (e.g., "I'll assume
  authentication is handled by an external identity provider").

At Meridian, interviewers use the problem statement as a starting point, not a complete
spec. Candidates who ask no clarifying questions are scored lower.

### Step 2: High-Level Architecture (10 minutes)

Draw the main components:
- Client (mobile app, web browser, or third-party service).
- API Gateway / Load Balancer.
- Backend services (monolith or microservices, depending on the problem).
- Data stores (relational DB, cache, message queue).
- External integrations (e.g., bank networks, SMS gateway).

Describe the primary data flow for the most important use case first.

### Step 3: Detailed Design (20 minutes)

Pick the two or three most interesting components and go deep:

**Database schema**:
- Identify the key entities and their relationships.
- Choose primary keys and common query patterns to inform index choices.
- Discuss normalisation vs. denormalisation trade-offs.

**API design**:
- Describe the primary REST endpoints (method, path, request body, response shape).
- Address idempotency for write operations (critical for payment systems).

**Critical algorithms or data structures**:
- If the problem involves rate limiting, describe the algorithm (token bucket or sliding
  window log) and where state is stored.
- If the problem involves search, discuss whether a database full-text index or a
  dedicated search service is appropriate.

### Step 4: Trade-offs and Scaling Discussion (10 minutes)

- **Bottlenecks**: where will the system break under load? (Usually the database.)
- **Caching strategy**: what can be cached, for how long, and where (in-process vs.
  Redis)?
- **Message queue**: where does decoupling via Kafka or RabbitMQ help?
- **Alternatives considered**: name one alternative design choice you rejected and
  explain why.

## Common Fresher Mistakes in System Design

1. **Jumping to implementation detail too early**: draw the high-level picture first;
   never start with schema design without agreeing on the overall architecture.

2. **Ignoring failure modes**: Meridian is a fintech; reliability and data integrity are
   non-negotiable. Mention at least one failure scenario (e.g., payment gateway timeout)
   and how your design handles it (idempotency key, retry with exponential backoff).

3. **Single-point-of-failure designs**: always mention a primary/replica setup for the
   main database and a load balancer in front of application servers — even if you don't
   detail the HA mechanism.

4. **Not discussing consistency vs. availability trade-offs**: for payment systems,
   strong consistency is usually required. State this explicitly and explain why
   eventual consistency would be dangerous for money movement.

## Common Problems at Meridian System Design Interviews

### Payment Processing System (Simplified)
**Scope**: design the backend for a UPI payment from a sender to a receiver, including
initiating the payment, validating balances, and recording the transaction.

Key design points expected:
- Idempotency: a payment initiated twice (network retry) must not debit the sender twice.
- Double-entry bookkeeping: debit sender's ledger, credit receiver's ledger atomically.
- State machine for payment status: INITIATED → PENDING → COMPLETED or FAILED.
- Notification on completion (deferred to a background worker via Kafka to avoid
  slowing the payment critical path).

### Notification Delivery Service
**Scope**: design a service that sends transactional notifications (SMS, email, push)
to Meridian's customers triggered by payment events.

Key design points expected:
- Fan-out from a single event to multiple channels.
- At-least-once delivery guarantee with deduplication.
- Priority queue: high-priority notifications (payment failure) vs. low-priority
  (marketing).
- Retry policy with exponential backoff and dead-letter queue for failed deliveries.

### Rate Limiter for the MFT Public API
**Scope**: design a rate limiter that enforces per-merchant API limits to protect the
payment gateway from abusive clients.

Key design points expected:
- Algorithm choice: token bucket (allows short bursts) vs. sliding window log (precise
  but memory-intensive) vs. sliding window counter (approximate but efficient).
- Distributed rate limiting: Redis as the shared counter store to handle multiple
  instances of the API gateway.
- Response when limit is exceeded: HTTP 429 with `Retry-After` header.
