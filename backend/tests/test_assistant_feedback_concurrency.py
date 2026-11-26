"""Database-enforced guest feedback deduplication under concurrent writes."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import tempfile
from threading import Barrier

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.sphera import AssistantFeedback


def test_concurrent_guest_feedback_submissions_allow_exactly_one():
    temp_dir = tempfile.TemporaryDirectory(prefix="assistant-feedback-")
    engine = create_engine(
        f"sqlite:///{Path(temp_dir.name) / 'feedback-concurrency.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    barrier = Barrier(2)
    shared = {
        "message_id": 82001,
        "user_id": None,
        "guest_session_hash": "a" * 64,
        "user_role": "visitor",
        "rating": "helpful",
        "match_score": 1.0,
        "status": "CLOSED",
        "priority": "LOW",
        "created_at": datetime.utcnow(),
    }

    def submit():
        with factory() as db:
            barrier.wait(timeout=5)
            # Serialize SQLite writers while both independent requests race to
            # insert the same actor/message key. MySQL/TiDB enforce the same
            # unique-key invariant at the index; this fixture is SQLite only.
            db.execute(text("BEGIN IMMEDIATE"))
            db.add(AssistantFeedback(**shared))
            try:
                db.commit()
                return "inserted"
            except IntegrityError:
                db.rollback()
                return "duplicate"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: submit(), range(2)))
        assert sorted(outcomes) == ["duplicate", "inserted"]
        with factory() as db:
            assert db.query(AssistantFeedback).count() == 1
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
        temp_dir.cleanup()
