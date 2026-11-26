import numpy as np
from io import BytesIO
import asyncio
from PIL import Image
from starlette.datastructures import Headers, UploadFile

from app.services import computer_vision_service as vision
from app.routers import computer_vision as cv_router


def test_face_signal_marks_a_blank_frame_as_no_face(monkeypatch):
    class BlankDetector:
        def setInputSize(self, _size):
            return None

        def detect(self, _frame):
            return 1.0, None

    monkeypatch.setattr(
        "app.services.computer_vision_service.get_face_detector",
        lambda: BlankDetector(),
    )
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    assert vision.detect_face_signals(frame) == {
        "face_detected": False,
        "face_count": 0,
        "looking_away_detected": False,
    }


def test_head_turn_signal_uses_normalized_eye_and_nose_landmarks():
    frontal_face = np.array(
        [100, 40, 120, 140, 135, 90, 185, 90, 160, 125, 140, 155, 180, 155, 0.99],
        dtype=np.float32,
    )
    turned_face = frontal_face.copy()
    turned_face[8] = 195

    assert vision.is_head_turn_signal(frontal_face) is False
    assert vision.is_head_turn_signal(turned_face) is True


def test_head_turn_signal_ignores_small_or_low_confidence_faces():
    small_face = np.array(
        [100, 40, 50, 60, 110, 60, 130, 60, 125, 80, 115, 95, 130, 95, 0.99],
        dtype=np.float32,
    )
    low_confidence_face = np.array(
        [100, 40, 120, 140, 135, 90, 185, 90, 195, 125, 140, 155, 180, 155, 0.5],
        dtype=np.float32,
    )

    assert vision.is_head_turn_signal(small_face) is False
    assert vision.is_head_turn_signal(low_confidence_face) is False


def test_yolo_failure_does_not_claim_no_phone_or_people(monkeypatch):
    payload = BytesIO()
    Image.new("RGB", (32, 32), color="black").save(payload, format="PNG")
    payload.seek(0)
    monkeypatch.setattr(
        vision,
        "detect_face_signals",
        lambda _frame: {
            "face_detected": False,
            "face_count": 0,
            "looking_away_detected": False,
        },
    )

    def unavailable_model():
        raise RuntimeError("Synthetic model unavailable")

    monkeypatch.setattr(vision, "get_model", unavailable_model)
    result = vision.detect_objects(payload.getvalue())

    assert result["object_detection_available"] is False
    assert result["phone_detected"] is None
    assert result["multiple_people_detected"] is None
    assert result["face_detected"] is False


def test_frame_api_returns_face_signals_when_yolo_is_unavailable(monkeypatch):
    payload = BytesIO()
    Image.new("RGB", (32, 32), color="black").save(payload, format="PNG")
    payload.seek(0)
    session = type(
        "Session",
        (),
        {
            "warning_count": 0,
            "is_flagged_for_review": False,
            "last_violation_at": None,
        },
    )()
    assignment = type("Assignment", (), {"id": 14})()
    candidate = type("Candidate", (), {"id": 9})()
    db = type("Database", (), {"expire": lambda *_args: None})()

    monkeypatch.setattr(cv_router, "get_candidate_assignment", lambda *_args: assignment)
    monkeypatch.setattr(cv_router, "get_active_attempt", lambda *_args: object())
    monkeypatch.setattr(cv_router, "get_active_proctoring_session", lambda *_args: session)
    monkeypatch.setattr(
        cv_router,
        "detect_objects",
        lambda _bytes: {
            "phone_detected": None,
            "person_count": None,
            "multiple_people_detected": None,
            "object_detection_available": False,
            "face_detected": False,
            "face_count": 0,
            "looking_away_detected": False,
            "detections": [],
            "frame_processed": True,
        },
    )
    upload = UploadFile(
        file=payload,
        filename="synthetic.png",
        headers=Headers({"content-type": "image/png"}),
    )

    result = asyncio.run(
        cv_router.analyze_proctoring_frame(
            assignment_id=14,
            file=upload,
            candidate=candidate,
            db=db,
        )
    )

    assert result["face_detected"] is False
    assert result["looking_away_detected"] is False
    assert result["object_detection_available"] is False
    assert result["phone_detected"] is None


def test_frame_api_persists_detected_phone_violation(monkeypatch):
    payload = BytesIO()
    Image.new("RGB", (32, 32), color="black").save(payload, format="PNG")
    payload.seek(0)
    session = type(
        "Session",
        (),
        {
            "id": 23,
            "warning_count": 0,
            "is_flagged_for_review": False,
            "last_violation_at": None,
            "session_status": "RECORDING",
            "consent_given": True,
            "camera_permission_granted": True,
        },
    )()
    candidate = type("Candidate", (), {"id": 9})()
    added = []

    class Database:
        def expire(self, _session):
            return None

        def add(self, record):
            added.append(record)

        def commit(self):
            return None

    db = Database()
    monkeypatch.setattr(cv_router, "get_candidate_assignment", lambda *_args: None)
    monkeypatch.setattr(cv_router, "get_active_attempt", lambda *_args: object())
    monkeypatch.setattr(cv_router, "get_active_proctoring_session", lambda *_args: session)
    monkeypatch.setattr(
        cv_router,
        "detect_objects",
        lambda _bytes: {
            "phone_detected": True,
            "person_count": 1,
            "multiple_people_detected": False,
            "object_detection_available": True,
            "face_detected": True,
            "face_count": 1,
            "looking_away_detected": False,
            "detections": [{"label": "cell phone", "confidence": 0.91}],
            "frame_processed": True,
        },
    )
    upload = UploadFile(
        file=payload,
        filename="synthetic.png",
        headers=Headers({"content-type": "image/png"}),
    )

    result = asyncio.run(
        cv_router.analyze_proctoring_frame(
            assignment_id=14,
            file=upload,
            candidate=candidate,
            db=db,
        )
    )

    assert result["warning_recorded"] is True
    assert len(added) == 1
    assert added[0].assignment_id == 14
    assert added[0].candidate_id == 9
    assert added[0].proctoring_session_id == 23
    assert added[0].violation_type == "AI_PHONE_DETECTED"
    assert session.warning_count == 1
