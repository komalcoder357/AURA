
"""Local facial-expression estimation for AURA.
Frames are processed locally and are not saved by this module.
"""

from pathlib import Path
import threading

import cv2
import numpy as np


MODEL_DIR = (
    Path(__file__).resolve().parent.parent
    / "models"
    / "face_expression"
)

FACE_MODEL = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
EXPRESSION_MODEL = (
    MODEL_DIR
    / "facial_expression_recognition_mobilefacenet_2022july_int8.onnx"
)

LABELS = [
    "angry",
    "disgust",
    "fearful",
    "happy",
    "neutral",
    "sad",
    "surprised",
]


class FaceExpressionAnalyzer:
    """Estimate visible facial-expression categories using local ONNX models."""

    def __init__(self):
        missing = [
            str(path)
            for path in (FACE_MODEL, EXPRESSION_MODEL)
            if not path.is_file()
        ]
        if missing:
            raise FileNotFoundError(
                "Required model file(s) missing: " + ", ".join(missing)
            )

        self._lock = threading.Lock()

        self._detector = cv2.FaceDetectorYN.create(
            str(FACE_MODEL),
            "",
            (320, 320),
            0.5,
            0.3,
            5000,
        )

        self._expression_net = cv2.dnn.readNetFromONNX(
            str(EXPRESSION_MODEL)
        )

    def analyze_frame(self, frame):
        """Analyze one BGR frame; return expression estimates."""
        if not isinstance(frame, np.ndarray):
            raise ValueError("A valid image frame is required.")

        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("Expected a three-channel color image.")

        height, width = frame.shape[:2]
        if height < 1 or width < 1:
            raise ValueError("The image frame is empty.")

        with self._lock:
            self._detector.setInputSize((width, height))
            _, faces = self._detector.detect(frame)

            if faces is None or len(faces) == 0:
                return {
                    "face_detected": False,
                    "expressions": [],
                    "message": "No face detected.",
                }

            results = []

            for face in faces[:3]:
                x, y, w, h = [
                    int(round(value)) for value in face[:4]
                ]

                landmarks = face[4:14].reshape(5, 2).astype(
                    np.float32
                )

                reference = np.array(
                    [
                        [38.2946, 51.6963],
                        [73.5318, 51.5014],
                        [56.0252, 71.7366],
                        [41.5493, 92.3655],
                        [70.7299, 92.2041],
                    ],
                    dtype=np.float32,
                )

                transform, _ = cv2.estimateAffinePartial2D(
                    landmarks,
                    reference,
                    method=cv2.LMEDS,
                )

                if transform is None:
                    continue

                aligned = cv2.warpAffine(
                    frame,
                    transform,
                    (112, 112),
                    flags=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT,
                )

                rgb = cv2.cvtColor(aligned, cv2.COLOR_BGR2RGB)
                normalized = rgb.astype(np.float32) / 255.0
                normalized = (normalized - 0.5) / 0.5
                blob = cv2.dnn.blobFromImage(normalized)

                self._expression_net.setInput(blob, "data")
                raw_scores = self._expression_net.forward("label")[0]
                raw_scores = np.asarray(raw_scores, dtype=np.float64).reshape(-1)

                if len(raw_scores) != len(LABELS):
                    continue

                # Convert model scores to a normalized distribution.
                # This is NOT a calibrated probability of a person's true emotion.
                shifted = raw_scores - np.max(raw_scores)
                exp_scores = np.exp(shifted)
                probabilities = exp_scores / np.sum(exp_scores)

                index = int(np.argmax(probabilities))

                results.append(
                    {
                        "expression": LABELS[index],
                        "model_score": round(
                            float(probabilities[index]), 4
                        ),
                        "face_box": {
                            "x": max(0, x),
                            "y": max(0, y),
                            "width": max(0, w),
                            "height": max(0, h),
                        },
                    }
                )

            return {
                "face_detected": bool(results),
                "expressions": results,
                "message": (
                    "Expression estimate available. It is not a diagnosis "
                    "or a reliable measure of a person's inner emotional state."
                    if results
                    else "A face was found, but alignment failed."
                ),
            }
