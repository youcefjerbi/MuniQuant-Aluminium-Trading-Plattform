"""Add Commodity Engine evidence, quality and trace layers.

Revision ID: d8f4c2a91b07
Revises: 5fa787f9511c
"""
from alembic import op
import sqlalchemy as sa

revision = "d8f4c2a91b07"
down_revision = "5fa787f9511c"
branch_labels = None
depends_on = None


def _sqlite_constraints(*clauses):
    """Preserve legacy unnamed checks when SQLite batch mode recreates a table."""
    if op.get_bind().dialect.name != "sqlite":
        return ()
    return tuple(sa.CheckConstraint(clause) for clause in clauses)


def upgrade():
    with op.batch_alter_table("entities", table_args=_sqlite_constraints(
        "kind IN ('company','facility')",
    )) as batch:
        batch.add_column(sa.Column("superseded_by_id", sa.String(), nullable=True))
        batch.create_foreign_key("fk_entities_superseded", "entities", ["superseded_by_id"], ["id"])

    with op.batch_alter_table("sources") as batch:
        batch.add_column(sa.Column("access_method", sa.String(), nullable=False, server_default="manual"))
        batch.add_column(sa.Column("coverage", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("update_frequency", sa.String(), nullable=False, server_default="unknown"))
        batch.add_column(sa.Column("licence_notes", sa.Text(), nullable=False, server_default=""))

    with op.batch_alter_table("runs") as batch:
        batch.add_column(sa.Column("finished_at", sa.String(), nullable=True))

    with op.batch_alter_table("reviews") as batch:
        batch.add_column(sa.Column("normalized_name", sa.String(), nullable=False, server_default=""))
        batch.add_column(sa.Column("match_method", sa.String(), nullable=False, server_default="NONE"))
        batch.add_column(sa.Column("resolver_version", sa.String(), nullable=False, server_default="1.0.0"))
        batch.add_column(sa.Column("context", sa.JSON(), nullable=False, server_default="{}"))
        batch.add_column(sa.Column("document_id", sa.String(), nullable=True))
        batch.create_foreign_key("fk_reviews_document", "documents", ["document_id"], ["id"])

    with op.batch_alter_table("observations", table_args=_sqlite_constraints(
        "valid_to IS NULL OR valid_to >= valid_from",
        "normalized_value IS NULL OR normalized_value >= 0",
    )) as batch:
        batch.add_column(sa.Column("superseded_by_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("supersession_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("superseded_at", sa.String(), nullable=True))
        batch.create_foreign_key("fk_observations_superseded", "observations", ["superseded_by_id"], ["id"])

    with op.batch_alter_table("relationships", table_args=_sqlite_constraints(
        "role IN ('OWNS','OPERATES')",
        "percentage IS NULL OR (percentage >= 0 AND percentage <= 100)",
        "valid_to IS NULL OR valid_to >= valid_from",
    )) as batch:
        batch.add_column(sa.Column("evidence_reference", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("superseded_by_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("supersession_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("superseded_at", sa.String(), nullable=True))
        batch.create_foreign_key("fk_relationships_superseded", "relationships", ["superseded_by_id"], ["id"])

    with op.batch_alter_table("market_observations", table_args=_sqlite_constraints(
        "volume IS NULL OR volume >= 0",
        "open_interest IS NULL OR open_interest >= 0",
    )) as batch:
        batch.add_column(sa.Column("superseded_by_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("supersession_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("superseded_at", sa.String(), nullable=True))
        batch.create_foreign_key("fk_market_observations_superseded", "market_observations", ["superseded_by_id"], ["id"])

    op.create_table(
        "source_access",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_id", sa.String(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("credential_ref", sa.String()),
        sa.Column("terms_url", sa.String()),
        sa.Column("rate_limit_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_source_access_source_id", "source_access", ["source_id"])

    op.create_table(
        "retrieval_attempts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("source_id", sa.String(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("document_id", sa.String(), sa.ForeignKey("documents.id")),
        sa.Column("requested_url", sa.String(), nullable=False),
        sa.Column("attempted_at", sa.String(), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.CheckConstraint("outcome IN ('SUCCESS','UNCHANGED','FAILED')"),
    )
    op.create_index("ix_retrieval_attempts_run_id", "retrieval_attempts", ["run_id"])
    op.create_index("ix_retrieval_attempts_source_id", "retrieval_attempts", ["source_id"])

    op.create_table(
        "resolution_matches",
        sa.Column("review_id", sa.String(), sa.ForeignKey("reviews.id"), primary_key=True),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id"), primary_key=True),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("matched_text", sa.String(), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 1"),
    )

    op.create_table(
        "quality_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("ruleset_version", sa.String(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("finished_at", sa.String()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
    )
    op.create_table(
        "quality_check_results",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("quality_run_id", sa.String(), sa.ForeignKey("quality_runs.id"), nullable=False),
        sa.Column("check_code", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("subject_type", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.CheckConstraint("severity IN ('INFO','WARN','ERROR','BLOCK')"),
    )
    op.create_index("ix_quality_check_results_quality_run_id", "quality_check_results", ["quality_run_id"])
    op.create_index("ix_quality_check_results_subject_id", "quality_check_results", ["subject_id"])


def downgrade():
    op.drop_index("ix_quality_check_results_subject_id", table_name="quality_check_results")
    op.drop_index("ix_quality_check_results_quality_run_id", table_name="quality_check_results")
    op.drop_table("quality_check_results")
    op.drop_table("quality_runs")
    op.drop_table("resolution_matches")
    op.drop_index("ix_retrieval_attempts_source_id", table_name="retrieval_attempts")
    op.drop_index("ix_retrieval_attempts_run_id", table_name="retrieval_attempts")
    op.drop_table("retrieval_attempts")
    op.drop_index("ix_source_access_source_id", table_name="source_access")
    op.drop_table("source_access")

    with op.batch_alter_table("market_observations", table_args=_sqlite_constraints(
        "volume IS NULL OR volume >= 0",
        "open_interest IS NULL OR open_interest >= 0",
    )) as batch:
        batch.drop_constraint("fk_market_observations_superseded", type_="foreignkey")
        batch.drop_column("superseded_at")
        batch.drop_column("supersession_reason")
        batch.drop_column("superseded_by_id")
    with op.batch_alter_table("relationships", table_args=_sqlite_constraints(
        "role IN ('OWNS','OPERATES')",
        "percentage IS NULL OR (percentage >= 0 AND percentage <= 100)",
        "valid_to IS NULL OR valid_to >= valid_from",
    )) as batch:
        batch.drop_constraint("fk_relationships_superseded", type_="foreignkey")
        batch.drop_column("superseded_at")
        batch.drop_column("supersession_reason")
        batch.drop_column("superseded_by_id")
        batch.drop_column("evidence_reference")
    with op.batch_alter_table("observations", table_args=_sqlite_constraints(
        "valid_to IS NULL OR valid_to >= valid_from",
        "normalized_value IS NULL OR normalized_value >= 0",
    )) as batch:
        batch.drop_constraint("fk_observations_superseded", type_="foreignkey")
        batch.drop_column("superseded_at")
        batch.drop_column("supersession_reason")
        batch.drop_column("superseded_by_id")
    with op.batch_alter_table("reviews") as batch:
        batch.drop_constraint("fk_reviews_document", type_="foreignkey")
        batch.drop_column("document_id")
        batch.drop_column("context")
        batch.drop_column("resolver_version")
        batch.drop_column("match_method")
        batch.drop_column("normalized_name")
    with op.batch_alter_table("runs") as batch:
        batch.drop_column("finished_at")
    with op.batch_alter_table("sources") as batch:
        batch.drop_column("licence_notes")
        batch.drop_column("update_frequency")
        batch.drop_column("coverage")
        batch.drop_column("access_method")
    with op.batch_alter_table("entities", table_args=_sqlite_constraints(
        "kind IN ('company','facility')",
    )) as batch:
        batch.drop_constraint("fk_entities_superseded", type_="foreignkey")
        batch.drop_column("superseded_by_id")
