import cv2
import numpy as np
from pathlib import Path
SFACE_COSINE_THRESHOLD = 0.363


class FacePipeline:
    def __init__(self,
                 score_threshold=0.9):
        BASE_DIR = Path(__file__).resolve().parent
        MODELS_DIR = BASE_DIR / "models"
        YUNET_MODEL_PATH = MODELS_DIR / "face_detection_yunet.onnx"
        SFACE_MODEL_PATH = MODELS_DIR / "face_recognition_sface.onnx"
        self.detector = cv2.FaceDetectorYN_create(
            YUNET_MODEL_PATH, "", (320, 320), score_threshold, 0.3, 5000
        )
        self.recognizer = cv2.FaceRecognizerSF_create(SFACE_MODEL_PATH, "")
        

    def detect_faces(self, frame):
        h, w = frame.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame)
        return faces

    def get_embedding(self, frame, face_row):
        aligned = self.recognizer.alignCrop(frame, face_row)
        embedding = self.recognizer.feature(aligned)
        return embedding.flatten()

    def match(self, embedding, known_employees, threshold=SFACE_COSINE_THRESHOLD):
        best_match, best_score = None, -1.0
        for emp in known_employees:
            score = self.recognizer.match(
                embedding.reshape(1, -1).astype(np.float32),
                emp["embedding"].reshape(1, -1).astype(np.float32),
                cv2.FaceRecognizerSF_FR_COSINE,
            )
            if score > best_score:
                best_score, best_match = score, emp
        if best_score >= threshold:
            return best_match, best_score
        return None, best_score


def landmark_geometry(face_row):
    """
    Extracts a depth-sensitive geometric signature from YuNet's 5-point
    landmarks (right eye, left eye, nose tip, right mouth corner, left
    mouth corner). The ratio of eye-width to mouth-width is INVARIANT
    under any rigid 2D transform (rotation, scaling, translation) of a
    flat image -- so tilting a photo/phone can't change it. A real 3D
    face turning DOES change this ratio, because perspective
    foreshortens the far side of the face more than the near side.
    Comparing this ratio between a "look straight" and "turn your head"
    capture is what the two-step liveness challenge relies on.
    """
    re = face_row[4:6]
    le = face_row[6:8]
    nose = face_row[8:10]
    rm = face_row[10:12]
    lm = face_row[12:14]

    eye_dist = float(np.linalg.norm(re - le))
    mouth_dist = float(np.linalg.norm(rm - lm))
    ratio = eye_dist / mouth_dist if mouth_dist > 0 else 0.0

    eye_mid = (re + le) / 2
    nose_asym = float((nose[0] - eye_mid[0]) / eye_dist) if eye_dist > 0 else 0.0

    return {"eye_dist": eye_dist, "mouth_dist": mouth_dist, "ratio": ratio, "nose_asym": nose_asym}


def check_head_turn_challenge(face_row_a, face_row_b, min_ratio_delta=0.02, min_box_shift_fraction=0.03):
    """
    Compares two captures (frame A: look straight, frame B: turn head)
    and returns (passed, details). Requires BOTH:
      1. The eye/mouth ratio changed by at least min_ratio_delta -- a
         flat photo tilted between shots would show ~0 change here.
      2. The face box moved horizontally by at least min_box_shift_fraction
         of the face's own width -- confirms the person really attempted
         the turn (not two near-identical frames). Using a fraction of
         face width (rather than a fixed pixel count) keeps this
         threshold consistent whether the person is close to or far
         from the camera, or at any camera resolution.
    """
    geo_a = landmark_geometry(face_row_a)
    geo_b = landmark_geometry(face_row_b)
    ratio_delta = abs(geo_a["ratio"] - geo_b["ratio"])

    face_width = max(float(face_row_a[2]), 1.0)
    box_shift_px = float(abs(face_row_a[0] - face_row_b[0]))
    box_shift_fraction = box_shift_px / face_width

    passed = (ratio_delta >= min_ratio_delta) and (box_shift_fraction >= min_box_shift_fraction)
    details = {
        "geo_a": geo_a, "geo_b": geo_b,
        "ratio_delta": ratio_delta,
        "box_shift_px": box_shift_px,
        "box_shift_fraction": box_shift_fraction,
        "passed": passed,
    }
    return passed, details


def _crop_face_square(frame, box, bbox_inc=1.5):
    real_h, real_w = frame.shape[:2]
    x, y, w, h = box
    l = max(w, h) * bbox_inc
    xc, yc = x + w / 2, y + h / 2
    x1 = int(max(xc - l / 2, 0))
    y1 = int(max(yc - l / 2, 0))
    x2 = int(min(xc + l / 2, real_w))
    y2 = int(min(yc + l / 2, real_h))
    return frame[y1:y2, x1:x2]


class _TextureLivenessHeuristic:
    def score(self, face_crop):
        if face_crop.size == 0:
            return 0.0
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        sat_std = hsv[:, :, 1].std()
        bright_ratio = float(np.mean(gray > 240))
        score = 0.0
        score += min(lap_var / 150.0, 1.0) * 0.5
        score += min(sat_std / 50.0, 1.0) * 0.3
        score += (1.0 - min(bright_ratio * 10, 1.0)) * 0.2
        return score


class LivenessChecker:
    def __init__(self,
                 model_path="models/AntiSpoofing_bin_1.5_128.onnx",
                 deep_threshold=0.5,
                 combined_threshold=0.35):
        self.model_path = model_path
        self.deep_threshold = deep_threshold
        self.combined_threshold = combined_threshold
        self.heuristic = _TextureLivenessHeuristic()
        try:
            self.net = cv2.dnn.readNetFromONNX(model_path)
            self.model_loaded = True
        except cv2.error:
            self.model_loaded = False
            print(f"Warning: could not load liveness model at {model_path}. Falling back to texture heuristic only.")

    def is_live(self, frame, face_row, debug=False):
        x, y, w, h = face_row[:4].astype(int)
        crop = _crop_face_square(frame, (x, y, w, h), bbox_inc=1.5)
        if crop.size == 0:
            return False, 0.0, {}

        heuristic_score = self.heuristic.score(crop)

        if not self.model_loaded:
            return heuristic_score >= 0.45, heuristic_score, {"mode": "heuristic_only", "heuristic": heuristic_score}

        blob = cv2.dnn.blobFromImage(
            cv2.resize(crop, (128, 128)),
            1.0 / 255.0, (128, 128), (0, 0, 0), swapRB=True, crop=False
        )
        self.net.setInput(blob)
        raw_out = self.net.forward()

        logits = raw_out.flatten().astype(np.float64)
        exp = np.exp(logits - np.max(logits))
        probs = exp / exp.sum()

        # CALIBRATED against real test data on this exact model export:
        # index 0 = "real", index 1 = "spoof" (the reverse of the usual
        # convention). Confirmed by testing: a phone-photo spoof scored
        # 0.9995 on index 1 and 0.0005 on index 0, so index 0 is clearly
        # the "real" class here.
        deep_score_idx1 = float(probs[1]) if len(probs) > 1 else float(probs[0])
        deep_score_idx0 = float(probs[0])
        deep_score_real = deep_score_idx0

        combined = 0.7 * deep_score_real + 0.3 * heuristic_score
        is_live_face = combined >= self.combined_threshold

        details = {
            "raw_out": logits.tolist(),
            "softmaxed": probs.tolist(),
            "heuristic": heuristic_score,
            "deep_score_used_idx0_real": deep_score_idx0,
            "deep_score_alt_idx1": deep_score_idx1,
            "combined": combined,
        }
        if debug:
            print(f"[liveness debug] {details}")

        return is_live_face, combined, details


def detect_mask(frame, face_row, threshold=0.5):
    """
    Lightweight heuristic mask flag -- not a trained model, just two cheap
    signals on the region YuNet already localized:
      1. Texture uniformity: mask fabric tends to be flatter than a real
         mouth/chin (lips, teeth, shadows all add texture variance).
      2. Color difference from visible forehead/nose-bridge skin: many
         masks (surgical blue/white, colored cloth) differ noticeably in
         hue from the wearer's own skin tone.
    This is meant as a soft FLAG for the attendance log, not a gate --
    it will occasionally be wrong (e.g. very skin-toned masks, or facial
    hair/shadow patterns that mimic mask uniformity), which is fine given
    it doesn't block check-in.
    """
    x, y, w, h = face_row[:4].astype(int)
    nose = face_row[8:10]
    re, le = face_row[4:6], face_row[6:8]

    ny = int(nose[1])
    y2 = min(y + h, frame.shape[0])
    x1, x2 = max(x, 0), min(x + w, frame.shape[1])
    lower = frame[max(ny, 0):y2, x1:x2]

    ey = int(min(re[1], le[1]))
    upper = frame[max(y, 0):max(ey, y + 1), x1:x2]

    if lower.size == 0 or upper.size == 0:
        return False, 0.0

    lower_gray = cv2.cvtColor(lower, cv2.COLOR_BGR2GRAY)
    lower_hsv = cv2.cvtColor(lower, cv2.COLOR_BGR2HSV)
    upper_hsv = cv2.cvtColor(upper, cv2.COLOR_BGR2HSV)

    texture_std = float(lower_gray.std())
    uniformity_score = max(0.0, 1.0 - min(texture_std / 45.0, 1.0))

    lower_hue = float(np.median(lower_hsv[:, :, 0]))
    upper_hue = float(np.median(upper_hsv[:, :, 0]))
    hue_diff = min(abs(lower_hue - upper_hue) / 90.0, 1.0)

    mask_score = 0.6 * uniformity_score + 0.4 * hue_diff
    return mask_score >= threshold, mask_score
