
"""Authenticated local facial-expression analysis endpoint."""

import base64
import binascii

import cv2
import numpy as np
from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required

bp = Blueprint("face_expression", __name__, url_prefix="/api/face-expression")

MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_IMAGE_DIMENSION = 1920


@bp.post("")
@login_required
def analyze():
    if not request.is_json:
        return jsonify(error="Expected a JSON request."), 415

    payload = request.get_json(silent=True) or {}
    image_data = payload.get("image")

    if not isinstance(image_data, str):
        return jsonify(error="An image is required."), 400

    # Accept a base64 data URL or raw base64 string.
    if image_data.startswith("data:"):
        header, separator, image_data = image_data.partition(",")
        if not separator or not header.startswith("data:image/"):
            return jsonify(error="Invalid image data URL."), 400

    if len(image_data) > (MAX_IMAGE_BYTES * 4 // 3 + 16):
        return jsonify(error="Image is too large."), 413

    try:
        image_bytes = base64.b64decode(image_data, validate=True)
    except (binascii.Error, ValueError):
        return jsonify(error="Invalid image encoding."), 400

    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        return jsonify(error="Image is empty or too large."), 413

    encoded = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

    if frame is None:
        return jsonify(error="Could not read the image."), 400

    height, width = frame.shape[:2]
    if (
        width < 1
        or height < 1
        or width > MAX_IMAGE_DIMENSION
        or height > MAX_IMAGE_DIMENSION
    ):
        return jsonify(error="Image dimensions are not supported."), 400

    try:
        analyzer = current_app.extensions.get("aura_face_expression")
        if analyzer is None:
            from modules.face_expression import FaceExpressionAnalyzer

            analyzer = FaceExpressionAnalyzer()
            current_app.extensions["aura_face_expression"] = analyzer

        result = analyzer.analyze_frame(frame)
        return jsonify(result), 200

    except FileNotFoundError:
        current_app.logger.exception("AURA facial-expression model files are missing.")
        return jsonify(error="Facial-expression models are not available."), 503
    except Exception:
        current_app.logger.exception("Facial-expression analysis failed.")
        return jsonify(error="Facial-expression analysis failed."), 500
