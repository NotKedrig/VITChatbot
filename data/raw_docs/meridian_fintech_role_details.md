# Meridian FinTech — Role Deep Dives and Engineering Culture

## Engineering at Meridian

Meridian's engineering organisation is structured around two product verticals — Lending
and Payments — and one shared-platform guild. Teams are small (5–8 engineers) and
operate with high autonomy. Engineers at MFT are expected to own their features end to
end: from database schema design through API implementation, frontend integration (for
full-stack tasks), deployment, and post-launch monitoring.

The technology stack is intentionally constrained to reduce cognitive overhead:

| Layer | Technology |
|---|---|
| Backend services | Java 21 (Spring Boot 3), Kotlin |
| Mobile | React Native |
| Data stores | PostgreSQL, Redis, Apache Kafka |
| Infrastructure | AWS EKS (Kubernetes), Terraform |
| Observability | Datadog, PagerDuty |
| CI/CD | GitHub Actions, ArgoCD |

Candidates who have used any subset of this stack are preferred, but MFT does not expect
freshers to know all of it — demonstrated ability to learn quickly matters more.

## Software Development Engineer (SDE-1) — Deep Dive

SDE-1s at Meridian join one of the four product squads based on their interests and
the team's headcount needs:

- **Lending Core**: loan origination APIs, credit-bureau integrations, EMI scheduling.
- **Payments Gateway**: UPI and card payment processing, reconciliation, chargebacks.
- **Risk & Fraud**: real-time transaction scoring, rule engines, alert management.
- **Platform**: shared libraries, API gateway, developer experience tooling.

**First 90 days**: New SDE-1s complete MFT's onboarding programme, which includes
three weeks of structured learning (codebase walkthroughs, architecture deep dives, and
a mini project), followed by assignment to a squad with a dedicated buddy (a senior SDE).
First production code is expected within 30 days.

**Promotion timeline**: SDE-1 to SDE-2 typically takes 18–24 months, contingent on
performance ratings and scope of impact.

## Associate Data Scientist — Deep Dive

The Data Science team at Meridian focuses exclusively on applied ML — there is no pure
research function. The team's primary outputs are:

- **Credit-scoring models**: gradient-boosted trees (XGBoost, LightGBM) trained on
  bureau data, bank statement analysis, and behavioural features from the MFT app.
- **Fraud detection**: real-time ML models served via a feature store (Redis-backed),
  plus rule-based systems for known fraud patterns.
- **Churn prediction**: logistic regression and survival analysis models driving retention
  campaigns.

Associates work in Python (scikit-learn, XGBoost, pandas) and are expected to be
comfortable with SQL for feature extraction. Models are deployed via a Kubernetes-based
serving infrastructure; Associates learn deployment practices on the job.

**Hiring note for this role**: The coding assessment is the same as for SDE-1, but
the technical phone screen (Round 2) replaces one algorithm problem with a statistics
problem (e.g., explain the bias-variance tradeoff, describe how you would validate a
classification model, or interpret a given ROC curve).

## Quality Assurance Engineer (QAE) — Deep Dive

QAEs at MFT own test automation for their assigned squad. The role is closer to
software engineering than traditional QA — QAEs write production-quality automation
code, review developer pull requests for testability, and contribute to the CI/CD
pipeline configuration.

Primary responsibilities:
- Build and maintain API test suites using RestAssured (Java) or pytest (Python).
- Write Selenium WebDriver or Appium scripts for web and mobile UI regression.
- Define and implement performance test scenarios using k6 or Gatling.
- Work with the squad's SDE to set up contract tests (Pact) for microservices
  integrations.

**Interview note**: QAE candidates are asked a coding problem in Round 2 (same
platform as the main assessment), plus questions on test strategy, how to prioritise
test coverage, and how to handle flaky tests.

## Engineering Culture and Values

MFT uses three internal values to guide hiring, performance reviews, and promotion
decisions:

1. **Customer obsession**: Engineering decisions are evaluated by their impact on end
   users (borrowers or merchants). Engineers are expected to understand the product,
   not just the technical spec.

2. **Speed of execution**: MFT ships to production multiple times daily. Engineers are
   expected to break work into small, independently deployable units and avoid
   big-bang releases.

3. **Frugal innovation**: The company runs lean. Engineers are expected to choose
   simple solutions over elaborate ones and to question whether a new third-party
   dependency is necessary before adding it.

## Compensation Details

All offers include:
- Fixed pay (monthly salary × 12).
- Variable pay (paid quarterly based on individual and company performance; target
  percentages given in the roles section).
- Provident Fund contribution (employer's share: 12 % of basic salary).
- Group health insurance: ₹5 lakh coverage per year, covering self, spouse, and
  two dependants.
- ESOPs: Not offered at SDE-1 or QAE level for campus hires (eligible after
  promotion to SDE-2 or equivalent).
