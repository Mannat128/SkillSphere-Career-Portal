import logging
import threading
import time
import warnings
from io import BytesIO
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from ultralytics import YOLO


logger = logging.getLogger(__name__)

MODEL_NAME = "yolo26n.pt"
FACE_MODEL_PATH = Path(__file__).parent / "data" / "face_detection_yunet_2026may.onnx"

PERSON_CLASS_ID = 0
CELL_PHONE_CLASS_ID = 67

PHONE_CONFIDENCE_THRESHOLD = 0.55
PERSON_CONFIDENCE_THRESHOLD = 0.55

MAX_FRAME_SIZE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_WIDTH = 8192
MAX_IMAGE_HEIGHT = 8192
MAX_IMAGE_PIXELS = 16_000_000

_model = None
_model_lock = threading.Lock()
_model_retry_after = 0.0
MODEL_LOAD_RETRY_BACKOFF_SECONDS = 60
_face_detector = None
_face_lock = threading.Lock()


def get_model() -> YOLO:
    """Load the YOLO model once and reuse it safely."""
    global _model, _model_retry_after

    with _model_lock:
        if _model is None:
            now = time.monotonic()
            if now < _model_retry_after:
                raise RuntimeError("Computer vision model is temporarily unavailable.")
            try:
                logger.info("Loading computer vision model: %s", MODEL_NAME)
                _model = YOLO(MODEL_NAME)
                _model_retry_after = 0.0
                logger.info("YOLO model loaded successfully.")
            except Exception as exc:
                _model_retry_after = now + MODEL_LOAD_RETRY_BACKOFF_SECONDS
                logger.error(
                    "Unable to load YOLO model; error_type=%s",
                    type(exc).__name__,
                )
                raise RuntimeError(
                    "Computer vision model could not be loaded."
                ) from exc

    return _model


def get_face_detector():
    """Load the local YuNet face detector once; no runtime download is used."""
    global _face_detector

    with _face_lock:
        if _face_detector is None:
            if not FACE_MODEL_PATH.is_file():
                raise RuntimeError("Local face detection model is unavailable.")
            try:
                _face_detector = cv2.FaceDetectorYN.create(
                    str(FACE_MODEL_PATH),
                    "",
                    (320, 320),
                    0.85,
                    0.3,
                    5000,
                )
            except Exception as exc:
                logger.exception("Unable to initialize local face detector.")
                raise RuntimeError("Face detector could not be initialized.") from exc
            if _face_detector is None:
                raise RuntimeError("Face detector could not be initialized.")
    return _face_detector


def is_head_turn_signal(face_row: np.ndarray) -> bool:
    """Estimate a pronounced head turn from YuNet eye/nose landmarks.

    This is an approximate head-orientation review signal, not eye-gaze
    recognition. Small or low-confidence faces are intentionally ignored.
    """
    row = np.asarray(face_row, dtype=np.float32).reshape(-1)
    if row.size < 15 or not np.isfinite(row[:15]).all():
        return False

    box_width = float(row[2])
    confidence = float(row[14])
    if box_width < 80 or confidence < 0.85:
        return False

    eye_x = sorted((float(row[4]), float(row[6])))
    eye_distance = eye_x[1] - eye_x[0]
    if eye_distance < max(12.0, box_width * 0.18):
        # Eye landmarks are too close to support a stable yaw estimate.
        return False

    eye_midpoint = (eye_x[0] + eye_x[1]) / 2.0
    normalized_nose_offset = abs(float(row[8]) - eye_midpoint) / eye_distance
    return normalized_nose_offset >= 0.35


def detect_face_signals(frame_rgb: np.ndarray) -> dict[str, Any]:
    """Detect faces and estimate sustained head-turn review signals in-memory."""
    if frame_rgb.ndim != 3 or frame_rgb.shape[2] != 3 or frame_rgb.size == 0:
        raise ValueError("Invalid image dimensions.")

    height, width = frame_rgb.shape[:2]
    scale = min(1.0, 640.0 / max(width, height))
    if scale < 1.0:
        frame_rgb = cv2.resize(
            frame_rgb,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )

    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    detector = get_face_detector()
    try:
        with _face_lock:
            detector.setInputSize((frame_bgr.shape[1], frame_bgr.shape[0]))
            _score, faces = detector.detect(frame_bgr)
    except Exception as exc:
        logger.exception("YuNet face inference failed.")
        raise RuntimeError("Face detection failed.") from exc
    finally:
        del frame_bgr

    if faces is None or len(faces) == 0:
        return {
            "face_detected": False,
            "face_count": 0,
            "looking_away_detected": False,
        }

    # Use the largest/highest-confidence detected face as the candidate signal.
    face_rows = sorted(
        faces,
        key=lambda row: (float(row[2]) * float(row[3]), float(row[14])),
        reverse=True,
    )
    primary_face = face_rows[0]
    return {
        "face_detected": True,
        "face_count": len(face_rows),
        "looking_away_detected": is_head_turn_signal(primary_face),
    }


def decode_frame(image_bytes: bytes) -> np.ndarray:
    """Decode a validated image into an RGB NumPy array."""
    if not image_bytes:
        raise ValueError("The uploaded frame is empty.")

    if len(image_bytes) > MAX_FRAME_SIZE_BYTES:
        raise ValueError("Frame size exceeds the 5 MB limit.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(BytesIO(image_bytes)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError(
                        "Only JPEG, PNG and WebP images are supported."
                    )

                width, height = image.size
                if width <= 0 or height <= 0:
                    raise ValueError("Invalid image dimensions.")

                if (
                    width > MAX_IMAGE_WIDTH
                    or height > MAX_IMAGE_HEIGHT
                    or width * height > MAX_IMAGE_PIXELS
                ):
                    raise ValueError(
                        "Image dimensions exceed the allowed limit."
                    )

                image.verify()

            # Reopen after verify because verify() invalidates the image.
            with Image.open(BytesIO(image_bytes)) as image:
                image = ImageOps.exif_transpose(image)
                image = image.convert("RGB")
                frame = np.array(image, dtype=np.uint8, copy=True)

    except ValueError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValueError(
            "Invalid, unsafe or unsupported image frame."
        ) from exc

    if frame.ndim != 3 or frame.shape[2] != 3 or frame.size == 0:
        raise ValueError("Invalid image dimensions.")

    return frame


def detect_objects(image_bytes: bytes) -> dict[str, Any]:
    """Detect mobile phones and people in one webcam frame.

    Only detection metadata is returned. Original image data is not saved.
    """
    frame = decode_frame(image_bytes)
    face_signals = detect_face_signals(frame)
    try:
        model = get_model()
        # Serialize inference because a shared YOLO model instance is reused.
        with _model_lock:
            results = model.predict(
                source=frame,
                imgsz=640,
                conf=0.25,
                device="cpu",
                verbose=False,
            )
    except Exception as exc:
        # Preserve the independent face signals while making degraded object
        # monitoring explicit. Never claim that no phone/person was found.
        logger.warning(
            "YOLO object monitoring unavailable; error_type=%s",
            type(exc).__name__,
        )
        return {
            "phone_detected": None,
            "person_count": None,
            "multiple_people_detected": None,
            "object_detection_available": False,
            **face_signals,
            "detections": [],
            "frame_processed": True,
        }
    finally:
        del frame

    detections = []
    person_count = 0
    phone_detected = False

    for result in results:
        if result.boxes is None:
            continue

        for box in result.boxes:
            class_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())

            if class_id == PERSON_CLASS_ID:
                if confidence < PERSON_CONFIDENCE_THRESHOLD:
                    continue
                person_count += 1
                label = "person"

            elif class_id == CELL_PHONE_CLASS_ID:
                if confidence < PHONE_CONFIDENCE_THRESHOLD:
                    continue
                phone_detected = True
                # Keep this label consistent with the router's confidence lookup.
                label = "cell phone"

            else:
                continue

            coordinates = box.xyxy[0].tolist()
            detections.append({
                "label": label,
                "confidence": round(confidence, 3),
                "bounding_box": [
                    round(float(value), 2) for value in coordinates
                ],
            })

    return {
        "phone_detected": phone_detected,
        "person_count": person_count,
        "multiple_people_detected": person_count > 1,
        "object_detection_available": True,
        **face_signals,
        "detections": detections,
        "frame_processed": True,
    }
