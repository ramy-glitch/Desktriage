# Desktriage

## What I am building and why



### Problem Statement: Automated Classification and Prioritisation of Escalated Support Tickets

When an AI powered support assistant cannot resolve a user's query, the query may be escalated to a human support team as a ticket. These tickets can concern different topics and vary in the urgency with which they require attention.

Without a consistent triage process, support staff must manually interpret each ticket, determine its category and priority, and decide how it should be routed. This introduces additional workload and can lead to inconsistent prioritisation, incorrect routing, and delays in handling high priority requests.

The problem is to develop a service that automatically classifies escalated tickets by category, assesses their priority, and supports appropriate routing to the relevant support team. To avoid unreliable automated decisions, the service must also identify uncertain classifications and send them for human review rather than assigning them automatically.

The objective is to make ticket handling more consistent, efficient, and reliable while retaining human oversight where necessary.

### Defining the user needs

The requirements are derived from the needs of the people responsible for handling and managing escalated support tickets.

* Consistent categorisation: Support staff need to understand what each ticket concerns without having to interpret and categorise every query manually.

* Reliable prioritisation: Support staff need to identify which tickets require attention first, particularly when several tickets are awaiting resolution.

* Appropriate routing: Tickets need to reach the relevant team or queue to reduce unnecessary reassignment.

* Human oversight: Support staff need to review uncertain classifications rather than rely on potentially incorrect automated predictions.

* Traceability: Support staff need to understand how a ticket was categorised and prioritised so that decisions can be reviewed and corrected.

* Integration: Developers need to connect the triage service to an existing support assistant without coupling the classification logic to the assistant's internal implementation.


### Defining the functional requirements

Functional requirements describe what the service must do.

1. Ticket ingestion: Accept an escalated ticket through a defined interface.

2. Input validation: Validate incoming ticket data and reject malformed or incomplete requests appropriately.

3. Category classification: Assign a category to each valid ticket from a predefined set of categories.

4. Priority assessment: Determine the ticket's operational priority according to a defined classification or decision policy.

5. Confidence assessment: Determine whether the classification is sufficiently reliable for automated processing.

6. Human review: Send tickets with uncertain predictions to a human review queue.

7. Routing: Map validated category and priority results to the appropriate destination according to configurable routing rules.

8. Decision traceability: Record the predicted category, priority, confidence information, and routing outcome.

9. Error handling: Return meaningful errors for invalid inputs and handle processing failures without silently losing tickets.


### Defining the non functional requirements

Non-functional requirements describe the quality attributes and operational constraints of the service.

* Reliability: The service should process valid tickets consistently and avoid silently dropping requests.

* Performance: Classification should complete within a defined latency target suitable for the ticket-handling workflow.

* Maintainability: Classification logic, routing rules, and API concerns should be separated so that each can be modified and tested independently.

* Scalability: The service should be designed so that processing capacity can be increased as ticket volume grows.

* Security: Ticket data should be protected in transit and at rest where applicable, with appropriate authentication and access controls.

* Privacy: The service should process only the information needed for triage and avoid unnecessarily retaining sensitive information.

* Testability: Classification, prioritisation, routing, and uncertainty handling should be independently testable.

* Observability: Operational logs and metrics should make failures, processing delays, and routing outcomes measurable without unnecessarily exposing sensitive ticket content.

Specific targets for latency, availability, classification performance, and retention will be defined and justified during implementation.

### Defining the scope 

Desktriage is intended to handle the triage stage after escalation, not the original conversation or final resolution of the user's issue.


### Defining the acceptance criteria

The following criteria describe how the service's behaviour and quality will be evaluated.

* A valid ticket can be submitted through the defined API and receives a structured response.

* Invalid ticket data is rejected with an appropriate error response.

* Valid tickets receive a category from the predefined category set.

* Valid tickets receive a priority according to the defined priority policy.

* Tickets below the configured confidence threshold are sent for human review rather than automatically routed.

* Tickets meeting the automatic routing criteria are assigned to the destination specified by the routing rules.

* Each triage decision can be traced through its recorded outcome.

* Automated tests cover successful classification, invalid inputs, routing decisions, and uncertain predictions.

* Evaluation results report category level precision, recall, and F1-score, alongside priority classification performance.

* Urgent ticket recall and the human review rate are measured on an appropriate evaluation dataset.

* API latency is measured against a documented performance target.

Classification thresholds and performance targets will be established using evaluation data rather than chosen solely to make the system appear successful.


## The dataset

Desktriage uses a labelled dataset of synthetic support tickets to develop and evaluate its classification and prioritisation pipeline. Details are in the [dataset card](dataset/desktriage_dataset_card.md). I used the priority definitions in the Cabinet Office [Technical incident management guidance](https://digital-handbook.cabinetoffice.gov.uk/docs/software/technical-incident-management-guidance.html).

Each record represents a query escalated by an AI-powered healthcare-policy assistant because it could not be resolved confidently or safely. The dataset contains fictional user queries covering supported healthcare-policy domains, different reasons for escalation, varying levels of operational priority, and examples requiring human review.

The dataset is designed to support supervised learning for ticket categorisation and experiments with priority assessment, confidence-based routing, and human escalation.

Each ticket is associated with a unique ticket_id and a pseudonymous user_id. These identifiers allow individual tickets to be tracked and multiple tickets from the same fictional user to be represented without including real personal identifiers.

The category and priority labels serve as ground-truth targets for training and evaluation. The dataset will also include ambiguous, out-of-scope, and insufficient-context examples to test the system's ability to avoid unreliable automatic decisions.

Because the dataset is synthetic, its results will not by themselves establish performance on real support tickets. The dataset, labelling rules, and evaluation methodology will be documented to make the limitations of the results explicit.

## The system architecture

The Deskline AI assistant submits an escalated ticket to the intake API. A background worker then classifies it, applies priority and routing rules, stores the result, and notifies a webhook. The assistant can read the ticket ID and status back from the API.

![Desktriage system architecture. The Deskline AI assistant posts a ticket to the intake API. A background worker classifies it, applies priority and routing rules, and stores the result in PostgreSQL. A mock webhook receives the notification, and the ticket ID and status return to the assistant.](docs/system-architecture.png)

### Design rationale and trade-offs

- **Separate API and background worker:** The API can accept tickets without waiting for classification to finish. The worker processes tickets independently and can retry failed jobs. The trade-off is extra complexity in tracking ticket status and recovering interrupted jobs.

- **PostgreSQL database:** PostgreSQL allows the API and multiple workers to access shared ticket data. Row-level locking helps prevent workers from claiming the same ticket. The trade-off is additional setup and maintenance; if the database becomes unavailable, ticket processing and API operations that require it will be affected.

- **Classifier inside the worker:** Keeping the model inside the worker avoids an extra container and internal HTTP requests. The trade-off is that the model and worker must be deployed together, and scaling classification independently is harder.

- **Confidence-based human review:** Low-confidence predictions are sent for human review instead of being routed automatically. This reduces the risk of incorrect assignments but increases manual workload and can delay ticket handling.

- **Rule-based priority and routing:** Explicit rules make operational priorities and team assignments easier to understand and test. However, incomplete or outdated rules can produce incorrect decisions, and some tickets may not fit the defined categories.

- **Webhook notifications:** Notifications alert the destination system when a ticket is ready. If the receiver is unavailable or a request times out, delivery may fail. Retries can also produce duplicate notifications unless idempotency is implemented.

- **Docker Compose:** Containers provide a repeatable environment for running and testing the API, worker, database and notification receiver. The trade-off is additional configuration and resource usage compared with running everything in one process.

- **Persistent database storage:** A Docker volume keeps PostgreSQL data when its container is recreated. However, a volume alone does not protect against every disk failure or data loss, so backups and recovery procedures are still needed.

Desktriage sequence diagram reflecting the PostgreSQL container, with the classifier running inside the background worker and the webhook receiver handling notifications.

![Desktriage sequence diagram reflecting the PostgreSQL container, with the classifier running inside the background worker and the webhook receiver handling notifications.](docs/sequence-diagram.png)

## How it works

## How to run it

### Database

PostgreSQL runs as the `db` service in `docker-compose.yml`. This step starts that service on its own. The API, worker, and webhook are in the same Compose file, and their images do not yet install dependencies or start a process.

Docker Desktop has to be running before Compose can start the container. From the repository root:

```bash
docker compose up db
```

Compose reads `.env`. `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` are the role, password, and database name. `POSTGRES_PORT` is the port published on the host. Inside the container, PostgreSQL listens on port 5432. `DATABASE_URL` uses the host name `db` and port 5432, which is the address the API and worker use on the Compose network.

The first start of an empty `postgres_data` volume creates the database and runs `db/init/001_schema.sql`. The log reports `CREATE TABLE` for `tickets`, `triage_decisions`, and `webhook_deliveries`, then `database system is ready to accept connections`. A later start of the same volume opens the existing database and does not run that script again.

From a second terminal, list the tables. The user and database name are the `POSTGRES_USER` and `POSTGRES_DB` values from `.env`:

```bash
docker compose exec db psql -U desktriage -d desktriage -c "\dt"
```

`\d tickets`, `\d triage_decisions`, and `\d webhook_deliveries` show the columns of each table.

Editing `001_schema.sql` has no effect after the volume exists. A later change needs a new script or a migration. To apply this file again to a local database you are willing to discard:

```bash
docker compose down -v
docker compose up db
```

`docker compose down -v` deletes the `postgres_data` volume.

## What I would improve with more time
