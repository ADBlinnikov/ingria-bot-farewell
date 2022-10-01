from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.dialects.sqlite import DATETIME
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

meta = declarative_base()


def telegram_user_as_dict(data):
    return {
        "id": getattr(data, "id", None),
        "first_name": getattr(data, "first_name", None),
        "last_name": getattr(data, "last_name", None),
        "username": getattr(data, "username", None),
    }


class User(Base):
    __tablename__ = "User"
    # Telegram data
    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    username = Column(String, nullable=True)
    # Our data
    try_count = Column(Integer, default=5)
    started_at = Column(DATETIME, nullable=True)
    finished_at = Column(DATETIME, nullable=True)
    is_winner = Column(Boolean, nullable=True)

    def __repr__(self):
        return f"""<User (id={self.id}
            first_name={self.first_name}
            last_name={self.last_name}
            username={self.username}
            try_count={self.try_count}
            started_at={self.started_at}
            finished_at={self.finished_at}
            is_winner={self.is_winner})>"""


def get_or_create(session, model, **kwargs):
    instance = session.query(model).get(kwargs["id"])
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
        return instance


# Initialize database and create tables
engine = create_engine("sqlite:///data.db", echo=True)
Base.metadata.create_all(engine)
Session = sessionmaker(engine)
