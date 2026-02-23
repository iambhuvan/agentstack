import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

from app.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def utcnow():
    return datetime.now(timezone.utc)


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(64), nullable=False, index=True)
    model = Column(String(128), nullable=False, index=True)
    display_name = Column(String(256), nullable=False)
    api_key_hash = Column(String(256), nullable=False, unique=True)
    reputation_score = Column(Float, default=0.0)
    total_contributions = Column(Integer, default=0)
    total_verifications = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    solutions = relationship("Solution", back_populates="contributor")
    verifications = relationship("Verification", back_populates="agent")


class Bug(Base):
    __tablename__ = "bugs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    structural_hash = Column(String(128), nullable=False, index=True)
    embedding = Column(Vector(384))
    error_pattern = Column(Text, nullable=False)
    error_type = Column(String(256), nullable=False, index=True)
    environment = Column(JSONB, default=dict)
    tags = Column(JSONB, default=list)
    solution_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    solutions = relationship("Solution", back_populates="bug", cascade="all, delete-orphan")
    failed_approaches = relationship("FailedApproach", back_populates="bug", cascade="all, delete-orphan")


class Solution(Base):
    __tablename__ = "solutions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bug_id = Column(UUID(as_uuid=True), ForeignKey("bugs.id"), nullable=False, index=True)
    contributed_by = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)
    approach_name = Column(String(512), nullable=False)
    steps = Column(JSONB, nullable=False)
    diff_patch = Column(Text)
    success_rate = Column(Float, default=0.0)
    total_attempts = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    avg_resolution_ms = Column(Integer, default=0)
    version_constraints = Column(JSONB, default=dict)
    warnings = Column(JSONB, default=list)
    source = Column(String(32), default="agent_verified")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    last_verified = Column(DateTime(timezone=True), default=utcnow)

    bug = relationship("Bug", back_populates="solutions")
    contributor = relationship("Agent", back_populates="solutions")
    verifications = relationship("Verification", back_populates="solution", cascade="all, delete-orphan")


class FailedApproach(Base):
    __tablename__ = "failed_approaches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bug_id = Column(UUID(as_uuid=True), ForeignKey("bugs.id"), nullable=False, index=True)
    approach_name = Column(String(512), nullable=False)
    command_or_action = Column(Text)
    failure_rate = Column(Float, default=0.0)
    common_followup_error = Column(Text)
    reason = Column(Text)

    bug = relationship("Bug", back_populates="failed_approaches")


class Verification(Base):
    __tablename__ = "verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    solution_id = Column(UUID(as_uuid=True), ForeignKey("solutions.id"), nullable=False, index=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True)
    success = Column(Boolean, nullable=False)
    context = Column(JSONB, default=dict)
    resolution_time_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    solution = relationship("Solution", back_populates="verifications")
    agent = relationship("Agent", back_populates="verifications")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
