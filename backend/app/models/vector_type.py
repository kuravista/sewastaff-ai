from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    """Minimal pgvector SQLAlchemy column type for DDL."""

    cache_ok = True

    def __init__(self, dimensions: int = 1536):
        self.dimensions = dimensions

    def get_col_spec(self, **kw):
        return f"vector({self.dimensions})"
