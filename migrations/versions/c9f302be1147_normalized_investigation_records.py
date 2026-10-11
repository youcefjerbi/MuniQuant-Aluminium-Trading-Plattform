"""Normalize manual notebook entries, tasks and evidence associations."""
from alembic import op
import sqlalchemy as sa
revision='c9f302be1147'
down_revision='b8e21ad4c902'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('investigation_entry',sa.Column('id',sa.String(),primary_key=True),sa.Column('case_id',sa.String(),sa.ForeignKey('investigation.id'),nullable=False),
        sa.Column('kind',sa.String(32),nullable=False),sa.Column('text',sa.String(),nullable=False),
        sa.Column('document_id',sa.String(),sa.ForeignKey('documents.id')),sa.Column('hypothesis_id',sa.String(),sa.ForeignKey('investigation_entry.id')),
        sa.Column('stance',sa.String(16),nullable=False),sa.Column('source_url',sa.String()),sa.Column('passage',sa.String(),nullable=False),
        sa.Column('published_at',sa.String()),sa.Column('actor',sa.String(),nullable=False),sa.Column('recorded_at',sa.String(),nullable=False))
    op.create_table('investigation_task',sa.Column('id',sa.String(),primary_key=True),sa.Column('case_id',sa.String(),sa.ForeignKey('investigation.id'),nullable=False),
        sa.Column('question',sa.String(),nullable=False),sa.Column('assignee',sa.String(),nullable=False),sa.Column('due_at',sa.String()),
        sa.Column('status',sa.String(16),nullable=False),sa.Column('answer',sa.String(),nullable=False),
        *[sa.Column(n,sa.String(),nullable=False) for n in ('created_by','created_at','updated_by','updated_at')])
    op.create_table('investigation_task_evidence',sa.Column('task_id',sa.String(),sa.ForeignKey('investigation_task.id'),primary_key=True),
        sa.Column('entry_id',sa.String(),sa.ForeignKey('investigation_entry.id'),primary_key=True))
    for table,columns in [('investigation_entry',['case_id','kind']),('investigation_task',['case_id','assignee','due_at','status'])]:
        for column in columns:op.create_index('ix_'+table+'_'+column,table,[column])
    # Existing JSON remains intact; populate normalized records in the same transaction.
    cases=sa.table('investigation',sa.column('id',sa.String()),sa.column('snapshot',sa.JSON()))
    connection=op.get_bind()
    metadata=sa.MetaData()
    entries=sa.Table('investigation_entry',metadata,autoload_with=connection)
    tasks=sa.Table('investigation_task',metadata,autoload_with=connection)
    links=sa.Table('investigation_task_evidence',metadata,autoload_with=connection)
    for identifier,snapshot in connection.execute(sa.select(cases.c.id,cases.c.snapshot)).all():
        for entry in snapshot['entries']:
            values={k:entry.get(k) for k in ['id','kind','text','document_id','hypothesis_id','source_url','published_at','actor','recorded_at']}
            values.update(case_id=identifier,stance=entry.get('stance','context'),passage=entry.get('passage',''))
            connection.execute(entries.insert().values(**values))
        for task in snapshot.get('tasks',[]):
            values={k:v for k,v in task.items() if k!='evidence_entry_ids'}
            connection.execute(tasks.insert().values(case_id=identifier,**values))
            for evidence_id in task['evidence_entry_ids']:
                connection.execute(links.insert().values(task_id=task['id'],entry_id=evidence_id))

def downgrade():
    op.drop_table('investigation_task_evidence');op.drop_table('investigation_task');op.drop_table('investigation_entry')
