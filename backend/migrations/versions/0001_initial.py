"""Initial evidence-oriented schema for agents; no demonstration market data."""
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE app.agents (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        code text NOT NULL UNIQUE CHECK (length(code) > 0),
        name text NOT NULL CHECK (length(name) > 0),
        enabled boolean NOT NULL DEFAULT false,
        created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE app.skill_versions (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        agent_id uuid NOT NULL REFERENCES app.agents(id) ON DELETE RESTRICT,
        version text NOT NULL,
        sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
        instructions text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (agent_id, sha256),
        UNIQUE (agent_id, version),
        UNIQUE (id, agent_id)
    );
    CREATE TABLE app.materials (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        kind text NOT NULL CHECK (kind IN ('catalog', 'case', 'technical', 'commercial', 'other')),
        title text NOT NULL,
        locator text NOT NULL,
        sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
        content text NOT NULL,
        access_scope text NOT NULL DEFAULT 'internal' CHECK (access_scope IN ('internal', 'client_approved', 'public')),
        ingestion_status text NOT NULL DEFAULT 'registered' CHECK (ingestion_status IN ('registered', 'parsed', 'failed')),
        parsed_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (locator, sha256)
    );
    CREATE TABLE app.companies (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        candidate_name text NOT NULL UNIQUE,
        official_name text,
        official_url text,
        identity_status text NOT NULL DEFAULT 'unverified' CHECK (identity_status IN ('unverified', 'ambiguous', 'verified')),
        competition_status text NOT NULL DEFAULT 'unverified' CHECK (competition_status IN ('unverified', 'confirmed', 'partial', 'not_confirmed')),
        notes text,
        created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE app.runs (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        agent_id uuid NOT NULL REFERENCES app.agents(id) ON DELETE RESTRICT,
        skill_version_id uuid,
        mode text NOT NULL CHECK (mode IN ('baseline', 'daily', 'weekly', 'on_demand')),
        status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'fetching', 'analysing', 'waiting', 'completed', 'partial', 'failed', 'cancelled')),
        question text,
        timezone text NOT NULL DEFAULT 'Europe/Moscow',
        period_start timestamptz,
        period_end timestamptz,
        constraints jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(constraints) = 'object'),
        coverage jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(coverage) = 'object'),
        error text,
        started_at timestamptz,
        finished_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(),
        FOREIGN KEY (skill_version_id, agent_id) REFERENCES app.skill_versions(id, agent_id) ON DELETE RESTRICT,
        CHECK (period_end IS NULL OR period_start IS NULL OR period_end >= period_start),
        CHECK (finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at),
        CHECK (status NOT IN ('completed', 'partial', 'failed', 'cancelled') OR finished_at IS NOT NULL)
    );
    CREATE INDEX runs_agent_created_idx ON app.runs(agent_id, created_at DESC);
    CREATE INDEX runs_pending_idx ON app.runs(status, created_at) WHERE status IN ('queued', 'fetching', 'analysing', 'waiting');
    CREATE TABLE app.sources (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        company_id uuid REFERENCES app.companies(id) ON DELETE RESTRICT,
        url text NOT NULL UNIQUE CHECK (url ~ '^https?://'),
        title text NOT NULL,
        enabled boolean NOT NULL DEFAULT true,
        created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE app.fetch_attempts (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        run_id uuid NOT NULL REFERENCES app.runs(id) ON DELETE RESTRICT,
        source_id uuid NOT NULL REFERENCES app.sources(id) ON DELETE RESTRICT,
        status text NOT NULL CHECK (status IN ('success', 'failed', 'blocked', 'partial')),
        http_status integer CHECK (http_status BETWEEN 100 AND 599),
        error text,
        attempted_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX fetch_source_attempted_idx ON app.fetch_attempts(source_id, attempted_at DESC);
    CREATE TABLE app.documents (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        source_id uuid NOT NULL REFERENCES app.sources(id) ON DELETE RESTRICT,
        sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
        title text NOT NULL,
        content text NOT NULL,
        snapshot_locator text,
        origin_group text,
        published_at timestamptz,
        discovered_at timestamptz NOT NULL DEFAULT now(),
        extraction_status text NOT NULL CHECK (extraction_status IN ('complete', 'partial', 'failed')),
        limitations text,
        UNIQUE (source_id, sha256)
    );
    CREATE TABLE app.evidence (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        document_id uuid NOT NULL REFERENCES app.documents(id) ON DELETE RESTRICT,
        fragment text NOT NULL CHECK (length(fragment) > 0),
        fragment_locator text NOT NULL,
        limitations text,
        created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE app.claims (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        run_id uuid NOT NULL REFERENCES app.runs(id) ON DELETE RESTRICT,
        company_id uuid REFERENCES app.companies(id) ON DELETE RESTRICT,
        statement text NOT NULL,
        status text NOT NULL CHECK (status IN ('statement', 'confirmed', 'conflicting', 'insufficient')),
        scope jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(scope) = 'object'),
        unknowns text,
        created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX claims_run_idx ON app.claims(run_id);
    CREATE TABLE app.claim_evidence (
        claim_id uuid NOT NULL REFERENCES app.claims(id) ON DELETE RESTRICT,
        evidence_id uuid NOT NULL REFERENCES app.evidence(id) ON DELETE RESTRICT,
        PRIMARY KEY (claim_id, evidence_id)
    );
    CREATE TABLE app.reports (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        run_id uuid NOT NULL REFERENCES app.runs(id) ON DELETE RESTRICT,
        version integer NOT NULL DEFAULT 1 CHECK (version > 0),
        title text NOT NULL,
        summary text NOT NULL,
        body_markdown text NOT NULL,
        status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'final', 'corrected')),
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (run_id, version)
    );
    CREATE INDEX reports_run_idx ON app.reports(run_id);
    CREATE TABLE app.recommendations (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        report_id uuid NOT NULL REFERENCES app.reports(id) ON DELETE RESTRICT,
        title text NOT NULL,
        rationale text NOT NULL,
        first_step text NOT NULL,
        limitations text,
        priority text NOT NULL CHECK (priority IN ('high', 'medium', 'low')),
        created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX recommendations_report_idx ON app.recommendations(report_id);
    CREATE TABLE app.decisions (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        report_id uuid REFERENCES app.reports(id) ON DELETE RESTRICT,
        recommendation_id uuid REFERENCES app.recommendations(id) ON DELETE RESTRICT,
        action text NOT NULL CHECK (action IN ('accepted', 'rejected', 'revision_requested')),
        actor_label text NOT NULL CHECK (length(actor_label) > 0),
        comment text,
        created_at timestamptz NOT NULL DEFAULT now(),
        CHECK (num_nonnulls(report_id, recommendation_id) = 1),
        CHECK (action = 'accepted' OR (comment IS NOT NULL AND length(btrim(comment)) > 0))
    );
    CREATE INDEX decisions_report_idx ON app.decisions(report_id, created_at DESC) WHERE report_id IS NOT NULL;
    CREATE INDEX decisions_recommendation_idx ON app.decisions(recommendation_id, created_at DESC) WHERE recommendation_id IS NOT NULL;
    """)


def downgrade():
    # Explicit order; no CASCADE that could remove later, unrelated application tables.
    for table in (
        "decisions", "recommendations", "reports", "claim_evidence", "claims",
        "evidence", "documents", "fetch_attempts", "sources", "runs",
        "companies", "materials", "skill_versions", "agents",
    ):
        op.execute(f"DROP TABLE app.{table}")
