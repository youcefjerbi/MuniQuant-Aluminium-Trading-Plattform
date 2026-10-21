from datetime import date, datetime
from decimal import Decimal

def record(obj):
    def encode(value):
        if isinstance(value,(date,datetime)): return value.isoformat()
        if isinstance(value,Decimal): return format(value,'f')
        return value
    return {c.name: encode(getattr(obj,c.name)) for c in obj.__table__.columns}
