# VITian Chatbot — Local POC Master Plan (V3)

Single source of truth. Supersedes all prior plan versions. Research-first: get valid statistical findings for the five experiments, then build the complete local application from the exact evaluated components.

---

## 1. Project Objective

Build and evaluate VITian Chatbot — a multi-agent, retrieval-grounded conversational assistant for academic, placement, and career guidance — as a **fully local proof-of-concept**. The POC must produce defensible statistical evidence for five architectural claims made in the Review-1 report, then assemble a demonstrable local application built from those same evaluated components.

Two ordered goals:
1. **Research validity** — real, non-fabricated statistical findings for Experiments 1–5.
2. **Working application** — a locally runnable chatbot using the exact agents/RAG/planner code that was evaluated, not a separate simplified demo.

---

## 2. Research Questions / Hypotheses

| # | Question | Hypothesis (stated up front, not a result) |
|---|---|---|
| 1 | Does retrieval grounding reduce hallucination and improve factual accuracy vs. an ungrounded LLM? | RAG-grounded answers will show higher factual accuracy and citation precision, lower hallucination rate, than vanilla LLM answers to the same questions. |
| 2 | Does an LLM Supervisor route more accurately than a rule-based/keyword router? | The Supervisor will achieve higher overall routing accuracy at some added latency cost. |
| 3 | Does multi-agent decomposition outperform a single well-engineered monolithic prompt? | The multi-agent system will show higher task completion and plan quality, at higher latency/token cost — a trade-off, not an unconditional win. |
| 4 | Does semantic chunking retrieve more relevant passages than fixed-size chunking? | Semantic chunking will show higher Precision@5, Recall@5, MRR, nDCG@10. |
| 5 | Does adaptive (closed-loop) planning outperform a static plan for the same simulated student? | Adaptive replanning will improve weak-topic mastery and time-to-competency relative to a static plan, holding the student's underlying simulated ability fixed. |

All five are treated as falsifiable hypotheses. A null or mixed result is an acceptable, reportable outcome.

---

## 3. Local Architecture

```
                 ┌─────────────────────┐
                 │  React + Vite UI     │   (Phase 9)
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │      FastAPI         │
                 └──────────┬──────────┘
                            │
                            ▼
                 ┌─────────────────────┐
                 │ LangGraph Supervisor │  (LLM-based; rule baseline kept separately)
                 └──────────┬──────────┘
             ┌──────────────┼──────────────┬───────────────┐
             ▼               ▼             ▼               ▼
        Company          Planner        Progress       Notification
        Research          Agent          Agent            Agent
           Agent              │              │                │
             │                └──────┬───────┘                │
             ▼                       ▼                        ▼
       ChromaDB +              PostgreSQL              Local Scheduler
       PostgreSQL              (Student State)          (APScheduler)
     (KB + citations)
```

No AWS component appears anywhere in this graph. Local NLU/intent-capture is folded into the Supervisor's classification step (replacing AWS Lex V2's role); no separate NLU service is introduced.

**Stack**
- Backend: FastAPI
- Orchestration: LangGraph
- Structured storage: PostgreSQL (student state, chunk metadata, experiment run metadata)
- Vector storage: ChromaDB
- Embeddings: local `sentence-transformers` model by default (provider-abstracted so a hosted embedding API could be swapped in)
- LLM: provider-abstracted; one hosted, cost-appropriate model as default, low/fixed temperature for evaluation runs
- Scheduling: APScheduler (local, in-process) instead of EventBridge/SNS
- Notifications: log line + optional local SMTP-to-self; not a production notification service
- Frontend: React + Vite + TypeScript (Phase 9 only)
- Containerization: Docker Compose for Postgres (+ optional Chroma server)

---

## 4. AWS-to-Local Mapping (documentation only — nothing here is implemented)

| Review-1 AWS component | Local POC replacement | AWS status |
|---|---|---|
| AWS Lex V2 (NLU) | Supervisor's own intent classification step | Future production option |
| AWS Lambda (email parsing) | Local Python parsing function, callable directly or via scheduler | Future production option |
| Amazon S3 (structured JSON storage) | Local disk (`data/`) + PostgreSQL | Future production option |
| EventBridge + SNS (reminders) | APScheduler + local notification sink | Future production option |
| IAM | N/A locally (no cross-service auth needed) | Future production option |
| CloudWatch | Local structured logging (stdout + rotating file) | Future production option |

`boto3` and all AWS SDKs are explicitly excluded from dependencies. Any mention of AWS in generated docs must be under a heading such as "Future Production Deployment Architecture," never implied as implemented or benchmarked.

---

## 5. Five-Experiment Research Methodology

### Experiment 1 — RAG Grounding vs Vanilla LLM
- **Systems**: RAG-grounded Company Research Agent vs. the *same underlying LLM/model/version* with no retrieved context.
- **Dataset**: `evaluation/datasets/rag_questions.json` — versioned, hand-written questions (not copied verbatim from source documents, to avoid trivializing retrieval) with `expected_facts` and `gold_source_doc_ids`.
- **Metrics**: Factual Accuracy, Hallucination Rate, Citation Precision — all computed deterministically (fact/keyword/fuzzy matching against gold facts and gold source ids), never by asking an LLM to declare a winner.
- **Explicit limitation handling**: every scored item gets a `needs_human_review` flag when the automated heuristic's confidence is low (e.g., ambiguous partial fact match) rather than forcing a binary judgment; the report must state that string/keyword-based hallucination detection is an approximation, not a perfect detector.
- **Statistical test**: McNemar's test (paired binary correct/incorrect per question, same question under both systems) for accuracy and hallucination-present/absent; bootstrap CI on the paired difference in each rate. Citation precision is RAG-only (no baseline value), reported descriptively with a bootstrap CI.
- **Primary/secondary endpoints and final N**: Factual Accuracy is the primary endpoint. Hallucination Rate and Citation Precision are secondary metrics, reported but not used to drive the final N. Final N is determined per Section 6.0 based on the paired binary comparison underlying McNemar's test on factual accuracy, before the final dataset is frozen. Unlimited hypothesis testing across every possible metric without this documented primary/secondary distinction is not permitted.

### Experiment 2 — Supervisor Routing Accuracy
- **Systems**: LangGraph LLM Supervisor vs. rule-based/keyword router (a genuinely competent baseline, not a strawman).
- **Dataset**: `evaluation/datasets/routing_queries.json` — labelled utterances across 4 agent classes, including straightforward, paraphrased, ambiguous, and multi-intent items, with the multi-intent labelling convention documented explicitly.
- **Metrics**: per-agent Precision/Recall, Overall Accuracy, Misroute Rate, Added Latency.
- **Statistical test**: McNemar's test (paired correct/incorrect per query) for overall accuracy; Wilcoxon signed-rank for paired latency. Because per-agent Precision/Recall involves 4 separate tests if compared statistically, apply a **Benjamini–Hochberg correction** across those 4 comparisons to control the false discovery rate.
- **Primary/secondary endpoints and final N**: Overall paired routing accuracy is the primary endpoint and drives the final N determination (Section 6.0). The four agent-specific Precision/Recall analyses are secondary analyses and retain the Benjamini–Hochberg correction specified above regardless of the final N chosen.

### Experiment 3 — Multi-Agent vs Monolithic LLM
- **Systems**: full multi-agent LangGraph pipeline vs. one monolithic prompt given equivalent capability/context, including the *same retrieved RAG context* for company-research turns.
- **Fairness requirements (hard constraints)**: same underlying LLM + version for both systems; same knowledge base; same retrieved context where retrieval applies; same evaluation sessions; monolithic prompt reviewed for capability parity before running — if it is noticeably thinner than the sum of the specialised prompts, it must be rewritten before the experiment is executed.
- **Dataset**: `evaluation/datasets/agent_sessions.json` — shared scripted sessions mixing company-research, plan-generation, and progress-check-in turns.
- **Metrics, explicitly separated by measurement type**:
  - *Deterministic/code-based*: Task Completion (rubric-checkable elements present — e.g., a citation exists, a plan object was returned), Latency, Token Usage.
  - *Rubric-based (human or LLM-assisted judge, always disclosed)*: Plan Quality, Overall Response Quality — scored against a written, inspectable rubric stored in the repo (`evaluation/rubrics/plan_quality_rubric.md`, `evaluation/rubrics/overall_quality_rubric.md`); if an LLM judge is used, its full prompt and rubric must be saved alongside the results, and it must never silently pick a "winner" without the rubric breakdown being logged.
- **Statistical test**: McNemar's test (paired, task completion); Wilcoxon signed-rank (paired, latency/tokens/quality scores — non-normal, ordinal-influenced data).
- **Primary/secondary endpoints and final N**: the primary outcome and secondary outcomes must be explicitly named before the final dataset is frozen and before any results are observed (e.g., Task Completion as primary; latency, tokens, plan quality, overall quality as secondary) — the primary outcome must not be chosen after observing results. Final N is based on the paired session/turn design and the chosen primary outcome, determined per Section 6.0.

### Experiment 4 — Retrieval Quality (Fixed-Size vs Semantic Chunking)
- **Systems**: identical corpus, identical queries, identical embedding model, identical retrieval settings — the *only* independent variable is chunking strategy (fixed-size vs semantic).
- **Dataset**: `evaluation/datasets/retrieval_queries.json` — queries paired with fixed, hand-labelled gold-relevant chunk/passage ids, created before any retrieval runs.
- **Metrics**: Precision@5, Recall@5, MRR, nDCG@10 — computed purely from retrieval rankings against gold labels. **No LLM is used to judge relevance at any point in this experiment.**
- **Statistical test**: Wilcoxon signed-rank per metric (paired by query, config A vs config B). A normality check (e.g., Shapiro-Wilk) may be run and reported, but is not used as a mechanical switch to a t-test — bounded metrics like Precision@5/nDCG@10 are ratio/ordinal-influenced and typically violate normality and homoscedasticity assumptions even when a normality test doesn't reject, so Wilcoxon signed-rank is the default unless there's a specific, stated reason (e.g., very large N with clearly continuous, symmetric differences) to prefer a paired t-test. Bootstrap CI on the mean paired difference for each metric.
- **Primary/secondary endpoints and final N**: one primary retrieval metric (e.g., nDCG@10) must be defined before the final run, with the remaining metrics (Precision@5, Recall@5, MRR) treated as secondary. Final N is based on the paired-query design and the primary metric, determined per Section 6.0; the same frozen query set is evaluated against both chunking strategies.

### Experiment 5 — Adaptive Planner vs Static Planner (Paired Simulated-Student Design)
- **Design (strengthened)**: within-subject / paired. Each simulated student is run through **both** conditions using the *same* fixed initial skill profile, learning parameters, available study time, and question-difficulty sequence:
  - `Student 001 → Static Planner`
  - `Student 001 → Adaptive Planner`
  - `Student 002 → Static Planner`
  - `Student 002 → Adaptive Planner`
  - ... etc.
  The only experimental variable is static vs. adaptive planning logic. This removes between-student variance as a confound and is why a paired test is appropriate.
- **Simulation integrity**: the performance-generation model (how a simulated student's latent per-topic skill translates into practice-attempt outcomes) must be fully specified and committed to the repo **before** any experimental run is executed, and must not be edited after results are observed to make either condition win. All generated data is labelled `SIMULATED` in the dataset, in every chart, and in every report table.
- **Metrics**: Topic Mastery Rate, Time-to-Competency, Problem-Solving Success Rate, Improvement in Weak Topics, Number/Effectiveness of Replanning Events.
- **Statistical test**: Wilcoxon signed-rank (paired, per-student difference between adaptive and static) for continuous/ordinal metrics; McNemar's or a paired proportions test for binary mastery-reached/not-reached outcomes if modeled that way; report if a chi-square on aggregate proportions is used instead, and justify. An independent-groups design (Mann–Whitney U) is used only if pairing is genuinely impractical (e.g., if simulation ordering effects contaminate the paired approach) — this must be justified explicitly in the experiment report if chosen instead of the default paired design.
- **Primary/secondary endpoints and final N**: final N refers to the number of paired simulated students, with the same student appearing in both conditions. The simulation model and all its parameters must be frozen before final evaluation, and the final student count must be determined per Section 6.0 before looking at final adaptive-vs-static outcomes.

---

## 6. Statistical Analysis Plan (applies to all five experiments)

### 6.0 Final Sample Size Determination (must happen BEFORE the final dataset is frozen)

Every experiment's numbers currently written elsewhere in this plan as "at least 30", "at least 60", "at least 15", "at least 25", etc. are **development/pipeline-validation sizes only** (see Section 10). They exist to prove the runner, metrics, statistical tests, charts, and output pipeline actually work end-to-end. They must never be silently reused as the final research N.

Before any final experiment is executed, the implementation process must explicitly determine a final sample size by considering:

- the experimental unit (question, query, session/turn, student, etc.)
- paired vs independent design
- the primary metric (see per-experiment primary/secondary split in Section 5 and 6.0.2)
- expected/meaningful effect size
- significance level α = 0.05
- desired statistical power, preferably 0.80, where a meaningful power calculation is possible
- practical compute/API cost constraints
- whether the planned test is parametric or non-parametric
- whether the result should be labelled exploratory because of a limited N

A textbook analytical power calculation is not required when the metric/test makes it unreliable (e.g., bootstrap-based CIs on bounded ratio metrics, or rubric-based ordinal scores with no established effect-size prior). In those cases, use a defensible simulation-based power analysis (simulate the paired test under a plausible effect size to estimate achievable power at candidate N), or explicitly document that a formal power calculation is not reliable here and state that limitation in the report.

**The final N must never be chosen merely because it is convenient or because it happens to produce statistical significance.**

#### 6.0.1 Preventing power analysis from becoming p-hacking

The final sample size must be determined and documented **before** inspecting final outcome results. Specifically, the process must NOT:

- increase N until p < 0.05
- decrease N because a result is inconvenient
- repeatedly re-test until significance is achieved
- choose the sample size based on preliminary/pilot results in a way that changes the hypothesis
- tune the simulation or data-generation process after seeing final results

If sequential sampling is ever used for a given experiment, it must be explicitly designed (stopping rule, alpha-spending or equivalent) and justified in that experiment's write-up before any data collection begins — not adopted informally.

The required procedure, for every experiment, is:

```text
Define hypothesis
      ↓
Define primary metric
      ↓
Choose statistical test
      ↓
Estimate meaningful effect size / power
      ↓
Determine final N
      ↓
Freeze final dataset
      ↓
Run experiment once for final analysis
      ↓
Report result
```

#### 6.0.2 Do not promise guaranteed power

This plan does not promise that every experiment will achieve 80% power. If practical constraints (compute/API cost, corpus size, available student-simulation budget, etc.) make the required N impractically large, the experiment's report must say explicitly:

> "The experiment is underpowered relative to the desired target and should therefore be interpreted as exploratory."

This is preferable to artificially shrinking N to something convenient and presenting the result as confirmatory.

Every experiment must report, at minimum:

- exact sample size (N)
- descriptive statistics (mean/median, SD/IQR as appropriate)
- the statistical test used and why it fits the data structure (unit of observation, paired vs independent, distributional assumptions)
- test statistic
- p-value
- effect size (odds ratio / Cohen's g for McNemar; rank-biserial correlation or Cliff's delta for Wilcoxon/Mann–Whitney)
- confidence interval (bootstrap CI as default, since most metrics are non-normal/bounded)
- significance decision at α = 0.05, with explicit multiple-comparison correction (Benjamini–Hochberg preferred over Bonferroni unless conservatism is specifically wanted) whenever more than one related hypothesis is tested within an experiment (e.g., Experiment 2's 4 per-agent comparisons)
- plain-language interpretation, distinguishing **statistical significance** from **practical/effect-size magnitude**
- explicit power/sample-size discussion: given the project's small-N reality, results from experiments with N below the final N determined per Section 6.0 (or below a documented minimum, computed via a simple/simulation-based power estimate or, if impractical, stated as a limitation) must be labelled **exploratory**, not confirmatory
- the recorded dataset version/checksum this result was computed from (see Section 10.2), so every reported statistic is traceable to an exact frozen dataset

No result is reported as a single p-value in isolation anywhere in the codebase's output or the final report.

---

## 7. Research Validity Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Small sample size | Report exact N; use exact/non-parametric tests; report CIs; label underpowered experiments exploratory |
| Simulated data (Exp. 5) | Fixed simulation model defined before runs; all outputs labelled SIMULATED; never merged with real data |
| LLM nondeterminism | Low/fixed temperature for evaluation; response caching; model+version logged per run |
| Model-version drift mid-project | Model string pinned in config; recorded in every results CSV; re-run affected experiments on forced version changes |
| Prompt sensitivity | All prompts versioned under `prompts/`; no post-hoc editing of a baseline prompt without re-running from scratch |
| Evaluation bias (rubric/LLM-judge) | Written, inspectable rubrics; deterministic scoring preferred; LLM-judge prompts and full rubric breakdowns logged, never a silent verdict |
| Weak baselines | Rule router (Exp 2) and monolithic prompt (Exp 3) explicitly reviewed for parity before running |
| Leakage between eval data and knowledge base | Evaluation questions hand-written, not copied verbatim from source passages; gold labels never fed into generation context |
| Repeated-measures dependence | Paired tests (McNemar, Wilcoxon signed-rank) used wherever the same query/session/student appears under both systems |
| Latency variability | Same machine/network conditions; interleaved (not batched) execution where practical; report median + IQR, not mean alone |
| Multiple comparisons inflating false positives | Benjamini–Hochberg correction applied wherever multiple related sub-hypotheses are tested (e.g., per-agent metrics in Exp 2) |
| Sample-size selection bias / p-hacking | Final N determined via the Section 6.0 procedure BEFORE final outcome inspection; N is never increased/decreased after seeing results; any deviation (e.g., sequential sampling) must be pre-registered and justified |
| Development/pilot results mistaken for final findings | Explicit three-stage dataset lifecycle (Section 10.1): development → optional pilot → frozen final; only the frozen final dataset may produce reported statistics |
| Post-hoc editing of final data after seeing results | Final datasets immutable once frozen (Section 10.3); any correction requires a new dataset version and a full transparent re-run, never a silent edit |

---

## 8. Dependency Graph

```
Phase 0: Repo/infra scaffold
   |
Phase 1: Knowledge base + RAG (ingestion, chunking [both strategies], embeddings, retrieval, citations)
   |
   +--> Phase 2: Experiment 1 (RAG vs Vanilla)      [needs Phase 1 only]
   |
Phase 3: Supervisor + rule-based baseline           [needs Phase 0 only; can run parallel to Phase 1/2]
   |--> Experiment 2 (Routing)
   |
Phase 4: Company Research Agent + Planner Agent as full LangGraph nodes
   (needs Phase 1 RAG + Phase 3 Supervisor)
   |
   +--> Phase 5: Monolithic baseline + Experiment 3 (Multi-agent vs Monolithic)
   |
Phase 6: Experiment 4 (Retrieval configs)           [needs Phase 1's ingestion pipeline only]
   |
Phase 7: Progress Agent + Adaptive Planner (paired sim design) --> Experiment 5
   (needs Phase 4 Planner Agent)
   |
Phase 8: Notifications (local scheduler)
   |
Phase 9: Frontend + full integration + Research Results dashboard + polish
   (needs Phases 1, 3, 4, 7, 8)
```

Experiments 1, 2, and 4 have no dependency on each other and may run in any order once their prerequisite phase is complete. Experiment 3 depends on Phase 4. Experiment 5 depends on Phase 7.

---

## 9. Repository Structure

```
vitian-chatbot/
├── docker-compose.yml
├── .env.example
├── pyproject.toml / requirements.txt
├── app/
│   ├── main.py
│   ├── config.py
│   ├── llm/
│   │   ├── provider.py            # LLM abstraction (swap providers), model+version recorded
│   │   ├── cache.py                # response cache keyed by prompt hash + model + temperature
│   │   └── embeddings.py           # local embedding wrapper (provider-abstracted)
│   ├── agents/
│   │   ├── supervisor.py
│   │   ├── rule_router.py          # baseline for Exp 2 — kept, never weakened
│   │   ├── company_research.py
│   │   ├── planner.py
│   │   ├── progress.py
│   │   ├── notification.py
│   │   └── monolithic_baseline.py  # baseline for Exp 3
│   ├── rag/
│   │   ├── ingest.py
│   │   ├── chunking.py             # fixed_size_chunk() + semantic_chunk(), swappable via config
│   │   ├── retriever.py
│   │   └── citations.py
│   ├── db/
│   │   └── state/
│   │       ├── models.py           # student profile, plan, progress, replanning log ORM models
│   │       └── db.py
│   └── scheduler/
│       └── notifier.py             # APScheduler-based local reminders
├── prompts/
│   ├── supervisor.txt
│   ├── company_research.txt
│   ├── planner.txt
│   ├── progress.txt
│   ├── notification.txt
│   ├── vanilla_baseline.txt
│   └── monolithic_baseline.txt
├── evaluation/
│   ├── datasets/
│   │   ├── rag_questions.json
│   │   ├── routing_queries.json
│   │   ├── agent_sessions.json
│   │   ├── retrieval_queries.json
│   │   └── simulated_students.json     # paired design; clearly labelled SIMULATED
│   ├── rubrics/
│   │   ├── plan_quality_rubric.md
│   │   └── overall_quality_rubric.md
│   ├── metrics/
│   │   ├── fact_matching.py            # deterministic scoring for Exp 1
│   │   ├── retrieval_metrics.py        # P@5, R@5, MRR, nDCG@10 for Exp 4
│   │   └── stats_utils.py              # McNemar, Wilcoxon, bootstrap CI, BH correction
│   └── simulate_students.py            # fixed, pre-registered simulation model for Exp 5
├── experiments/
│   ├── run_experiment_1.py
│   ├── run_experiment_2.py
│   ├── run_experiment_3.py
│   ├── run_experiment_4.py
│   ├── run_experiment_5.py
│   └── run_all.py
├── results/            # raw per-observation CSVs only — never edited by hand
│   ├── experiment_1_raw.csv
│   ├── experiment_2_raw.csv
│   ├── experiment_3_raw.csv
│   ├── experiment_4_raw.csv
│   └── experiment_5_raw.csv
├── analysis/            # statistical outputs + charts — kept separate from raw results
│   ├── experiment_1_statistics.csv
│   ├── experiment_2_statistics.csv
│   ├── experiment_3_statistics.csv
│   ├── experiment_4_statistics.csv
│   ├── experiment_5_statistics.csv
│   └── charts/
├── frontend/             # React + Vite + TS, built in Phase 9
├── tests/
│   ├── test_rag.py
│   ├── test_supervisor.py
│   ├── test_company_research.py
│   ├── test_planner.py
│   ├── test_progress.py
│   └── test_stats_utils.py
└── docs/
    ├── architecture.md
    ├── local_deployment.md
    ├── research_summary.md
    └── future_aws_deployment.md   # AWS discussed ONLY here, as future work
```

`results/` (raw, one row per observation) is kept strictly separate from `analysis/` (derived statistics and charts), matching the requirement to distinguish raw data from statistical processing.

---

## 10. Dataset Requirements

- All evaluation datasets under `evaluation/datasets/` are **versioned** (committed to git, never silently regenerated) and **deterministic** — no random question generation without a fixed seed, and no LLM-generated evaluation questions without human review and a fixed seed if generation is used at all.
- Evaluation questions/gold labels must not be created by copying exact sentences from the knowledge base (this would trivialize retrieval and inflate Experiment 1/4 metrics); they should be written to reflect realistic student phrasing.
- Gold answers/labels are never included in the LLM's generation context — retrieval, not the evaluation harness, decides what context a system receives.

### 10.1 Three dataset stages (every experiment)

**A. Development dataset**
- Small dataset used while implementing and debugging the experiment (see indicative sizes in Section 10.4 — these are for debugging only, never for final reporting).
- Can be modified freely.
- Used only to verify that the experiment runner, metrics, statistical tests, charts, and output pipeline work end-to-end.
- Results from this dataset must **never** be presented as final research findings, in any chart, table, or report.

**B. Pilot dataset (optional)**
- An optional intermediate dataset used to surface implementation/evaluation problems before committing to the final run.
- Must be frozen before the pilot is run.
- Pilot results are exploratory only, and must not be used to tune the final hypothesis, metric definition, or system implementation in a way that introduces post-hoc bias.

**C. Final evaluation dataset**
- Created and frozen **before** the final experiment is executed, using the final N determined per Section 6.0.
- Must not be edited after final results have been inspected.
- Any substantive post-freeze change (adding/removing items, relabeling gold answers, changing the simulation model, etc.) requires creating a new dataset version and re-running the complete experiment — never a silent edit.
- Only this dataset may produce the statistics reported as final research findings.

### 10.2 Dataset-freezing and traceability

Every frozen dataset (pilot or final) must have a recorded, versioned manifest capturing:

- dataset version (e.g., `rag_questions_v1.0`)
- dataset hash/checksum (e.g., SHA256 of the dataset file)
- creation date
- sample size (N)
- experiment code version (e.g., git commit / tag)
- prompt version(s) used
- model name/version used
- statistical-analysis module version

Example, to be written into the experiment results (CSV header/metadata or an accompanying manifest file):

```text
Experiment 1
Dataset: rag_questions_v1.0
SHA256: <checksum>
N: <final N>
Model: <model name/version>
Prompt version: <version>
Experiment code version: <git ref>
Statistical-analysis version: <version>
```

Every reported final statistic must be traceable back to the exact dataset version (and its checksum) that produced it.

### 10.3 Immutability of frozen final datasets

Once a final dataset is frozen:

- experiment/runner code may still be fixed if a genuine bug is discovered
- evaluation labels may **not** be silently changed
- questions/queries/sessions may **not** be added or removed after seeing final results
- expected facts may **not** be rewritten after seeing results
- gold retrieval labels (Experiment 4) may **not** be changed after seeing retrieval results
- simulated-student parameters (Experiment 5) may **not** be changed after seeing Experiment 5 results

If an error is discovered post-freeze, the correction produces a **new dataset version**, and the complete experiment is re-run transparently — the old version and its results are kept, not overwritten.

### 10.4 Indicative development dataset sizes (debugging only — NOT final N)

These sizes exist purely to validate that the pipeline runs correctly; they are not a claim of statistical sufficiency and are not to be used as the final research sample size. The final N for every experiment is determined via the Section 6.0 procedure before the final dataset is frozen.

- **Experiment 1 (RAG vs Vanilla):** development ~10–15 questions; final N determined before final run.
- **Experiment 2 (Supervisor vs Rule Router):** development ~20–30 queries; final N determined before final run.
- **Experiment 3 (Multi-Agent vs Monolithic):** development ~5 sessions; final N determined before final run.
- **Experiment 4 (Retrieval Quality):** development ~10 queries; final N determined before final run.
- **Experiment 5 (Adaptive vs Static):** development ~5 simulated students; final N determined before final run.

These development sizes may be adjusted if necessary during implementation — what must not change is the rule that they are never substituted for the final, power-informed N.

---

## 11. Reproducibility & Cost-Control Strategy

- **Provider abstraction**: `app/llm/provider.py` exposes a single `.complete(prompt, **kwargs)` interface; swapping providers/models requires no changes to agent code.
- **Model/version recording**: every experiment run writes the exact model name, version/date string, and temperature into the results CSV alongside each row.
- **Caching**: `app/llm/cache.py` caches responses keyed by (prompt hash, model, temperature) so re-running an experiment during debugging does not repeatedly incur API cost — cache is bypassed only via an explicit `--no-cache` flag.
- **Low/fixed temperature**: evaluation runs default to `temperature=0` (or as close to deterministic as the provider allows) unless an experiment specifically needs to observe generation variance.
- **Local embeddings by default**: `sentence-transformers` runs locally for all RAG/retrieval work, avoiding embedding API costs entirely; a hosted embedding provider is optional and provider-abstracted the same way as the LLM.
- **Prompt versioning**: every prompt lives in `prompts/*.txt`, tracked in git; no prompt used in an experiment may be edited post-hoc without a documented reason and a full re-run.
- **Timestamps**: every experiment run is timestamped in its output filename or a run-id column, so historical runs are never silently overwritten without a trace.

---

## 12. Phase-by-Phase Implementation Roadmap

**Phase 0 — Repo & infra scaffold.** Deps: none. Research outcome: establishes reproducibility (logging, config, experiment/results/analysis skeleton, caching). App outcome: runnable FastAPI skeleton + Postgres via Docker Compose.

**Phase 1 — Knowledge base & RAG.** Deps: Phase 0. Research outcome: enables Experiments 1 and 4. App outcome: ingestion pipeline, independently testable retriever, both chunking strategies implemented behind a swappable interface.

**Phase 2 — Experiment 1 (RAG vs Vanilla).** Deps: Phase 1. Research outcome: factual accuracy / hallucination / citation precision results with explicit `needs_human_review` flagging. App outcome: none new — stop-and-verify checkpoint.

**Phase 3 — Supervisor & routing.** Deps: Phase 0. Research outcome: Experiment 2 results (accuracy, misroute rate, latency, BH-corrected per-agent comparisons). App outcome: working LangGraph Supervisor + retained rule-based router.

**Phase 4 — Company Research Agent + Planner Agent (full agents).** Deps: Phases 1, 3. Research outcome: prerequisite infra for Experiment 3. App outcome: two specialised agents fully wired into the graph with typed state and failure handling.

**Phase 5 — Multi-Agent vs Monolithic experiment.** Deps: Phase 4. Research outcome: Experiment 3 results with deterministic vs rubric-based metrics clearly separated. App outcome: none new (monolithic baseline exists only for evaluation).

**Phase 6 — Retrieval experiment.** Deps: Phase 1. Research outcome: Experiment 4 results, no-LLM-judge retrieval evaluation. App outcome: optionally adopt the winning chunking config in production RAG.

**Phase 7 — Progress Agent + Adaptive Planner + Experiment 5 (paired design).** Deps: Phase 4. Research outcome: Experiment 5 results from the paired simulated-student design. App outcome: full closed-loop planning system.

**Phase 8 — Notifications.** Deps: Phase 7 (for plan-related reminders) — can start once Phase 4 exists for basic deadline reminders. Research outcome: none (application-only). App outcome: local APScheduler-based reminders + demonstration notification sink.

**Phase 9 — Frontend & Research Results dashboard.** Deps: Phases 1, 3, 4, 7, 8. Research outcome: none new. App outcome: complete local demo built on the exact evaluated components, including a Research Results section presenting real statistics.

---

## 13. Full Cursor/Antigravity Prompts (one per phase, copy-pasteable)

Every experiment-running phase prompt (Phases 2, 3, 5, 6, 7) follows this pattern — Cursor/Antigravity must NOT treat any "at least N" style figure as the final research N:

```text
Development dataset
        ↓
Validate implementation
        ↓
Determine final sample size
        ↓
Create/freeze final dataset
        ↓
Run final experiment
        ↓
Generate statistical results
```

### Phase 0 Prompt
```
You are working in an existing (possibly empty) repository for a project called
"VITian Chatbot Local POC". Before making changes, inspect the repository
structure and report what already exists.

Goal: scaffold the project infrastructure only. Do NOT implement any agent
logic, RAG, or frontend yet.

Create:
1. Python project setup (pyproject.toml or requirements.txt) with: fastapi,
   uvicorn, langgraph, langchain-core, chromadb, sqlalchemy, psycopg2-binary,
   pydantic, pydantic-settings, pytest, python-dotenv, sentence-transformers,
   apscheduler, pandas, scipy, statsmodels, matplotlib. Do NOT add boto3 or
   any AWS SDK.
2. docker-compose.yml with services: postgres, and the app itself. Use a
   local persistent Chroma directory (not a Chroma server) unless there's a
   strong reason to run Chroma as its own service.
3. app/config.py reading env vars via pydantic-settings (LLM provider name,
   API key env var name, model name/version string, temperature, embedding
   model name, DB URL), with .env.example documenting each.
4. app/main.py: a FastAPI app with a /health endpoint only.
5. Structured logging (stdout + rotating file under logs/), including a
   helper to log model name/version/temperature/timestamp alongside any
   future LLM call.
6. Folder skeleton exactly matching this structure (empty __init__.py or
   .gitkeep where needed):
   app/llm, app/agents, app/rag, app/db/state, app/scheduler,
   prompts/, evaluation/datasets, evaluation/rubrics, evaluation/metrics,
   experiments/, results/, analysis/charts, tests/, docs/.
7. app/llm/cache.py: a simple cache keyed by (prompt hash, model, temperature)
   using a local SQLite or file-based store — implement the interface now
   even though no LLM calls exist yet, so later phases can use it
   immediately.
8. pytest config and one trivial test (tests/test_health.py hitting /health).
9. docs/architecture.md and docs/future_aws_deployment.md: the latter must
   state clearly that AWS Lex/Lambda/S3/EventBridge/SNS/IAM/CloudWatch are
   documented ONLY as future production deployment options and are not
   implemented or benchmarked in this POC.

Constraints:
- Do not add AWS SDKs or AWS-specific config anywhere.
- Do not build the frontend.
- Run the test suite and report the actual output verbatim. Do not claim
  success without running pytest.
- Do not modify files outside what this phase requires.

Report: files created, how to run `docker-compose up` and `pytest`, and any
issues encountered.
```

### Phase 1 Prompt
```
Context: Phase 0 scaffolding exists. Inspect app/, prompts/, evaluation/,
and app/llm/cache.py before changing anything, and summarize what you find.

Goal: implement the knowledge base ingestion and RAG retrieval pipeline,
independently testable from any agent, with BOTH chunking strategies needed
later by Experiment 4.

Implement in app/rag/:
1. ingest.py — loads raw documents from data/raw_docs/ (create this folder
   with 8-12 realistic sample documents covering company eligibility,
   recruitment process, role info, and interview patterns for at least 3
   fictional/sample companies — enough variety to support later evaluation
   sets without evaluation questions copying document sentences verbatim).
2. chunking.py — implement TWO chunking strategies behind one interface:
   - fixed_size_chunk(text, size, overlap)
   - semantic_chunk(text) — paragraph/section-boundary-aware splitting
   Both selectable via config (app/config.py: CHUNKING_STRATEGY), since
   Experiment 4 compares them later using otherwise-identical settings.
3. app/llm/embeddings.py — wrap a local sentence-transformers model
   (default: all-MiniLM-L6-v2) behind a provider-style interface so a
   hosted embedding API could later be swapped in without touching callers.
4. retriever.py — given a query, embed it, query ChromaDB, return top-k
   passages with source document id, chunk id, and similarity score.
5. citations.py — format retrieved passages as citations traceable to
   source documents.
6. Store chunk-to-source metadata (doc id, title, chunk index, char offsets,
   chunking_strategy used) in PostgreSQL so citations and later retrieval
   evaluation can trace back to source documents and configuration.

Write tests/test_rag.py that:
- ingest the sample documents with both chunking strategies into separate
  Chroma collections/namespaces
- verify retrieval returns the expected document for at least 5 hand-written
  queries (not copied verbatim from the documents) against the sample corpus
- verify citation metadata is correctly attached and traceable

Constraints:
- No AWS S3 — raw docs live on local disk under data/raw_docs/.
- Chunking strategy must be fully swappable via config, not hardcoded.
- Use app/llm/cache.py conventions if this phase adds any LLM calls (it
  should not need to — embeddings are local).
- Run tests and report the actual pytest output.
- Do not touch app/agents/ or the frontend.
```

### Phase 2 Prompt
```
Context: Phase 1 RAG pipeline is implemented and tested. Inspect app/rag/
and confirm it works (re-run tests/test_rag.py) before proceeding.

Goal: implement Experiment 1 (RAG vs Vanilla LLM) end-to-end with a
deterministic, limitation-aware evaluation methodology — producing real
results, not fabricated numbers.

Steps:
1. Create evaluation/datasets/dev/rag_questions_dev.json with ~10-15 hand-
   written development questions (not copied verbatim from source
   documents). This DEVELOPMENT dataset is for validating the pipeline
   only — it may be freely edited and its results must never be reported
   as final findings.
2. Build and run the full pipeline (steps 6-11 below) against the
   development dataset first, and confirm the runner, metrics, statistical
   tests, and charts all work end-to-end.
3. Final Sample Size Determination (BEFORE building the final dataset):
   follow Section 6.0 to determine the final N for the paired binary
   comparison (factual accuracy is primary; hallucination rate and citation
   precision are secondary). Use a simulation-based power estimate where a
   textbook calculation isn't reliable, or explicitly document why a formal
   power calculation isn't reliable here and treat the result as
   exploratory. Do not pick N to guarantee significance. If the sample
   corpus limits how many distinct questions are meaningful, state that
   explicitly as a limitation rather than inflating the dataset.
4. Create evaluation/datasets/rag_questions_v1.0.json with the determined
   final N of hand-written questions (not copied verbatim from source
   documents). Freeze it (record dataset version, SHA256 checksum, creation
   date, N, prompt version, model/version, experiment code version per
   Section 10.2) before running the final experiment. Each entry:
   {
     "question_id": str,
     "question": str,
     "expected_facts": [str, ...],
     "gold_source_doc_ids": [str, ...]
   }
5. app/llm/provider.py — implement the LLM abstraction now: a class with a
   .complete(prompt, temperature=0) method, default backed by one hosted
   provider reading its API key from env, recording model name+version in
   every response object it returns. Must be swappable via config.
6. app/agents/company_research.py (RAG-grounded): retrieves via
   app/rag/retriever.py, generates via app/llm/provider.py, returns answer +
   citations.
7. prompts/vanilla_baseline.txt + a vanilla baseline function: same LLM,
   same question, NO retrieved context.
8. evaluation/metrics/fact_matching.py — deterministic scoring, NOT another
   LLM call:
   - factual_accuracy: proportion of expected_facts matched (substring or
     documented fuzzy match) in the answer
   - hallucinated (bool): a fixed, documented heuristic for unsupported
     claims (e.g., a claim template matched in the answer that doesn't
     correspond to any gold fact/source) — explicitly document this is an
     approximation
   - citation_precision (RAG only): proportion of cited passages whose
     source doc id is in gold_source_doc_ids
   - needs_human_review (bool): set true whenever the heuristic's match
     confidence is ambiguous (e.g., partial fact match, borderline
     hallucination signal) — this flag must be surfaced in the raw results,
     not silently resolved either way
9. experiments/run_experiment_1.py: run both systems — first against the
   development dataset to validate the pipeline, then, once validated,
   against the frozen final dataset (rag_questions_v1.0.json) for the
   reported results — using app/llm/cache.py so repeated runs don't
   re-incur API cost; write results/experiment_1_raw.csv with per-question
   rows: question_id, system, answer, factual_accuracy, hallucinated,
   citation_precision, needs_human_review, model_name, model_version,
   temperature, timestamp, dataset_version, dataset_sha256. Only the run
   against the frozen final dataset may be reported as the final result.
10. evaluation/metrics/stats_utils.py: implement McNemar's test (paired
   binary), bootstrap CI, and a generic effect-size helper — this module is
   reused by later experiments too. Compute McNemar's test on paired
   correct/incorrect (accuracy) and hallucinated/not between systems;
   bootstrap CI on the accuracy difference and hallucination-rate
   difference. Write analysis/experiment_1_statistics.csv with: sample_size,
   test_statistic, p_value, effect_size, ci_lower, ci_upper, significant
   (bool at alpha=0.05), pct_needs_human_review, dataset_version,
   dataset_sha256.
11. Generate analysis/charts/experiment_1_chart.png (accuracy, hallucination
   rate, citation precision by system), computed from the frozen final
   dataset run only.

Constraints:
- Do NOT hardcode or fabricate any result values.
- Actually run experiments/run_experiment_1.py and report the real output,
  including if results do not support the hypothesis.
- Explicitly print/report the percentage of items flagged
  needs_human_review and state in output that automated hallucination
  detection here is a heuristic, not a perfect or human-equivalent judge.
- Do not modify Phase 1 RAG internals except to expose what's needed here.
- The final N must be determined per Section 6.0 BEFORE the final dataset
  is frozen and BEFORE inspecting final outcome results — never increase,
  decrease, or re-sample N after seeing results to chase or avoid
  significance.
- Once rag_questions_v1.0.json is frozen, do not edit its questions,
  expected_facts, or gold_source_doc_ids after seeing final results; any
  correction requires a new dataset version and a full re-run.

Report: the actual generated CSV contents (or a faithful summary) from the
frozen final dataset run, the dataset version/checksum used, the actual
statistical results, and whether the Review-1 hypothesis was supported.
```

### Phase 3 Prompt
```
Context: inspect existing app/agents/ and app/rag/ before changing anything.

Goal: implement the LangGraph Supervisor and a genuinely competent rule-
based baseline router, then run Experiment 2 with corrected per-agent
comparisons.

Steps:
1. app/agents/supervisor.py: a LangGraph node classifying an incoming
   utterance's intent into {company_research, planner, progress,
   notification} via an LLM call using prompts/supervisor.txt (temperature
   0 for evaluation determinism), returning the routing decision and
   latency.
2. app/agents/rule_router.py: a keyword/regex-based baseline for the same
   four labels. Build this with genuine care — a reasonably complete
   keyword/phrase list per agent covering common phrasings — since it must
   be a fair baseline, not a strawman.
3. evaluation/datasets/dev/routing_queries_dev.json: ~20-30 labelled
   DEVELOPMENT utterances across the four agents, used only to validate the
   runner/metrics/pipeline — never reported as final findings; may be
   freely edited.
4. Final Sample Size Determination (BEFORE building the final dataset):
   follow Section 6.0 to determine the final N, primarily on the basis of
   overall paired routing accuracy (McNemar's test). Do not pick N to
   guarantee significance.
5. evaluation/datasets/routing_queries_v1.0.json: the determined final N of
   labelled utterances across the four agents, including straightforward,
   paraphrased, ambiguous, and multi-intent examples. Document explicitly,
   in a comment or README note in the same folder, how "correct" is scored
   for multi-intent utterances (e.g., any acceptable label counts, or a
   pre-assigned primary-intent label is used). Freeze this dataset (version,
   SHA256, N, prompt/model/code versions per Section 10.2) before the final
   run.
6. experiments/run_experiment_2.py: validate against the development
   dataset first, then run both routers over the frozen final dataset,
   recording per query: query_id, expected_agent, predicted_agent, system,
   latency_ms, correct, model_name/model_version (for the Supervisor row),
   timestamp, dataset_version, dataset_sha256. Write
   results/experiment_2_raw.csv from the frozen final dataset run only.
7. Analysis (reuse evaluation/metrics/stats_utils.py):
   - Overall accuracy: McNemar's test (paired correct/incorrect per query)
     between Supervisor and rule baseline.
   - Latency: Wilcoxon signed-rank on paired latency.
   - Per-agent Precision/Recall: compute for both systems; if statistically
     comparing per-agent metrics across systems, apply a Benjamini–Hochberg
     correction across the 4 per-agent comparisons and report both raw and
     corrected p-values.
   Write analysis/experiment_2_statistics.csv with all of: sample_size,
   test_statistic, p_value, bh_corrected_p_value (where applicable),
   effect_size, ci_lower, ci_upper, significant, dataset_version,
   dataset_sha256.
8. Generate a confusion matrix per system and a precision/recall-by-agent
   bar chart under analysis/charts/, computed from the frozen final dataset
   run only.

Constraints:
- Keep rule_router.py as a standalone, reusable, genuinely-competent
  baseline module — it is not deleted or weakened later.
- Actually run the experiment and report real numbers from the frozen
  final dataset.
- Do not build full Company Research/Planner/Progress/Notification agent
  bodies yet — Supervisor can route to stub handlers for this phase's
  testing purposes.
- The final N must be determined per Section 6.0 before the final dataset
  is frozen and before inspecting final outcome results. Once
  routing_queries_v1.0.json is frozen, do not edit labels/utterances after
  seeing final results; a correction requires a new dataset version and a
  full re-run.
```

### Phase 4 Prompt
```
Context: inspect app/agents/supervisor.py, app/agents/company_research.py
(from Phase 2), and app/rag/ before proceeding.

Goal: turn Company Research (already partially built in Phase 2) and a new
Planner Agent into full LangGraph nodes wired to the Supervisor, with typed
state, tools, and failure handling.

Steps:
1. Define a shared LangGraph state schema (app/agents/state_schema.py):
   student_id, conversation history, target_companies, skill_profile,
   current_plan, last_agent_output.
2. Wire company_research.py as a graph node with a defined failure path
   (e.g., retrieval returns nothing -> explicit "insufficient information"
   response, never a hallucinated guess).
3. app/agents/planner.py: generatePlan(target_companies, skill_profile,
   available_time) -> structured study plan (list of topics/tasks with
   target dates); revisePlan(current_plan, signal) as a stub for now (full
   adaptive logic comes in Phase 7). Use prompts/planner.txt.
4. Typed input/output Pydantic models for both agents' tool calls.
5. Structured logging for every agent invocation (inputs, outputs, latency,
   errors, model name/version) to support later experiments.
6. tests/test_company_research.py and tests/test_planner.py covering: a
   normal case, a no-context/failure case, and a malformed-input case.

Constraints:
- Do not implement Progress or Notification agents yet.
- Do not implement the monolithic baseline yet (next phase).
- Preserve rule_router.py and the Experiment 1/2 code untouched.
- Run all tests and report actual results.
```

### Phase 5 Prompt
```
Context: inspect the full app/agents/ package before proceeding.

Goal: implement a fair monolithic baseline and run Experiment 3 with
deterministic and rubric-based metrics explicitly separated.

Steps:
1. prompts/monolithic_baseline.txt: one carefully engineered system prompt
   giving a single LLM call the equivalent instructions and context to
   perform company research, plan generation, and progress-aware responses
   in one turn. Before running the experiment, compare this prompt's
   coverage against the sum of prompts/company_research.txt +
   prompts/planner.txt + prompts/supervisor.txt — if it's noticeably
   thinner, rewrite it until it's a fair comparison, and state in your
   report that you did this check.
2. app/agents/monolithic_baseline.py: given a session, produce a single-
   prompt-per-turn response using retrieved context assembled the SAME way
   as the multi-agent pipeline (same retriever, same top-k).
3. evaluation/datasets/dev/agent_sessions_dev.json: ~5 DEVELOPMENT sessions
   (2-5 turns each) mixing company-research, plan-generation, and
   progress-check-in requests, used only to validate the runner/metrics —
   never reported as final findings; may be freely edited.
4. evaluation/rubrics/plan_quality_rubric.md and
   evaluation/rubrics/overall_quality_rubric.md: write explicit, inspectable
   scoring criteria (e.g., 1-5 scale with defined anchors) before running
   any evaluation.
5. Explicitly define, before building the final dataset: the primary
   outcome (e.g., Task Completion) and the secondary outcomes (latency,
   tokens, plan quality, overall quality) for this experiment. The primary
   outcome must not be chosen after observing results.
6. Final Sample Size Determination (BEFORE building the final dataset):
   follow Section 6.0, based on the paired session/turn design and the
   primary outcome chosen in step 5. Do not pick N to guarantee
   significance.
7. evaluation/datasets/agent_sessions_v1.0.json: the determined final N of
   representative sessions (2-5 turns each) mixing company-research,
   plan-generation, and progress-check-in requests. Freeze this dataset
   (version, SHA256, N, prompt/model/code versions per Section 10.2)
   before the final run.
8. experiments/run_experiment_3.py: validate against the development
   dataset first, then run every session in the frozen final dataset
   through both the full multi-agent graph and the monolithic baseline,
   recording per turn: session_id, turn_id, system, latency_ms,
   tokens_used, task_completion (deterministic bool, rubric-checkable
   elements present — document exactly what's checked), plan_quality_score
   (per plan_quality_rubric.md), overall_quality_score (per
   overall_quality_rubric.md), dataset_version, dataset_sha256. If an LLM
   judge is used for the rubric scores, save its full prompt/rubric text
   and its raw per-item justification alongside the score — never just the
   number.
9. Write results/experiment_3_raw.csv (each row tagged as
   metric_type=deterministic or metric_type=rubric_based), from the frozen
   final dataset run only.
10. Analysis: McNemar's test for task completion (paired per session/turn);
   Wilcoxon signed-rank for latency, tokens, plan quality, overall quality
   (paired, non-normal assumption stated and justified). Report effect
   sizes (odds ratio/Cohen's g for McNemar; rank-biserial for Wilcoxon) and
   bootstrap CIs. Write analysis/experiment_3_statistics.csv with
   dataset_version and dataset_sha256 included.
11. Distribution plots for latency and token usage; box plots for quality
   scores, saved under analysis/charts/, computed from the frozen final
   dataset run only.

Constraints:
- The monolithic prompt must not be deliberately weakened — verify and
  report the parity check from step 1 before running.
- Identical underlying LLM model/version and identical RAG context for both
  systems within a given session.
- Actually run this and report real numbers from the frozen final dataset,
  including if the multi-agent system does NOT win on some metric — that
  is an acceptable finding.
- Never let a rubric-based/LLM-judge score be reported without its
  rubric/justification also being saved.
- The final N must be determined per Section 6.0 before the final dataset
  is frozen and before inspecting final outcome results. Once
  agent_sessions_v1.0.json is frozen, sessions/turns and rubrics may not be
  edited after seeing final results; a correction requires a new dataset
  version and a full re-run.
```

### Phase 6 Prompt
```
Context: inspect app/rag/chunking.py and retriever.py before proceeding.

Goal: run Experiment 4 (retrieval quality) fully independent of any agent
or generated-answer quality, with no LLM involved in scoring.

Steps:
1. evaluation/datasets/dev/retrieval_queries_dev.json: ~10 DEVELOPMENT
   queries paired with hand-labelled gold-relevant chunk/passage ids, used
   only to validate the runner/metrics — never reported as final findings;
   may be freely edited.
2. Final Sample Size Determination (BEFORE building the final dataset):
   follow Section 6.0, based on the paired-query design and one primary
   retrieval metric (e.g., nDCG@10) defined now, with the remaining metrics
   (Precision@5, Recall@5, MRR) treated as secondary. Do not pick N to
   guarantee significance.
3. evaluation/datasets/retrieval_queries_v1.0.json: the determined final N
   of queries, each paired with a hand-labelled list of gold-relevant
   chunk/passage ids from the Phase 1 corpus, labelled BEFORE any retrieval
   runs are executed (expand the sample corpus if needed for enough
   labelled variety, documenting the expansion). Freeze this dataset
   (version, SHA256, N, model/code versions per Section 10.2) before the
   final run.
4. Ingest the same corpus twice — once per chunking strategy (fixed-size,
   semantic) — into separate Chroma collections, with identical embedding
   model and identical retrieval settings otherwise, so retrieval quality is
   the only difference being measured.
5. evaluation/metrics/retrieval_metrics.py: deterministic implementations of
   Precision@5, Recall@5, MRR, nDCG@10, computed purely from the ranked
   retrieval list vs. gold relevance labels. No LLM call anywhere in this
   file.
6. experiments/run_experiment_4.py: validate against the development
   dataset first, then, for each query in the frozen final dataset and each
   configuration, retrieve top-10 passages and compute all four metrics.
   Write results/experiment_4_raw.csv (per query, per config, per metric,
   dataset_version, dataset_sha256) from the frozen final dataset run only.
7. Analysis: run a normality check (e.g., Shapiro-Wilk) on the paired
   differences per metric and report the result, but do NOT use it as a
   mechanical trigger for a t-test — default to Wilcoxon signed-rank per
   metric (paired by query, config A vs config B) given these are bounded,
   ratio-like metrics; only use a paired t-test instead if you can state a
   specific justification beyond "Shapiro p > .05" (e.g., large N with
   clearly continuous, symmetric differences), and document that reasoning
   explicitly in the output. Compute bootstrap CI on the mean paired
   difference per metric. Write analysis/experiment_4_statistics.csv with
   dataset_version and dataset_sha256 included, and explicitly flag the
   primary metric (from step 2) vs secondary metrics.
8. Bar/box charts comparing configurations across all four metrics, saved
   under analysis/charts/, computed from the frozen final dataset run only.

Constraints:
- This experiment must not call an LLM to judge relevance at any point —
  relevance labels are fixed ground truth created ahead of time.
- Actually run it and report real results from the frozen final dataset.
- The final N must be determined per Section 6.0 before the final dataset
  is frozen and before inspecting final outcome results. Once
  retrieval_queries_v1.0.json is frozen, gold relevance labels may not be
  changed after seeing retrieval results; a correction requires a new
  dataset version and a full re-run.
```

### Phase 7 Prompt
```
Context: inspect app/agents/planner.py and app/db/state/ before proceeding.

Goal: implement Progress Agent, complete the Adaptive Planner's replanning
logic, build a PAIRED simulated-student environment (same student under
both conditions), and run Experiment 5.

Steps:
1. app/db/state/models.py: extend student state to store progress records
   (topic, score, timestamp), weak/mastered topic flags, and a plan-
   revision log (revision timestamp, triggering signal, topics affected).
2. app/agents/progress.py: recordProgress(topic, score), detectStruggle()
   (rule: e.g., 2+ below-threshold scores on a topic within a window) and
   detectMastery() (rule: score above threshold, sustained).
3. app/agents/planner.py: implement revisePlan(current_plan,
   struggle_signal) for real — reprioritize/insert remedial tasks for
   struggling topics, log a replanning event with its triggering reason.
4. evaluation/simulate_students.py: implement and COMMIT (before any
   experimental run) a documented, non-arbitrary performance-generation
   model. For each simulated student, fix: a per-topic latent skill drawn
   from a distribution, available study time, and a rule mapping
   (latent skill + time invested) -> practice-attempt outcome probability.
   First generate ~5 DEVELOPMENT simulated students
   (evaluation/datasets/dev/simulated_students_dev.json) to validate the
   runner/metrics/pipeline end-to-end — these development results must
   never be reported as final findings and may be freely edited.
5. Final Sample Size Determination (BEFORE building the final dataset):
   follow Section 6.0 to determine the final number of paired simulated
   students, based on the paired per-student design. Use a simulation-based
   power estimate where a textbook calculation isn't reliable, or
   explicitly document why a formal power calculation isn't reliable here
   and treat the result as exploratory. Do not pick N to guarantee
   significance, and do not tune the simulation model based on preliminary
   results.
6. Generate the determined final N of simulated students. Run EACH
   simulated student through BOTH the Static Planner and the Adaptive
   Planner using the IDENTICAL initial skill profile, learning parameters,
   available time, and question-difficulty sequence for both runs of that
   student — the only difference between the two runs is which planner is
   used. Write evaluation/datasets/simulated_students_v1.0.json labelled
   SIMULATED, storing both conditions per student with a shared student_id.
   Freeze this dataset (version, SHA256, N, simulation-model version per
   Section 10.2) before the final run — the simulation model and all its
   parameters must not change after this point.
7. experiments/run_experiment_5.py: validate against the development
   dataset first, then, for each simulated student in the frozen final
   dataset, run both conditions and log per (student_id, condition):
   topic_mastery_rate, time_to_competency, problem_solving_success_rate,
   weak_topic_improvement, replanning_events_count (0 for static by
   definition), dataset_version, dataset_sha256. Write
   results/experiment_5_raw.csv from the frozen final dataset run only,
   with every row/field and every chart clearly labelled "SIMULATED DATA".
8. Analysis: default to Wilcoxon signed-rank (paired by student_id, adaptive
   vs static) for continuous/ordinal metrics; for a binary mastery-
   reached/not-reached formulation, use McNemar's test or an equivalent
   paired-proportions test. If you determine an independent-groups design
   (Mann–Whitney U) is preferable instead of the paired design (e.g., due to
   ordering/carryover effects in the simulation), you must justify this
   explicitly in analysis output before switching away from the default
   paired approach. Write analysis/experiment_5_statistics.csv with the
   full standard reporting set (N, descriptives, test statistic, p-value,
   effect size, CI, significance, interpretation, dataset_version,
   dataset_sha256).
9. Trajectory plots (mastery over time, adaptive vs static per student) and
   a replanning-event timeline chart, saved under analysis/charts/, titled
   to include "Simulated Data", computed from the frozen final dataset run
   only.

Constraints:
- Never present simulated_students_v1.0.json output as real user data
  anywhere, including chart titles/labels — always mark "Simulated Data".
- The simulation's performance model (step 4) must be fully defined and
  committed BEFORE looking at whether it produces a result favoring the
  adaptive planner; do not tune it post hoc to manufacture significance.
- Preserve the paired design (same student, same fixed parameters, both
  conditions) unless you explicitly justify deviating from it.
- The final student count must be determined per Section 6.0 before the
  final dataset is frozen and before looking at final adaptive-vs-static
  outcomes.
- Once simulated_students_v1.0.json is frozen, simulated-student parameters
  may not be changed after seeing Experiment 5 results; a correction
  requires a new dataset version and a full re-run.
- Run the experiment and report actual results, including a null result if
  that's what occurs.
```

### Phase 8 Prompt
```
Context: inspect app/agents/notification.py stub (if any) and app/db/state/
before proceeding.

Goal: implement local, non-AWS notification/reminder functionality.

Steps:
1. app/agents/notification.py: scheduleReminder(event, due_date),
   dispatchNotification(student_id, message) — reads deadline/event data
   from student state or a simple local events table (no email-parsing
   pipeline needed for the POC unless you choose to add one from local
   sample "placement emails" as plain text files).
2. app/scheduler/notifier.py: an APScheduler-based background job that
   checks for upcoming deadlines and calls dispatchNotification().
3. Demonstration notification sink: a log line by default; an OPTIONAL
   local SMTP-to-self path if SMTP credentials are present in env,
   otherwise clearly no-op/stubbed with a message saying so.
4. tests/test_notification.py: verify a scheduled reminder fires (using a
   short test interval, not real deadlines) and is dispatched to the log
   sink.

Constraints:
- No AWS SNS/EventBridge/Lambda — everything here is local/in-process.
- Run tests and report actual output.
- Do not touch the frontend yet.
```

### Phase 9 Prompt
```
Context: inspect the full app/ and experiments/ directories; summarize what
exists before proceeding.

Goal: build the polished local demo application using the EXACT evaluated
components from Phases 1-8 (no separate/fake demo system), now that all
five experiments have real results, plus a Research Results dashboard.

Steps:
1. Build the React + Vite + TS frontend: chat interface, student dashboard,
   study-plan view, progress view, company-research interface with visible
   citations, notification panel.
2. Wire FastAPI endpoints for: chat message -> Supervisor graph, plan
   fetch/revise, progress submit, notifications list.
3. Add error handling and loading states in the frontend for slow/failed
   agent calls.
4. Add demo seed data (a few sample students, companies, plans) clearly
   marked as demo/seed data, kept separate from the simulated Experiment 5
   dataset and from the evaluation datasets.
5. Build a "Research Results" section/page in the frontend (or, at minimum,
   a docs/research_summary.md rendered into the app) that presents, for
   each of the five experiments: objective, dataset, sample size, baseline,
   proposed system, statistical test, actual test statistic, actual
   p-value, actual effect size, actual confidence interval, and plain-
   language interpretation — pulled from the real analysis/*.csv files, not
   re-typed by hand. This section must visually/textually distinguish three
   categories on every relevant chart or table:
     MEASURED EXPERIMENTAL RESULT
     ORIGINAL HYPOTHESIS (from Review-1)
     SIMULATED DATA (Experiment 5 only)
6. Write docs/local_deployment.md with setup and run instructions.
7. Write/finalize docs/research_summary.md linking each shipped feature to
   the experiment that validated it, with the actual results obtained, and
   explicitly noting that a feature working in the demo is not by itself
   evidence of the architectural claim — the claim is evidenced only by the
   corresponding experiment's statistics.
8. Confirm docs/future_aws_deployment.md still frames AWS purely as future
   production architecture, not implemented/benchmarked.

Constraints:
- Do not fabricate demo data as if it were experimental results.
- Do not reintroduce AWS services or SDKs anywhere.
- Confirm the frontend actually calls the real backend agents used in the
  experiments, not a separate simplified path.
- Run the app end-to-end locally and report what worked and what didn't.
```

---

## 14. Acceptance Criteria (per phase)

- **Phase 0:** `docker-compose up` starts Postgres + app; `/health` returns 200; `pytest` passes with ≥1 real test executed and output shown; no AWS packages present in dependency file.
- **Phase 1:** Retrieval tests pass for ≥5 hand-written queries; citation metadata correctly links to source docs; both chunking strategies produce non-empty, distinct chunk sets stored with `chunking_strategy` metadata.
- **Phase 2:** development dataset run completed and validated first; final N determined per Section 6.0 before the final dataset was frozen; `rag_questions_v1.0.json` frozen with recorded version/SHA256/N; `results/experiment_1_raw.csv` (from the frozen final dataset run only) has one row per (question × system) including `needs_human_review`, `dataset_version`, `dataset_sha256` columns; `analysis/experiment_1_statistics.csv` contains a real p-value, effect size, and CI (no placeholders); chart file generated from the final run; no hardcoded metric values in code.
- **Phase 3:** development dataset run completed first; final N determined per Section 6.0; `routing_queries_v1.0.json` frozen with recorded version/SHA256/N; `results/experiment_2_raw.csv` (from the frozen final dataset run only) has one row per (query × system) with `dataset_version`/`dataset_sha256`; confusion matrices generated for both systems; BH-corrected p-values reported alongside raw p-values for the 4 per-agent comparisons; rule router achieves non-trivial (not deliberately near-zero) accuracy.
- **Phase 4:** Company Research and Planner nodes callable through the LangGraph app with typed I/O; failure-path tests pass (empty retrieval handled without hallucination).
- **Phase 5:** primary and secondary outcomes explicitly named before the final dataset was frozen; development dataset run completed first; final N determined per Section 6.0; `agent_sessions_v1.0.json` frozen with recorded version/SHA256/N; both systems process identical sessions from the frozen final dataset; `results/experiment_3_raw.csv` populated with a `metric_type` column distinguishing deterministic vs rubric-based rows, plus `dataset_version`/`dataset_sha256`; monolithic prompt parity check documented in the run report; if an LLM judge was used, its rubric/justification is saved alongside scores.
- **Phase 6:** primary retrieval metric named before the final dataset was frozen; development dataset run completed first; final N determined per Section 6.0; `retrieval_queries_v1.0.json` frozen with recorded version/SHA256/N; both chunking configs indexed separately with identical other settings; `results/experiment_4_raw.csv` populated with all four metrics per query per config plus `dataset_version`/`dataset_sha256`; normality-check result reported but not used as a blind t-test trigger.
- **Phase 7:** development simulated-student run completed and validated first; final student count determined per Section 6.0 before the final dataset was frozen; `simulated_students_v1.0.json` frozen with recorded version/SHA256/N, stores paired (same student_id, both conditions, identical fixed parameters) records, clearly labelled SIMULATED; `results/experiment_5_raw.csv` (from the frozen final dataset run only) populated with `dataset_version`/`dataset_sha256`; replanning events logged with triggering signal; paired test used unless a documented justification for an independent-groups alternative is given.
- **Phase 8:** Reminder scheduling test passes on a short test interval; no AWS services referenced in code.
- **Phase 9:** Frontend runs locally, chat round-trips through the real Supervisor graph, plan/progress/notification views reflect live backend state, Research Results section pulls real numbers from `analysis/*.csv` and visually distinguishes measured/hypothesis/simulated content.

**Global criterion for every phase**: Cursor/Antigravity must have actually executed the relevant tests/experiments and pasted real console/CSV output. A phase is not complete on the basis of code existing without a run log. No placeholders, no fabricated numbers, no "this should produce..." language in place of an actual run.

**No experiment may be labelled a FINAL research result unless all of the following hold:**
- the final dataset version and checksum are recorded (Section 10.2)
- the final N was determined per Section 6.0 BEFORE final outcome inspection
- the final dataset was frozen before the final run
- the actual experiment was executed against the frozen final dataset (not the development or pilot dataset)
- raw observations are saved (`results/*_raw.csv`)
- statistical analysis is generated from those raw observations (`analysis/*_statistics.csv`)
- no final result values are hard-coded anywhere in code or reports

---

## 15. Final Application Architecture

Same as Section 3, now fully populated: React frontend → FastAPI → LangGraph Supervisor → {Company Research, Planner, Progress, Notification} agents → PostgreSQL + ChromaDB, with APScheduler driving local reminders. Every agent shown in the demo is the literal code path exercised by its corresponding experiment — there is no separate simplified demo pipeline.

---

## 16. Final Demo Plan (Narrative)

1. **Here is the chatbot** — open the chat interface, show a normal conversational turn.
2. **Here is the Supervisor deciding which agent handles the request** — surface the routing decision in the UI (which agent, and optionally confidence/latency).
3. **Here is the Company Research agent grounding an answer in the knowledge base** — ask a company/eligibility question, show the answer with inline citations back to source documents.
4. **Here is the Planner creating a study plan** — request a plan for a target company; show the generated roadmap.
5. **Here is Progress detecting a struggle** — submit a few low practice scores on a topic; show the struggle signal firing.
6. **Here is Adaptive Planning revising the plan** — show the plan-revision log entry, the triggering signal, and the updated plan.
7. **Here are the experiments that evaluated those architectural decisions** — navigate to the Research Results section.
8. **Here are the actual statistical findings** — walk through each experiment's real sample size, test, p-value, effect size, CI, and interpretation, explicitly labelling MEASURED RESULT vs. ORIGINAL HYPOTHESIS vs. SIMULATED DATA (Experiment 5).
9. **Here are the limitations** — small-N/exploratory flags, simulated-data caveats, heuristic hallucination detection, rubric-based scoring caveats.
10. **AWS is only the future production deployment architecture** — reference `docs/future_aws_deployment.md`, explicit that nothing AWS-related was implemented or benchmarked.

A feature working smoothly in the live demo (step 1–6) is never presented as proof of an architectural claim by itself — the claim is only evidenced by the corresponding experiment's statistics (step 7–8). This distinction should be stated out loud/in text during the demo, not left implicit.

---

## 17. Research-Report Outputs

For each of the five experiments, the pipeline must be able to emit a structured block suitable for direct inclusion in the university research report:

```
Experiment
Objective
Dataset (name, version, SHA256 checksum, N — from the frozen FINAL dataset only)
Final sample size determination summary (how N was chosen, per Section 6.0)
Baseline
Proposed system
Primary metric / Secondary metrics
Statistical test (and why it fits the data structure)
Test statistic
p-value (raw, and BH-corrected where applicable)
Effect size
Confidence interval
Significance decision (alpha = 0.05)
Interpretation (statistical vs practical significance)
Exploratory flag (if underpowered relative to the target)
Limitations
```

Every emitted block must be traceable to the exact frozen final dataset version/checksum that produced it (Section 10.2); development- or pilot-dataset results must never be substituted into this block.

Plus a clean comparison table per experiment and the corresponding chart(s) from `analysis/charts/`. The system does not auto-write the final prose research paper unless separately requested — its job is to produce trustworthy, ready-to-cite experimental evidence.

---

## 18. Limitations and How Results Should Be Interpreted

- This is a course-project-scale POC: sample sizes across all five experiments are necessarily small relative to a production research study. Every statistical result must be read alongside its confidence interval and effect size, not the p-value alone, and experiments below a documented minimum-N threshold are explicitly exploratory.
- Experiment 1's hallucination/factual-accuracy scoring is heuristic (string/fact matching), not human-equivalent judgment; `needs_human_review`-flagged items should be spot-checked before being cited as firm evidence.
- Experiment 3's plan-quality/overall-quality scores are rubric-based and may involve an LLM judge; the rubric and justification are always available for inspection, but rubric-based scores carry more subjectivity than the deterministic completion/latency/token metrics from the same experiment.
- Experiment 5 uses a pre-registered simulation model for student behavior; it demonstrates whether the adaptive-planning *logic* behaves as intended under a defined, disclosed model of student performance — it does not demonstrate real-world student outcomes, and must never be cited as such.
- A component working correctly in the final demo application is evidence of functional correctness, not of the architectural superiority claims — those are established only by the corresponding experiment's statistical result, which may be null, mixed, or in the opposite direction of the original Review-1 hypothesis. Null/negative findings are to be reported with the same rigor and prominence as positive ones.
- AWS scalability, cost, or production behavior is never claimed to have been measured or demonstrated by this project; AWS appears only as documented future work.
