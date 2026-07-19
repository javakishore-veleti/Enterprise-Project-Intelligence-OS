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

## Enterprise Project Intelligence OS — Folder Structure

```text
Enterprise-Project-Intelligence-OS/
├── CICD/
│   └── LocalDev/
│       ├── docker-all-up.sh
│       ├── docker-all-down.sh
│       ├── status.sh
│       ├── MongoDB/
│       │   └── docker-compose.yaml
│       ├── PostgreSQL/
│       │   └── docker-compose.yaml (Ensure to reuse existing docker images in the laptop)
│       ├── Airflow/
│       │   └── docker-compose.yaml (Ensure to reuse existing docker images in the laptop)
│       ├── ChromDB/
│       │   └── docker-compose.yaml (Ensure to reuse existing docker images in the laptop)
│
├── Airflow/
│   ├── dags/
│   │   ├── project_dataset_acquire/
│   │   ├── project_dataset_ingest/
│   │   ├── project_dataset_validate/
│   │   ├── project_dataset_index/
│   │   ├── project_dataset_reconcile/
│   │   ├── project_risk_schedule/
│   │   └── portfolio_risk_schedule/
│   ├── plugins/
│   ├── config/
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── requirements.txt
│   └── README.md
│
├── Middleware/
│   ├── Ingestion-API/
│   │   ├── ingestion_api/
│   │   │   ├── api/
│   │   │   │   ├── dependencies/
│   │   │   │   ├── exception_handlers/
│   │   │   │   ├── routers/
│   │   │   │   └── main.py
│   │   │   ├── common/
│   │   │   │   ├── configuration/
│   │   │   │   ├── exceptions/
│   │   │   │   ├── logging/
│   │   │   │   ├── models/
│   │   │   │   ├── security/
│   │   │   │   └── utilities/
│   │   │   ├── interfaces/
│   │   │   │   ├── facades/
│   │   │   │   ├── services/
│   │   │   │   └── daos/
│   │   │   ├── facades/
│   │   │   │   ├── start_ingestion/
│   │   │   │   ├── pause_ingestion/
│   │   │   │   ├── resume_ingestion/
│   │   │   │   ├── cancel_ingestion/
│   │   │   │   ├── retry_ingestion_batch/
│   │   │   │   ├── get_ingestion_status/
│   │   │   │   └── get_reconciliation/
│   │   │   ├── services/
│   │   │   │   ├── ingestion_orchestration/
│   │   │   │   ├── batch_management/
│   │   │   │   ├── checkpoint_management/
│   │   │   │   ├── validation/
│   │   │   │   └── reconciliation/
│   │   │   ├── daos/
│   │   │   │   ├── ingestion_tracking/
│   │   │   │   ├── batch_tracking/
│   │   │   │   └── airflow_gateway/
│   │   │   └── dtos/
│   │   │       ├── requests/
│   │   │       ├── responses/
│   │   │       └── common/
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── contract/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── Admin-API/
│   │   ├── admin_api/
│   │   │   ├── api/
│   │   │   │   ├── dependencies/
│   │   │   │   ├── exception_handlers/
│   │   │   │   ├── routers/
│   │   │   │   └── main.py
│   │   │   ├── common/
│   │   │   │   ├── configuration/
│   │   │   │   ├── exceptions/
│   │   │   │   ├── logging/
│   │   │   │   ├── models/
│   │   │   │   ├── security/
│   │   │   │   └── utilities/
│   │   │   ├── interfaces/
│   │   │   │   ├── facades/
│   │   │   │   ├── services/
│   │   │   │   └── daos/
│   │   │   ├── facades/
│   │   │   │   ├── manage_configuration/
│   │   │   │   ├── manage_agents/
│   │   │   │   ├── manage_models/
│   │   │   │   ├── manage_prompts/
│   │   │   │   ├── manage_schedules/
│   │   │   │   ├── get_system_health/
│   │   │   │   └── get_audit_history/
│   │   │   ├── services/
│   │   │   │   ├── configuration_management/
│   │   │   │   ├── agent_management/
│   │   │   │   ├── model_management/
│   │   │   │   ├── prompt_management/
│   │   │   │   ├── schedule_management/
│   │   │   │   ├── system_health/
│   │   │   │   └── audit_management/
│   │   │   ├── daos/
│   │   │   │   ├── configuration/
│   │   │   │   ├── schedules/
│   │   │   │   ├── audit/
│   │   │   │   ├── airflow_gateway/
│   │   │   │   └── graph_run_gateway/
│   │   │   └── dtos/
│   │   │       ├── requests/
│   │   │       ├── responses/
│   │   │       └── common/
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── contract/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── Projects-API/
│   │   ├── projects_api/
│   │   │   ├── api/
│   │   │   │   ├── dependencies/
│   │   │   │   ├── exception_handlers/
│   │   │   │   ├── routers/
│   │   │   │   └── main.py
│   │   │   ├── common/
│   │   │   │   ├── configuration/
│   │   │   │   ├── exceptions/
│   │   │   │   ├── logging/
│   │   │   │   ├── models/
│   │   │   │   ├── security/
│   │   │   │   └── utilities/
│   │   │   ├── interfaces/
│   │   │   │   ├── facades/
│   │   │   │   ├── services/
│   │   │   │   └── daos/
│   │   │   ├── facades/
│   │   │   │   ├── search_projects/
│   │   │   │   ├── get_project/
│   │   │   │   ├── search_work_items/
│   │   │   │   ├── get_work_item_history/
│   │   │   │   ├── get_comments/
│   │   │   │   ├── get_dependencies/
│   │   │   │   ├── get_project_metrics/
│   │   │   │   └── get_portfolio_summary/
│   │   │   ├── services/
│   │   │   │   ├── project_search/
│   │   │   │   ├── work_item_search/
│   │   │   │   ├── history_analysis/
│   │   │   │   ├── dependency_analysis/
│   │   │   │   ├── backlog_metrics/
│   │   │   │   ├── quality_metrics/
│   │   │   │   ├── schedule_metrics/
│   │   │   │   └── portfolio_metrics/
│   │   │   ├── daos/
│   │   │   │   ├── projects/
│   │   │   │   ├── work_items/
│   │   │   │   ├── change_events/
│   │   │   │   ├── comments/
│   │   │   │   ├── relationships/
│   │   │   │   └── project_metrics/
│   │   │   └── dtos/
│   │   │       ├── requests/
│   │   │       ├── responses/
│   │   │       └── common/
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── contract/
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   └── RiskAnalytics-API/
│       ├── risk_analytics_api/
│       │   ├── api/
│       │   │   ├── dependencies/
│       │   │   ├── exception_handlers/
│       │   │   ├── routers/
│       │   │   └── main.py
│       │   ├── common/
│       │   │   ├── configuration/
│       │   │   ├── exceptions/
│       │   │   ├── logging/
│       │   │   ├── models/
│       │   │   ├── security/
│       │   │   └── utilities/
│       │   ├── interfaces/
│       │   │   ├── facades/
│       │   │   ├── services/
│       │   │   └── daos/
│       │   ├── facades/
│       │   │   ├── start_project_analysis/
│       │   │   ├── start_portfolio_analysis/
│       │   │   ├── get_analysis_status/
│       │   │   ├── get_agent_executions/
│       │   │   ├── get_risk_findings/
│       │   │   ├── get_recommendations/
│       │   │   ├── get_reports/
│       │   │   ├── cancel_analysis/
│       │   │   └── resume_analysis/
│       │   ├── services/
│       │   │   ├── analysis_orchestration/
│       │   │   ├── evidence_retrieval/
│       │   │   ├── risk_scoring/
│       │   │   ├── risk_validation/
│       │   │   ├── mitigation_planning/
│       │   │   └── report_generation/
│       │   ├── daos/
│       │   │   ├── analysis_requests/
│       │   │   ├── graph_runs/
│       │   │   ├── agent_executions/
│       │   │   ├── risk_findings/
│       │   │   ├── recommendations/
│       │   │   └── reports/
│       │   ├── dtos/
│       │   │   ├── requests/
│       │   │   ├── responses/
│       │   │   └── common/
│       │   └── graphs/
│       │       ├── project_risk_manager/
│       │       ├── portfolio_risk_orchestrator/
│       │       ├── evidence_retrieval/
│       │       └── risk_review/
│       ├── tests/
│       │   ├── unit/
│       │   ├── integration/
│       │   ├── contract/
│       │   └── graph_paths/
│       ├── Dockerfile
│       ├── pyproject.toml
│       └── README.md
│
├── Agents/
│   ├── project_risk_manager/
│   ├── project_status_tracking/
│   ├── schedule_risk/
│   ├── quality_risk/
│   ├── dependency_risk/
│   ├── resource_risk/
│   ├── backlog_health/
│   ├── delivery_forecasting/
│   ├── risk_scoring/
│   ├── evidence_validation/
│   ├── risk_correlation/
│   ├── risk_deduplication/
│   ├── mitigation_planning/
│   ├── critic/
│   ├── project_reporting/
│   └── executive_reporting/
│
├── Portals/
│   ├── Admin/
│   │   ├── src/
│   │   ├── public/
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   ├── angular.json
│   │   ├── package.json
│   │   └── README.md
│   └── Project-Tracker/
│       ├── src/
│       ├── public/
│       ├── tests/
│       ├── Dockerfile
│       ├── angular.json
│       ├── package.json
│       └── README.md
│

├── Database/
│   ├── PostgreSQL/
│   │   ├── changelogs/
│   │   ├── migrations/
│   │   ├── seed/
│   │   └── README.md
│   └── MongoDB/
│       ├── indexes/
│       ├── initialization/
│       ├── validation/
│       └── README.md
│
├── OpenAPI/
│   ├── ingestion-api.yaml
│   ├── admin-api.yaml
│   ├── projects-api.yaml
│   └── risk-analytics-api.yaml
│
├── docs/
│   ├── architecture/
│   ├── agents/
│   ├── api/
│   ├── data/
│   ├── operations/
│   └── testing/
│
├── tests/
│   ├── end_to_end/
│   ├── performance/
│   ├── resilience/
│   └── fixtures/
│
├── .env.example
├── .gitignore
├── LICENSE-NOTICE.md
├── README.md
└── pyproject.toml
└── package.json (this is for the project developer commands)
        Commands like:
        1. local:containers:start-all stop-all status-all
        2. local:api-services:start-all stop-all status-all
        3. local:portals:start-all stop-all status-all
        4. local:api-portals:start-all stop-all status-all

        Ensure "api-services" internally starts each api microservice independently on different port numbers. 
        While starting the "api-services" ensure the .sh files that starts
        install the python dependencies this way developers need not run the
        python dependencies everytime we add something new.

        While starting the "portals" ensure each portal .sh file does npm install this way everytime we add new dependency developers need not 
        install the dependencies

```

## Copyright and Use

Copyright © 2026 Dr. Kishore Veleti. All rights reserved.

This repository is currently provided for viewing and evaluation only. No permission is granted to copy, modify, distribute, sublicense, or use the source code for commercial or production purposes without prior written authorization from the copyright owner.

Third-party software, frameworks, dependencies, and datasets remain subject to their respective licenses.
