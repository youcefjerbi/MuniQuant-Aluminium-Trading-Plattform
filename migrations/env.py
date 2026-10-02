import os
from pathlib import Path
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.models import Base
config=context.config
config.set_main_option('sqlalchemy.url',os.getenv('DATABASE_URL',config.get_main_option('sqlalchemy.url')).replace('%','%%'))
Path('data').mkdir(exist_ok=True)
if context.is_offline_mode():
    context.configure(url=config.get_main_option('sqlalchemy.url'), target_metadata=Base.metadata,literal_binds=True)
    with context.begin_transaction(): context.run_migrations()
else:
    connectable=engine_from_config(config.get_section(config.config_ini_section),prefix='sqlalchemy.',poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata,render_as_batch=connection.dialect.name=='sqlite')
        with context.begin_transaction(): context.run_migrations()
