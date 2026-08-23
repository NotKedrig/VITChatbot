# Future AWS Production Architecture

**DISCLAIMER: The architecture described below outlines a FUTURE production deployment state. None of the AWS services mentioned (ECS, RDS, EventBridge, SNS, OpenSearch) are implemented, benchmarked, or evaluated in the current Proof of Concept.** 

The current application functions entirely via a Local POC (FastAPI + SQLite + ChromaDB + APScheduler).

---

## Target State Architecture

When scaling from the local POC to a production environment on AWS, the architecture will migrate to distributed, managed cloud services to ensure high availability, scalability, and robust state management.

### 1. Compute & Orchestration (AWS ECS / Fargate)
- The FastAPI backend and LangGraph multi-agent workflow will be containerized and deployed on **Amazon Elastic Container Service (ECS)** using **AWS Fargate** for serverless compute.
- Multi-turn conversational memory (currently `MemorySaver`) will migrate to a robust distributed key-value store (e.g., Redis on Amazon ElastiCache) to persist thread states safely across multiple ECS tasks.

### 2. Persistence & Database (AWS RDS)
- The local SQLite file will be replaced by **Amazon Relational Database Service (RDS)** running PostgreSQL.
- `StudentProfile`, `PerformanceLog`, `PlanRevisionLog`, and `Notification` schemas will migrate seamlessly via SQLAlchemy connection strings.

### 3. Vector Knowledge Base (Amazon OpenSearch)
- The local ChromaDB instance will be replaced by **Amazon OpenSearch Service** with vector engine capabilities.
- This provides scalable similarity search and distributed RAG inference for the Company Research Agent.

### 4. Notifications & Scheduling (AWS EventBridge + SNS)
- The local `APScheduler` background thread will be entirely replaced.
- The **Notification Agent** will dispatch scheduling payloads to **Amazon EventBridge**.
- When a reminder is due, EventBridge will trigger an **Amazon SNS (Simple Notification Service)** topic to dispatch emails, SMS, or mobile push notifications directly to students.

### 5. Deployment Pipeline (AWS CDK)
- Infrastructure will be provisioned as Code using the **AWS Cloud Development Kit (CDK)** to ensure reproducible deployments across staging and production environments.
