"""
monitoring/detector.py
-----------------------
Core AI detection engine using MediaPipe FaceLandmarker (Tasks API) + OpenCV.

Accurately and separately calculates:
  1. Face Detection (Face presence, single vs multiple faces)
  2. Eye Gaze Direction (Iris position relative to eye socket center)
  3. Head Pose Orientation (Yaw & Pitch from 3D facial feature geometry)

Returns a structured dictionary:
  {
    "face_detected": bool,
    "face_count": int,
    "gaze_direction": "CENTER" | "LEFT" | "RIGHT" | "UP" | "DOWN",
    "gaze_label": "Looking at Screen" | "Looking Left" | "Looking Right" | "Looking Up" | "Looking Down",
    "head_direction": "CENTER" | "LEFT" | "RIGHT" | "UP" | "DOWN",
    "head_label": "Center" | "Turned Left" | "Turned Right" | "Tilted Up" | "Tilted Down",
    "is_suspicious": bool,
    "violation": str | None,
    "details": dict
  }
"""

import base64
import io
import logging
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from PIL import Image

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Model setup — download face_landmarker.task if not cached
# ------------------------------------------------------------------
_MODEL_DIR  = Path(__file__).parent / "models"
_MODEL_PATH = _MODEL_DIR / "face_landmarker.task"
_MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/latest/face_landmarker.task"
)


def _ensure_model() -> str:
    """Download the face landmarker model on first run and return its path."""
    _MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if not _MODEL_PATH.exists():
        logger.info("Downloading face_landmarker.task model (~6 MB)…")
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        logger.info("Model downloaded to %s", _MODEL_PATH)
    return str(_MODEL_PATH)


# ------------------------------------------------------------------
# Build the FaceLandmarker once (reuse across requests)
# ------------------------------------------------------------------
def _build_landmarker() -> mp_vision.FaceLandmarker:
    model_path = _ensure_model()
    base_opts  = mp_python.BaseOptions(model_asset_path=model_path)
    # Using 0.30 confidence ensures continuous tracking when student moves
    # or tilts head slightly without falsely dropping face detection.
    options    = mp_vision.FaceLandmarkerOptions(
        base_options=base_opts,
        running_mode=mp_vision.RunningMode.IMAGE,
        num_faces=4,
        min_face_detection_confidence=0.30,
        min_face_presence_confidence=0.30,
        min_tracking_confidence=0.30,
        output_face_blendshapes=False,
        output_facial_transformation_matrixes=True,
    )
    return mp_vision.FaceLandmarker.create_from_options(options)


# Lazy-initialise so the model only loads when the first request arrives
_landmarker: Optional[mp_vision.FaceLandmarker] = None


def _get_landmarker() -> mp_vision.FaceLandmarker:
    global _landmarker
    if _landmarker is None:
        _landmarker = _build_landmarker()
    return _landmarker


# ------------------------------------------------------------------
# MediaPipe FaceLandmarker landmark indices (478-point mesh)
# ------------------------------------------------------------------
# Iris centers
_LEFT_IRIS_CENTER  = 468  # Eye on left side of image (person's anatomical right eye)
_RIGHT_IRIS_CENTER = 473  # Eye on right side of image (person's anatomical left eye)

# Left Eye in image (Person's right eye)
_LEFT_EYE_OUTER    = 33   # outer corner (temporal)
_LEFT_EYE_INNER    = 133  # inner corner (nasal / caruncle)
_LEFT_EYE_TOP      = 159  # upper eyelid
_LEFT_EYE_BOTTOM   = 145  # lower eyelid

# Right Eye in image (Person's left eye)
_RIGHT_EYE_INNER   = 362  # inner corner (nasal / caruncle)
_RIGHT_EYE_OUTER   = 263  # outer corner (temporal)
_RIGHT_EYE_TOP     = 386  # upper eyelid
_RIGHT_EYE_BOTTOM  = 374  # lower eyelid

# Facial feature landmarks for head pose
_NOSE_TIP          = 1
_CHIN              = 152
_FOREHEAD          = 10
_LEFT_EAR          = 234  # Left cheek / ear tragus
_RIGHT_EAR         = 454  # Right cheek / ear tragus


# ------------------------------------------------------------------
# Frame decoding
# ------------------------------------------------------------------
def _decode_base64_frame(b64_data: str) -> Optional[np.ndarray]:
    """
    Decode a base64-encoded JPEG/PNG string into an RGB numpy array.
    Returns None on failure.
    """
    try:
        if "," in b64_data:
            b64_data = b64_data.split(",", 1)[1]
        raw_bytes = base64.b64decode(b64_data)
        pil_img   = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        return np.array(pil_img)
    except Exception as exc:
        logger.warning("Frame decode failed: %s", exc)
        return None


# ------------------------------------------------------------------
# Gaze Direction Calculation (Iris offset from eye socket center)
# ------------------------------------------------------------------
def _calculate_gaze_offsets(lm) -> Tuple[float, float]:
    """
    Computes horizontal (dx) and vertical (dy) iris offsets relative to
    the geometric center of each eye socket.

    Returns:
      avg_dx: -1.0 (far left) to +1.0 (far right), 0.0 is center/screen
      avg_dy: -1.0 (far up) to +1.0 (far down), 0.0 is center/screen
    """
    # 1. Left eye in image (Person's right eye)
    # Corners: 33 (outer left in image) and 133 (inner right in image)
    e_l_x1 = lm[_LEFT_EYE_OUTER].x
    e_l_x2 = lm[_LEFT_EYE_INNER].x
    mid_l_x = (e_l_x1 + e_l_x2) / 2.0
    half_w_l = max(abs(e_l_x2 - e_l_x1) / 2.0, 1e-6)
    iris_l_x = lm[_LEFT_IRIS_CENTER].x
    # Offset normalized by half-width: positive = shifted right in image
    dx_left = (iris_l_x - mid_l_x) / half_w_l

    # Vertical
    e_l_y1 = lm[_LEFT_EYE_TOP].y
    e_l_y2 = lm[_LEFT_EYE_BOTTOM].y
    mid_l_y = (e_l_y1 + e_l_y2) / 2.0
    half_h_l = max(abs(e_l_y2 - e_l_y1) / 2.0, 1e-6)
    iris_l_y = lm[_LEFT_IRIS_CENTER].y
    dy_left = (iris_l_y - mid_l_y) / half_h_l

    # 2. Right eye in image (Person's left eye)
    # Corners: 362 (inner left in image) and 263 (outer right in image)
    e_r_x1 = lm[_RIGHT_EYE_INNER].x
    e_r_x2 = lm[_RIGHT_EYE_OUTER].x
    mid_r_x = (e_r_x1 + e_r_x2) / 2.0
    half_w_r = max(abs(e_r_x2 - e_r_x1) / 2.0, 1e-6)
    iris_r_x = lm[_RIGHT_IRIS_CENTER].x
    dx_right = (iris_r_x - mid_r_x) / half_w_r

    # Vertical
    e_r_y1 = lm[_RIGHT_EYE_TOP].y
    e_r_y2 = lm[_RIGHT_EYE_BOTTOM].y
    mid_r_y = (e_r_y1 + e_r_y2) / 2.0
    half_h_r = max(abs(e_r_y2 - e_r_y1) / 2.0, 1e-6)
    iris_r_y = lm[_RIGHT_IRIS_CENTER].y
    dy_right = (iris_r_y - mid_r_y) / half_h_r

    # Combine both eyes with safe clipping
    avg_dx = float(np.clip((dx_left + dx_right) / 2.0, -1.0, 1.0))
    avg_dy = float(np.clip((dy_left + dy_right) / 2.0, -1.0, 1.0))
    return avg_dx, avg_dy


# ------------------------------------------------------------------
# Head Pose Calculation (Yaw & Pitch in degrees)
# ------------------------------------------------------------------
def _calculate_head_pose_angles(lm, img_w: int = 640, img_h: int = 480) -> Tuple[float, float]:
    """
    Computes head yaw (horizontal rotation) and pitch (vertical tilt) in degrees.
    Positive yaw: turned right. Negative yaw: turned left.
    Positive pitch: tilted down. Negative pitch: tilted up.
    """
    nose_x = lm[_NOSE_TIP].x * img_w
    nose_y = lm[_NOSE_TIP].y * img_h

    left_ear_x  = lm[_LEFT_EAR].x  * img_w
    right_ear_x = lm[_RIGHT_EAR].x * img_w
    forehead_y  = lm[_FOREHEAD].y  * img_h
    chin_y      = lm[_CHIN].y      * img_h

    # Horizontal yaw: relative deviation of nose between ears
    ear_mid_x = (left_ear_x + right_ear_x) / 2.0
    ear_span  = abs(right_ear_x - left_ear_x)
    if ear_span > 1e-3:
        # Scale to approx ±45 degrees
        yaw = float(np.clip(((nose_x - ear_mid_x) / (ear_span * 0.5)) * 45.0, -90.0, 90.0))
    else:
        yaw = 0.0

    # Vertical pitch: relative deviation of nose between forehead and chin
    face_mid_y  = (forehead_y + chin_y) / 2.0
    face_height = abs(chin_y - forehead_y)
    if face_height > 1e-3:
        # Scale to approx ±45 degrees
        pitch = float(np.clip(((nose_y - face_mid_y) / (face_height * 0.5)) * 45.0, -90.0, 90.0))
    else:
        pitch = 0.0

    return yaw, pitch


# ------------------------------------------------------------------
# Main analysis function
# ------------------------------------------------------------------
def analyse_frame(
    b64_data: str,
    gaze_h_threshold:    float = 0.38,
    gaze_v_threshold:    float = 0.38,
    head_yaw_threshold:  float = 25.0,
    head_pitch_threshold: float = 20.0,
) -> dict:
    """
    Decodes a base64 webcam frame, runs MediaPipe FaceLandmarker,
    and returns independent assessments for Face, Gaze, and Head pose.
    """
    result = {
        "face_detected":   False,
        "face_count":      0,
        "gaze_direction":  "CENTER",
        "gaze_label":      "Looking at Screen",
        "head_direction":  "CENTER",
        "head_label":      "Center",
        "is_suspicious":   False,
        "violation":       None,
        "details":         {}
    }

    # 1. Decode frame
    rgb_frame = _decode_base64_frame(b64_data)
    if rgb_frame is None:
        result["violation"] = "FRAME_ERROR"
        result["error"] = "Frame decoding returned None"
        return result

    img_h, img_w = rgb_frame.shape[:2]

    # 2. Run FaceLandmarker
    try:
        landmarker = _get_landmarker()
        mp_image   = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        detection  = landmarker.detect(mp_image)
    except Exception as exc:
        logger.error("FaceLandmarker detection error: %s", exc)
        result["violation"] = "FRAME_ERROR"
        result["error"] = str(exc)
        return result

    face_count = len(detection.face_landmarks) if detection and detection.face_landmarks else 0
    result["face_count"] = face_count

    # 3. Check face presence violations
    if face_count == 0:
        result["face_detected"]  = False
        result["is_suspicious"]  = True
        result["violation"]      = "FACE_MISSING"
        result["gaze_label"]     = "Face Missing"
        result["head_label"]     = "Face Missing"
        return result

    if face_count > 1:
        result["face_detected"]  = True
        result["is_suspicious"]  = True
        result["violation"]      = "MULTIPLE_FACES"
        result["gaze_label"]     = "Multiple Faces"
        result["head_label"]     = "Multiple Faces"
        return result

    # 4. Face is detected (single face)
    result["face_detected"] = True
    lm = detection.face_landmarks[0]

    # 5. Calculate Eye Gaze Offsets
    dx, dy = _calculate_gaze_offsets(lm)

    # 6. Calculate Head Pose Angles
    yaw, pitch = _calculate_head_pose_angles(lm, img_w=img_w, img_h=img_h)

    result["details"] = {
        "gaze_dx":    round(dx, 3),
        "gaze_dy":    round(dy, 3),
        "head_yaw":   round(yaw, 1),
        "head_pitch": round(pitch, 1),
    }

    # 7. Classify Head Direction Independently
    if yaw > head_yaw_threshold:
        result["head_direction"] = "RIGHT"
        result["head_label"]     = "Turned Right"
    elif yaw < -head_yaw_threshold:
        result["head_direction"] = "LEFT"
        result["head_label"]     = "Turned Left"
    elif pitch > head_pitch_threshold:
        result["head_direction"] = "DOWN"
        result["head_label"]     = "Tilted Down"
    elif pitch < -head_pitch_threshold:
        result["head_direction"] = "UP"
        result["head_label"]     = "Tilted Up"
    else:
        result["head_direction"] = "CENTER"
        result["head_label"]     = "Center"

    # 8. Classify Eye Gaze Direction Independently
    if dx > gaze_h_threshold:
        result["gaze_direction"] = "RIGHT"
        result["gaze_label"]     = "Looking Right"
    elif dx < -gaze_h_threshold:
        result["gaze_direction"] = "LEFT"
        result["gaze_label"]     = "Looking Left"
    elif dy > gaze_v_threshold:
        result["gaze_direction"] = "DOWN"
        result["gaze_label"]     = "Looking Down"
    elif dy < -gaze_v_threshold:
        result["gaze_direction"] = "UP"
        result["gaze_label"]     = "Looking Up"
    else:
        result["gaze_direction"] = "CENTER"
        result["gaze_label"]     = "Looking at Screen"

    # 9. Intelligent Combination for Proctoring Decision
    # If head is turned significantly away from screen -> HEAD_TURNED
    if result["head_direction"] != "CENTER":
        result["is_suspicious"] = True
        result["violation"]     = "HEAD_TURNED"
    # Else if eyes are looking away from screen while head is forward -> GAZE violation
    elif result["gaze_direction"] == "LEFT":
        result["is_suspicious"] = True
        result["violation"]     = "GAZE_LEFT"
    elif result["gaze_direction"] == "RIGHT":
        result["is_suspicious"] = True
        result["violation"]     = "GAZE_RIGHT"
    elif result["gaze_direction"] == "UP":
        result["is_suspicious"] = True
        result["violation"]     = "GAZE_UP"
    elif result["gaze_direction"] == "DOWN":
        result["is_suspicious"] = True
        result["violation"]     = "GAZE_DOWN"
    else:
        # Both head and eyes are focused on the screen -> NORMAL
        result["is_suspicious"] = False
        result["violation"]     = None

    return result
