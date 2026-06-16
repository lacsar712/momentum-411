from sqlmodel import SQLModel, create_engine, Session, text
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)

def init_db() -> None:
    SQLModel.metadata.create_all(engine)

def get_session() -> Session:
    return Session(engine)

def check_db() -> bool:
    try:
        with get_session() as session:
            session.exec(text("SELECT 1"))
        return True
    except Exception:
        return False
