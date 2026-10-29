-- Schema applied by the PostgreSQL container on the first start of the postgres_data volume.
-- Later changes need a new script or a migration; editing this file does nothing
-- once the volume already exists.
--
-- tickets
--   Public ticket id, user id, query text, escalation reason.
--   Status from desktriage_common.statuses, attempt count, timestamps,
--   and the claim fields the worker uses.
--   Unique public ticket id.
--   Index the status the worker polls.
--   Do not add dataset label columns. Category and priority are decisions, not intake fields.
--
-- triage_decisions
--   Ticket reference, category, priority, confidence, human-review flag,
--   destination team, routing outcome, model version, and the time of the decision.
--
-- webhook_deliveries
--   Ticket reference, idempotency key, attempt number, response status,
--   error text, and delivery time.
--   Unique idempotency key.
--
-- The worker claim query needs a row lock so two workers cannot take the same ticket.
-- Claim with SELECT ... FROM tickets WHERE status = 'queued' ... FOR UPDATE SKIP LOCKED.

CREATE TABLE tickets (
    ticket_id text PRIMARY KEY,
    user_id text NOT NULL,
    query_text text NOT NULL,
    escalation_reason text NOT NULL,
    status text NOT NULL,
    attempt_count integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    claimed_at timestamptz,
    next_attempt_at timestamptz,
    CONSTRAINT tickets_ticket_id_present CHECK (btrim(ticket_id) <> ''),
    CONSTRAINT tickets_user_id_present CHECK (btrim(user_id) <> ''),
    CONSTRAINT tickets_query_text_present CHECK (btrim(query_text) <> ''),
    CONSTRAINT tickets_escalation_reason_present CHECK (btrim(escalation_reason) <> ''),
    CONSTRAINT tickets_status_check CHECK (
        status IN (
            'accepted',
            'queued',
            'processing',
            'routed',
            'needs_human_review',
            'failed'
        )
    ),
    CONSTRAINT tickets_attempt_count_check CHECK (attempt_count >= 0)
);

CREATE INDEX tickets_status_idx
    ON tickets (next_attempt_at, created_at)
    WHERE status = 'queued';

CREATE TABLE triage_decisions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id text NOT NULL REFERENCES tickets (ticket_id),
    category text NOT NULL,
    priority text NOT NULL,
    confidence double precision NOT NULL,
    requires_human_review boolean NOT NULL,
    destination text,
    routing_outcome text NOT NULL,
    model_version text NOT NULL,
    decided_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT triage_decisions_category_check CHECK (
        category IN (
            'eligibility_and_enrollment',
            'coverage_and_benefits',
            'claims_and_appeals',
            'costs_and_financial_assistance',
            'access_and_referrals',
            'policy_interpretation',
            'other_or_unknown'
        )
    ),
    CONSTRAINT triage_decisions_priority_check CHECK (
        priority IN ('P1', 'P2', 'P3', 'P4')
    ),
    CONSTRAINT triage_decisions_confidence_check CHECK (
        confidence >= 0 AND confidence <= 1
    ),
    CONSTRAINT triage_decisions_model_version_present CHECK (btrim(model_version) <> ''),
    CONSTRAINT triage_decisions_review_check CHECK (
        (
            requires_human_review
            AND destination IS NULL
            AND routing_outcome = 'needs_human_review'
        )
        OR (
            NOT requires_human_review
            AND destination IS NOT NULL
            AND btrim(destination) <> ''
            AND routing_outcome = 'routed'
        )
    )
);

CREATE INDEX triage_decisions_ticket_id_idx
    ON triage_decisions (ticket_id, decided_at DESC);

CREATE TABLE webhook_deliveries (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id text NOT NULL REFERENCES tickets (ticket_id),
    idempotency_key text NOT NULL,
    attempt_number integer NOT NULL,
    response_status integer,
    error_text text,
    delivered_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT webhook_deliveries_idempotency_key_key UNIQUE (idempotency_key),
    CONSTRAINT webhook_deliveries_idempotency_key_present CHECK (btrim(idempotency_key) <> ''),
    CONSTRAINT webhook_deliveries_attempt_number_check CHECK (attempt_number >= 1),
    CONSTRAINT webhook_deliveries_response_status_check CHECK (
        response_status IS NULL OR (response_status >= 100 AND response_status <= 599)
    ),
    CONSTRAINT webhook_deliveries_result_check CHECK (
        response_status IS NOT NULL OR error_text IS NOT NULL
    )
);

CREATE INDEX webhook_deliveries_ticket_id_idx
    ON webhook_deliveries (ticket_id);
