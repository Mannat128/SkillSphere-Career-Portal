import logging
import threading
import warnings
from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from ultralytics import YOLO


logger = logging.getLogger(__name__)

MODEL_NAME = "yolo26n.pt"

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


def get_model() -> YOLO:
    """Load the YOLO model once and reuse it safely."""
    global _model

    with _model_lock:
        if _model is None:
            logger.info("Loading computer vision model: %s", MODEL_NAME)
            try:
                _model = YOLO(MODEL_NAME)
                logger.info("YOLO model loaded successfully.")
            except Exception as exc:
                logger.exception("Unable to load YOLO model.")
                raise RuntimeError(
                    "Computer vision model could not be loaded."
                ) from exc

    return _model


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
    model = get_model()

    try:
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
        logger.exception("YOLO frame inference failed.")
        raise RuntimeError(
            "Computer vision frame processing failed."
        ) from exc
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
        "detections": detections,
        "frame_processed": True,
    }
