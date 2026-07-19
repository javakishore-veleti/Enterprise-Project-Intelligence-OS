# Enterprise Project Intelligence OS

Enterprise Project Intelligence OS is an AI-driven project and portfolio intelligence platform that analyzes project activity, identifies emerging delivery risks, explains the supporting evidence, recommends mitigation actions, and presents actionable insights through administrative and project-tracking experiences.

The platform is designed around a large public issue-tracking dataset containing 1,822 projects, 2.7 million issues, 32 million historical changes, 9 million comments, and 1 million issue links.

## Product Capabilities

### Project Intelligence

- Search and explore projects
- Review project status and delivery health
- Analyze backlog growth and issue aging
- Monitor sprint and milestone progress
- Examine defects, reopened issues, and unresolved critical issues
- Identify blockers and dependency chains
- Track historical changes in project health
- Compare current conditions with earlier project patterns

### Risk Intelligence

The platform identifies and evaluates:

- Schedule risk
- Delivery risk
- Quality risk
- Dependency risk
- Backlog risk
- Resource-concentration risk
- Workload risk
- Release-readiness risk
- Cross-project risk
- Portfolio-level systemic risk

Every material risk finding is designed to include:

- Risk category
- Probability and impact
- Severity and overall score
- Confidence level
- Supporting project evidence
- Affected issues or projects
- Explanation and assumptions
- Recommended mitigation actions
- Source agent
- Analysis timestamp

### Multi-Agent Analysis

A central Project Risk Manager coordinates specialized agents, including:

- Project Status Tracking Agent
- Schedule Risk Agent
- Quality Risk Agent
- Dependency Risk Agent
- Resource Risk Agent
- Backlog Health Agent
- Delivery Forecasting Agent
- Risk Scoring Agent
- Evidence Validation Agent
- Risk Correlation Agent
- Risk Deduplication Agent
- Mitigation Planning Agent
- Critic Agent
- Project Reporting Agent
- Executive Reporting Agent

The platform selects the agents relevant to each analysis, executes independent specialists in parallel, validates their findings, correlates related risks, removes duplication, and produces consolidated project or portfolio reports.

## User Experiences

### Administration

The administrative experience supports:

- Dataset configuration and ingestion
- Ingestion progress monitoring
- Batch status and failure analysis
- Pause, resume, cancellation, and retry operations
- Data validation and reconciliation
- Workflow monitoring
- Multi-agent execution monitoring
- Agent, model, and prompt configuration
- Risk-analysis scheduling
- System-health monitoring
- Audit-history review

### Project Tracking

The project-tracking experience provides:

- Portfolio dashboard
- Project search and filtering
- Project overview
- Issue and backlog statistics
- Schedule-health analysis
- Quality-health analysis
- Dependency analysis
- Resource and workload indicators
- Current risk register
- Historical risk analyses
- Agent execution progress
- Evidence supporting each finding
- Mitigation recommendations
- Project, portfolio, and executive reports

## How the Platform Works

```text
Public Issue-Tracking Dataset
        |
        v
Batch Ingestion and Operational Workflows
        |
        v
Project Evidence Store
        |
        v
Governed Middleware APIs
        |
        v
LangGraph Multi-Agent Risk Workflows
        |
        v
Risk Findings, Evidence, and Recommendations
        |
        v
Administration and Project-Tracking Experiences
```

Apache Airflow manages dataset acquisition, batch ingestion, scheduled analysis, operational retries, validation, and reconciliation.

LangGraph manages multi-agent state, specialist routing, parallel execution, evidence validation, risk correlation, bounded review loops, mitigation planning, and report generation.

FastAPI middleware services provide the governed boundary between user applications, operational workflows, databases, and LangGraph.

## Technical Architecture

| Area | Technology |
|---|---|
| Operational workflow scheduling | Apache Airflow |
| Multi-agent orchestration | LangGraph |
| Middleware APIs | Python and FastAPI |
| User interfaces | Angular |
| Project evidence storage | MongoDB |
| Operational tracking | PostgreSQL |
| Database schema management | Version-controlled migrations |
| API contracts | OpenAPI and Swagger |
| Local runtime | Docker and Docker Compose |
| Observability | Structured logging and OpenTelemetry-compatible tracing |

## Middleware Capabilities

### Ingestion Management

- Start, pause, resume, cancel, and retry ingestion
- Report ingestion and batch progress
- Return validation and reconciliation results
- Coordinate ingestion requests with operational workflows

### Platform Administration

- Manage platform, agent, model, and prompt configuration
- Configure analysis schedules
- Report system and workflow health
- Administer multi-agent runs
- Expose audit history

### Project Information

- Search projects and issues
- Retrieve project details
- Retrieve issue histories and comments
- Analyze issue dependencies
- Calculate backlog, quality, schedule, and project-health indicators
- Produce portfolio summaries

### Risk Analytics

- Start manual project analysis
- Start portfolio analysis
- Report workflow and agent execution status
- Return risk findings and supporting evidence
- Return mitigation recommendations
- Produce project and executive reports
- Support analysis cancellation and resumption

## Data Ingestion

The source dataset is approximately 5.8 GB compressed and is processed through restartable, batch-oriented workflows.

The ingestion lifecycle includes:

1. Reading the published dataset metadata
2. Checking available disk space
3. Downloading the archive
4. Verifying its checksum
5. Extracting and inspecting its contents
6. Discovering the source structure
7. Ingesting records in configurable batches
8. Recording durable batch checkpoints
9. Retrying recoverable failures
10. Creating database indexes
11. Validating imported records
12. Reconciling source and destination counts
13. Completing the ingestion run

The complete dataset is never loaded into application memory at once.

### Ingestion Characteristics

- Configurable batch size
- Configurable parallelism
- Durable checkpoints
- Idempotent batch processing
- Duplicate protection
- Bounded retries
- Pause and resume
- Failure recovery
- Progress reporting
- Count reconciliation
- Manual and scheduled execution

## Data Responsibilities

### Project Evidence

MongoDB serves as the authoritative evidence store for:

- Projects
- Issues
- Issue histories
- Comments
- Issue links
- Anonymized user references
- Computed project metrics
- Evidence referenced by risk analyses

### Operational State

PostgreSQL maintains:

- Dataset definitions
- Ingestion runs and batches
- Checkpoints and failures
- Reconciliation results
- Analysis requests
- Multi-agent run metadata
- Agent executions
- Analysis schedules
- Administrative configuration
- Audit records

Operational workflow metadata remains isolated from application data.

## API Design Standards

Each middleware service follows a layered request flow:

```text
API Endpoint
    |
    v
Use-Case Facade
    |
    v
Business Service
    |
    v
Data Access Object
    |
    v
Database
```

- API endpoints handle HTTP concerns and typed request validation.
- Facades implement complete application use cases.
- Services implement reusable business capabilities and domain rules.
- Data access objects encapsulate database operations.
- Shared components provide configuration, logging, security, exceptions, and genuine utilities.

Communication across architectural layers uses typed class objects. Public facade, service, and data-access methods normally accept one request object and return one response object. Untyped dictionaries are not passed between layers, and database entities are not exposed directly through API responses.

## OpenAPI and Swagger

Every middleware API provides:

- Versioned endpoints
- OpenAPI specification
- Swagger UI
- Stable operation identifiers
- Typed request and response schemas
- Standard error responses
- Pagination contracts
- Request and response examples
- Liveness and readiness endpoints

User-interface API clients are generated or validated from the OpenAPI contracts to prevent contract duplication.

## Airflow and LangGraph Responsibilities

### Apache Airflow

Airflow manages:

- Dataset acquisition
- Archive extraction
- Batch ingestion
- Data validation
- Index creation
- Count reconciliation
- Scheduled project analysis
- Scheduled portfolio analysis
- Large operational batches
- Operational retries

### LangGraph

LangGraph manages:

- Multi-agent workflow state
- Conditional agent routing
- Parallel specialist execution
- Evidence validation
- Risk correlation and deduplication
- Risk scoring
- Critic and revision loops
- Mitigation generation
- Report generation
- Workflow checkpointing and resumption

Airflow invokes the risk-analysis capability through a governed application boundary. Agent prompts and reasoning logic do not reside inside operational scheduling workflows.

## Evidence-Grounded Analysis

The platform does not send millions of issue-tracking records to a language model.

```text
Issue-Tracking Records
      |
      v
Indexed Queries and Deterministic Metrics
      |
      v
Bounded Evidence Packages
      |
      v
LangGraph Specialist Agents
      |
      v
Validated Risk Findings
```

Deterministic code calculates observable facts such as:

- Backlog growth
- Issue aging
- Resolution velocity
- Reopen rate
- Blocker count
- Dependency depth
- Contributor concentration
- Critical-defect trends

Agents interpret these facts, retrieve supporting evidence, identify risks, challenge unsupported conclusions, and recommend mitigation actions.

## Delivery Roadmap

### Platform Foundation

- Local containerized environment
- Service health checks
- Configuration management
- Database migration framework

### Dataset Ingestion

- Ingestion tracking
- Batch-oriented workflows
- Durable checkpointing
- Database loading
- Administrative monitoring

### Project Intelligence

- Project and issue search
- Historical activity analysis
- Dependency exploration
- Project-health indicators
- Project-tracking experience

### Initial Risk Intelligence

- Project Risk Manager
- Project Status Tracking Agent
- Schedule Risk Agent
- Quality Risk Agent
- Dependency Risk Agent
- Risk Scoring Agent
- Reporting Agent

### Advanced Risk Intelligence

- Backlog Health Agent
- Resource Risk Agent
- Delivery Forecasting Agent
- Evidence Validation Agent
- Risk Correlation Agent
- Risk Deduplication Agent
- Mitigation Planning Agent
- Critic Agent

### Portfolio Intelligence

- Portfolio orchestration
- Cross-project analysis
- Scheduled analysis
- Executive reporting

### Operational Hardening

- Security
- Auditability
- Observability
- Performance testing
- Failure injection
- Resilience testing
- Operational documentation

## Dataset

This project uses a public issue-tracking research dataset created by Lloyd Montgomery, Clara Lüders, and Walid Maalej:

> Montgomery, L., Lüders, C., and Maalej, W.  
> 2022 IEEE/ACM 19th International Conference on Mining Software  
> Repositories (MSR), pp. 73–77.

Dataset record:

https://zenodo.org/records/15719919

The dataset is not distributed as part of this repository. It is acquired separately through the ingestion process.

The dataset remains subject to its own license, usage requirements, and attribution requirements. The copyright notice for this repository does not grant ownership of or additional rights to the dataset.

## Project Status

This project is under active development. APIs, schemas, agent workflows, user interfaces, and operational processes may change as implementation progresses.

It is not currently intended for production use.

## Copyright and Use

Copyright © 2026 Dr. Kishore Veleti. All rights reserved.

This repository is currently provided for viewing and evaluation only. No permission is granted to copy, modify, distribute, sublicense, or use the source code for commercial or production purposes without prior written authorization from the copyright owner.

Third-party software, frameworks, dependencies, and datasets remain subject to their respective licenses.
