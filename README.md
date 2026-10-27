# Desktriage

## What I am building and why



### Problem Statement: Automated Classification and Prioritisation of Escalated Support Tickets

When an AI powered support assistant cannot resolve a user's query, the query may be escalated to a human support team as a ticket. These tickets can concern different topics and vary in the urgency with which they require attention.

Without a consistent triage process, support staff must manually interpret each ticket, determine its category and priority, and decide how it should be routed. This introduces additional workload and can lead to inconsistent prioritisation, incorrect routing, and delays in handling high priority requests.

The problem is to develop a service that automatically classifies escalated tickets by category, assesses their priority, and supports appropriate routing to the relevant support team. To avoid unreliable automated decisions, the service must also identify uncertain classifications and send them for human review rather than assigning them automatically.

The objective is to make ticket handling more consistent, efficient, and reliable while retaining human oversight where necessary.

### Defining the user needs

The requirements are derived from the needs of the people responsible for handling and managing escalated support tickets.

Consistent categorisation: Support staff need to understand what each ticket concerns without having to interpret and categorise every query manually.

Reliable prioritisation: Support staff need to identify which tickets require attention first, particularly when several tickets are awaiting resolution.

Appropriate routing: Tickets need to reach the relevant team or queue to reduce unnecessary reassignment.

Human oversight: Support staff need to review uncertain classifications rather than rely on potentially incorrect automated predictions.

Traceability: Support staff need to understand how a ticket was categorised and prioritised so that decisions can be reviewed and corrected.

Integration: Developers need to connect the triage service to an existing support assistant without coupling the classification logic to the assistant's internal implementation.


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


### Defining the scope 


### Defining the Acceptance criteria




## How it works

## How to run it



## What I would improve with more time
