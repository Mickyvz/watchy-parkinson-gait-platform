from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_wtf import CSRFProtect
import requests
from datetime import datetime
import os
import json
import joblib
import numpy as np
import pandas as pd
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# ===== Firebase Admin =====
import firebase_admin
from firebase_admin import credentials, db

# ===== Signal processing =====
from scipy import signal
from scipy.fft import fft, fftfreq
from scipy.signal import find_peaks

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ["FLASK_SECRET_KEY"]
csrf = CSRFProtect(app)

# ================== CONFIG FIREBASE (REST para dashboard) ==================
FIREBASE_URL = os.environ["FIREBASE_URL"]
USER_ID = os.environ["FIREBASE_USER_ID"]
DEVICE_ID = os.environ["FIREBASE_DEVICE_ID"]

# ================== FIREBASE ADMIN KEY ==================
# Coloca tu serviceAccountKey.json en la ruta indicada por esta variable de entorno
# (por defecto, junto a app.py). Nunca subas este archivo a git.
SERVICE_ACCOUNT_PATH = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH", "serviceAccountKey.json")

def initialize_firebase_admin():
    """Inicializa Firebase Admin (solo una vez)."""
    if not firebase_admin._apps:
        if not os.path.exists(SERVICE_ACCOUNT_PATH):
            raise FileNotFoundError(
                f"No encontré {SERVICE_ACCOUNT_PATH}. Colócalo junto a app.py o ajusta la ruta."
            )

        cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
        firebase_admin.initialize_app(cred, {
            "databaseURL": FIREBASE_URL
        })
        print("✓ Firebase Admin inicializado")
    else:
        # ya estaba inicializado
        pass


# Usuario de prueba (credenciales configurables por variables de entorno; NUNCA hardcodear aquí)
USERS = {
    os.environ.get("DEMO_USER_EMAIL", "demo@demo.com"): {
        "password": os.environ.get("DEMO_USER_PASSWORD", "changeme"),
        "name": os.environ.get("DEMO_USER_NAME", "Usuario Demo")
    }
}

# Cuenta de servicio de Firebase Auth usada por el JS del cliente (dashboard/rawdata)
# para autenticarse contra Realtime Database. Se inyecta a las plantillas vía
# context_processor en vez de vivir hardcodeada en los .js estáticos.
FIREBASE_DEVICE_AUTH_EMAIL = os.environ["FIREBASE_DEVICE_AUTH_EMAIL"]
FIREBASE_DEVICE_AUTH_PASSWORD = os.environ["FIREBASE_DEVICE_AUTH_PASSWORD"]


@app.context_processor
def inject_firebase_device_auth():
    return {
        "firebase_device_auth_email": FIREBASE_DEVICE_AUTH_EMAIL,
        "firebase_device_auth_password": FIREBASE_DEVICE_AUTH_PASSWORD,
        "firebase_user_id": USER_ID,
        "firebase_device_id": DEVICE_ID,
    }

# ================== ML MODEL (RF) ==================
MODEL_PATH = "rf_model.joblib"
FEATURES_PATH = "features_order.json"

model = joblib.load(MODEL_PATH)
with open(FEATURES_PATH, "r", encoding="utf-8") as f:
    FEATURES = json.load(f)

ALLOWED_EXTENSIONS = {"csv"}
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

NEW_WALKS_DIR = "new_walks"
os.makedirs(NEW_WALKS_DIR, exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ================== DASHBOARD: leer steps_interval por REST ==================
def get_capture_steps():
    """
    Lee capturas de /rawdata en Firebase (REST) y regresa lista:
    [{subject, steps_interval, label, ts_str}, ...]
    Solo incluye capturas con steps_interval.
    """
    url = f"{FIREBASE_URL}/users/{USER_ID}/devices/{DEVICE_ID}/rawdata.json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json() or {}
    except Exception as e:
        print(f"[ERROR] No se pudo leer rawdata desde Firebase: {e}")
        data = {}

    captures = []
    for key, value in data.items():
        if not isinstance(value, dict):
            continue

        steps_interval = value.get("steps_interval")
        if steps_interval is None:
            continue

        subject_id = value.get("subjectId", "NA")
        label = value.get("label", "")

        ts_ms = value.get("timestamp")
        if ts_ms is None:
            try:
                ts_ms = int(key)
            except (TypeError, ValueError):
                ts_ms = None

        if ts_ms is not None:
            dt = datetime.fromtimestamp(ts_ms / 1000.0)
            ts_str = dt.strftime("%Y-%m-%d %H:%M")
        else:
            ts_str = "s/f"

        captures.append({
            "subject": subject_id,
            "steps_interval": steps_interval,
            "label": label,
            "ts_str": ts_str,
        })

    captures.sort(key=lambda x: x["ts_str"])
    return captures


# ================== HISTORIAL DE PREDICCIONES ==================
def save_prediction_to_firebase(predicted_label, confidence, steps_10s, capture_date, user_id=USER_ID, device_id=DEVICE_ID):
    """
    Guarda una predicción en Firebase bajo:
    /users/{user_id}/devices/{device_id}/predictions/{timestamp}
    """
    try:
        initialize_firebase_admin()
        ref = db.reference(f"users/{user_id}/devices/{device_id}/predictions")

        timestamp = int(datetime.now().timestamp() * 1000)
        prediction_data = {
            "predicted_label": predicted_label,
            "confidence": confidence if confidence is not None else 0.0,
            "steps_10s": steps_10s if steps_10s is not None else 0,
            "capture_date": capture_date,
            "prediction_timestamp": timestamp
        }

        ref.child(str(timestamp)).set(prediction_data)
        print(f"✓ Predicción guardada en Firebase: {predicted_label}")
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo guardar la predicción en Firebase: {e}")
        return False


def get_prediction_history(user_id=USER_ID, device_id=DEVICE_ID, limit=10):
    """
    Recupera el historial de predicciones desde Firebase.
    Retorna lista ordenada por timestamp (más reciente primero).
    """
    url = f"{FIREBASE_URL}/users/{user_id}/devices/{device_id}/predictions.json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json() or {}
    except Exception as e:
        print(f"[ERROR] No se pudo leer historial de predicciones: {e}")
        return []

    history = []
    for key, value in data.items():
        if not isinstance(value, dict):
            continue

        prediction_ts = value.get("prediction_timestamp")
        if prediction_ts:
            dt = datetime.fromtimestamp(prediction_ts / 1000.0)
            prediction_date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            prediction_date_str = "s/f"

        history.append({
            "predicted_label": value.get("predicted_label", "N/A"),
            "confidence": value.get("confidence", 0.0),
            "steps_10s": value.get("steps_10s", 0),
            "capture_date": value.get("capture_date", "N/A"),
            "prediction_date": prediction_date_str
        })

    # Ordenar por fecha de predicción (más reciente primero)
    history.sort(key=lambda x: x["prediction_date"], reverse=True)

    return history[:limit]


# ================== FEATURE EXTRACTION (tu pipeline) ==================
def extract_temporal_features(x, y, z):
    magnitude = np.sqrt(x**2 + y**2 + z**2)
    return {
        'mean_x': np.mean(x), 'mean_y': np.mean(y), 'mean_z': np.mean(z), 'mean_mag': np.mean(magnitude),
        'std_x': np.std(x), 'std_y': np.std(y), 'std_z': np.std(z), 'std_mag': np.std(magnitude),
        'var_x': np.var(x), 'var_y': np.var(y), 'var_z': np.var(z), 'var_mag': np.var(magnitude),
        'range_x': np.max(x) - np.min(x), 'range_y': np.max(y) - np.min(y),
        'range_z': np.max(z) - np.min(z), 'range_mag': np.max(magnitude) - np.min(magnitude),
        'max_x': np.max(x), 'max_y': np.max(y), 'max_z': np.max(z), 'max_mag': np.max(magnitude),
        'min_x': np.min(x), 'min_y': np.min(y), 'min_z': np.min(z), 'min_mag': np.min(magnitude),
        'q25_mag': np.percentile(magnitude, 25),
        'q50_mag': np.percentile(magnitude, 50),
        'q75_mag': np.percentile(magnitude, 75),
        'cv_mag': np.std(magnitude) / (np.mean(magnitude) + 1e-10),
        'rms_x': np.sqrt(np.mean(x**2)),
        'rms_y': np.sqrt(np.mean(y**2)),
        'rms_z': np.sqrt(np.mean(z**2)),
        'rms_mag': np.sqrt(np.mean(magnitude**2)),
    }

def extract_movement_features(x, y, z, sampling_rate=50):
    dt = 1.0 / sampling_rate
    vx = np.diff(x) / dt
    vy = np.diff(y) / dt
    vz = np.diff(z) / dt

    jerk_x = np.diff(vx) / dt
    jerk_y = np.diff(vy) / dt
    jerk_z = np.diff(vz) / dt
    jerk_mag = np.sqrt(jerk_x**2 + jerk_y**2 + jerk_z**2)

    magnitude = np.sqrt(x**2 + y**2 + z**2)

    return {
        'mean_jerk': np.mean(jerk_mag),
        'std_jerk': np.std(jerk_mag),
        'max_jerk': np.max(jerk_mag),
        'min_jerk': np.min(jerk_mag),

        'sma': (np.sum(np.abs(x)) + np.sum(np.abs(y)) + np.sum(np.abs(z))) / len(x),

        'zcr_x': np.sum(np.diff(np.sign(x)) != 0),
        'zcr_y': np.sum(np.diff(np.sign(y)) != 0),
        'zcr_z': np.sum(np.diff(np.sign(z)) != 0),
        'zcr_mag': np.sum(np.diff(np.sign(magnitude - np.mean(magnitude))) != 0),

        'energy_x': np.sum(x**2),
        'energy_y': np.sum(y**2),
        'energy_z': np.sum(z**2),
        'energy_mag': np.sum(magnitude**2),
    }

def extract_frequency_features(x, y, z, sampling_rate=50):
    magnitude = np.sqrt(x**2 + y**2 + z**2)
    n = len(magnitude)
    fft_values = np.abs(fft(magnitude))
    freqs = fftfreq(n, 1 / sampling_rate)

    positive_freqs = freqs[:n // 2]
    positive_fft = fft_values[:n // 2]

    positive_fft_norm = (positive_fft / np.sum(positive_fft)) if np.sum(positive_fft) != 0 else np.zeros_like(positive_fft)

    dominant_idx = int(np.argmax(positive_fft))
    dominant_freq = float(positive_freqs[dominant_idx])

    def power_in_band(freqs_, fft_vals_, low, high):
        mask = (freqs_ >= low) & (freqs_ <= high)
        return float(np.sum(fft_vals_[mask]**2))

    spectral_energy = float(np.sum(positive_fft**2))
    spectral_centroid = float(np.sum(positive_freqs * positive_fft) / (np.sum(positive_fft) + 1e-10))

    features = {
        'dominant_power': float(positive_fft[dominant_idx]),
        'spectral_energy': spectral_energy,
        'power_tremor_band': power_in_band(positive_freqs, positive_fft, 4, 6),
        'power_low_freq': power_in_band(positive_freqs, positive_fft, 0.5, 3),
        'power_mid_freq': power_in_band(positive_freqs, positive_fft, 3, 8),
        'power_high_freq': power_in_band(positive_freqs, positive_fft, 8, 15),
        'spectral_entropy': float(-np.sum(positive_fft_norm * np.log2(positive_fft_norm + 1e-10))),
        'spectral_centroid': spectral_centroid,
    }

    features['spectral_spread'] = float(np.sqrt(
        np.sum(((positive_freqs - spectral_centroid) ** 2) * positive_fft) / (np.sum(positive_fft) + 1e-10)
    ))

    return features

def extract_fog_features(x, y, z, sampling_rate=50):
    magnitude = np.sqrt(x**2 + y**2 + z**2)
    n = len(magnitude)

    fft_values = np.abs(fft(magnitude))
    freqs = fftfreq(n, 1 / sampling_rate)
    positive_freqs = freqs[:n // 2]
    positive_fft = fft_values[:n // 2]

    def power_in_band(freqs_, fft_vals_, low, high):
        mask = (freqs_ >= low) & (freqs_ <= high)
        return float(np.sum(fft_vals_[mask]**2))

    locomotor_band = power_in_band(positive_freqs, positive_fft, 0.5, 3)
    freeze_band = power_in_band(positive_freqs, positive_fft, 3, 8)
    freeze_index = float(freeze_band / (locomotor_band + 1e-10))

    try:
        sos = signal.butter(4, [0.5, 3], btype='band', fs=sampling_rate, output='sos')
        filtered_signal = signal.sosfilt(sos, magnitude)
        peaks, _ = find_peaks(filtered_signal, distance=sampling_rate // 4)

        cadence = float(len(peaks) * (60 / (len(magnitude) / sampling_rate)))

        if len(peaks) > 1:
            step_intervals = np.diff(peaks) / sampling_rate
            step_regularity = float(np.std(step_intervals))
        else:
            step_regularity = 0.0
    except Exception:
        cadence = 0.0
        step_regularity = 0.0

    return {
        'freeze_index': freeze_index,
        'locomotor_power': float(locomotor_band),
        'freeze_power': float(freeze_band),
        'cadence_spm': cadence,
        'step_regularity': step_regularity,
        'freeze_ratio': float(freeze_band / (freeze_band + locomotor_band + 1e-10)),
    }

def extract_all_features(samples, sampling_rate=50):
    x = np.array([s.get('x', 0.0) for s in samples], dtype=float)
    y = np.array([s.get('y', 0.0) for s in samples], dtype=float)
    z = np.array([s.get('z', 0.0) for s in samples], dtype=float)

    if np.any(np.isnan(x)) or np.any(np.isnan(y)) or np.any(np.isnan(z)):
        return None

    feats = {}
    feats.update(extract_temporal_features(x, y, z))
    feats.update(extract_movement_features(x, y, z, sampling_rate))
    feats.update(extract_frequency_features(x, y, z, sampling_rate))
    feats.update(extract_fog_features(x, y, z, sampling_rate))
    return feats


# ================== Latest capture utils (Firebase Admin) ==================
def get_latest_capture(user_uid, device_id, path_suffix="rawdata"):
    initialize_firebase_admin()
    path = f'users/{user_uid}/devices/{device_id}/{path_suffix}'
    ref = db.reference(path)
    captures = ref.get() or {}

    if not captures:
        return None, None

    def capture_ts(item):
        capture_id, data = item
        if isinstance(data, dict) and "timestamp" in data:
            return int(data.get("timestamp", 0))
        try:
            return int(capture_id)
        except:
            return 0

    latest_id, latest_data = max(captures.items(), key=capture_ts)
    return latest_id, latest_data


def build_one_row_for_model(capture_data):
    samples = capture_data.get("samples", [])
    if not isinstance(samples, list) or len(samples) < 10:
        raise ValueError("La captura no tiene samples suficientes.")

    feats = extract_all_features(samples, sampling_rate=capture_data.get("sampleRate", 50))
    if feats is None:
        raise ValueError("No se pudieron extraer features (NaNs o error).")

    # steps_interval -> steps_10s
    steps_interval = capture_data.get("steps_interval", np.nan)
    try:
        steps_interval = int(steps_interval) if steps_interval is not None else np.nan
    except:
        steps_interval = np.nan

    feats["steps_10s"] = steps_interval
    feats["numSamples"] = len(samples)

    row = {c: feats.get(c, 0.0) for c in FEATURES}
    df_one = pd.DataFrame([row], columns=FEATURES)
    return df_one


# ================== ROUTES ==================
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    capture_steps = get_capture_steps()
    return render_template("dashboard.html", capture_steps=capture_steps)


@app.route("/rawdata")
def rawdata():
    return render_template("rawdata.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = USERS.get(email)
        if user and password == user["password"]:
            session["user_email"] = email
            session["user_name"] = user["name"]
            flash("Inicio de sesión correcto", "success")
            return redirect(url_for("home"))
        else:
            flash("Email o contraseña incorrectos", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/classify_walk", methods=["GET"])
def classify_walk():
    history = get_prediction_history(limit=10)
    return render_template("classify_walk.html", history=history)


@app.route("/predict_walk", methods=["POST"])
def predict_walk():
    if "csv_file" not in request.files:
        flash("No se recibió archivo.", "danger")
        return redirect(url_for("classify_walk"))

    f = request.files["csv_file"]

    if f.filename == "":
        flash("Selecciona un archivo CSV.", "warning")
        return redirect(url_for("classify_walk"))

    if not allowed_file(f.filename):
        flash("El archivo debe ser .csv", "danger")
        return redirect(url_for("classify_walk"))

    filename = secure_filename(f.filename)
    filepath = os.path.join(UPLOAD_DIR, filename)
    f.save(filepath)

    try:
        df = pd.read_csv(filepath)

        missing = [c for c in FEATURES if c not in df.columns]
        if missing:
            flash(f"Faltan columnas en tu CSV: {missing[:8]}... (total {len(missing)})", "danger")
            return redirect(url_for("classify_walk"))

        # Recomendación: exigir 1 fila para evitar confusión
        if len(df) != 1:
            flash(f"Tu CSV tiene {len(df)} filas. Sube un CSV con 1 sola caminata (1 fila).", "warning")
            return redirect(url_for("classify_walk"))

        x = df[FEATURES].iloc[0].to_numpy(dtype=float).reshape(1, -1)

        pred = model.predict(x)[0]

        confidence = None
        probs = None
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(x)[0]
            confidence = float(np.max(proba))
            probs = list(zip(model.classes_.tolist(), proba.tolist()))

        # ====== Guardar en historial de Firebase ======
        save_prediction_to_firebase(pred, confidence, None, "Desde CSV")

        # ====== Obtener historial actualizado ======
        history = get_prediction_history(limit=10)

        return render_template(
            "classify_walk.html",
            predicted_label=pred,
            confidence=confidence,
            probs=probs,
            filename=filename,
            history=history
        )

    except Exception as e:
        flash(f"Error procesando el CSV: {e}", "danger")
        return redirect(url_for("classify_walk"))


@app.route("/predict_last_walk", methods=["POST"])
def predict_last_walk():
    try:
        latest_id, latest_data = get_latest_capture(USER_ID, DEVICE_ID, "rawdata")
        if latest_data is None:
            flash("No hay capturas disponibles en Firebase.", "warning")
            return redirect(url_for("classify_walk"))

        # ====== Extraer pasos (10s) y fecha de captura ======
        steps_10s = latest_data.get("steps_interval", None)

        ts_ms = latest_data.get("timestamp", None)
        if ts_ms:
            capture_date = datetime.fromtimestamp(ts_ms / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
        else:
            capture_date = "No disponible"

        # ====== Construir fila con features para el modelo ======
        df_one = build_one_row_for_model(latest_data)
        x = df_one.to_numpy(dtype=float)

        # ====== Predicción ======
        pred = model.predict(x)[0]

        confidence = None
        probs = None
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(x)[0]
            confidence = float(np.max(proba))
            probs = list(zip(model.classes_.tolist(), proba.tolist()))

        # ====== Guardar CSV de auditoría (opcional) ======
        csv_name = f"last_walk_{latest_id}.csv"
        csv_path = os.path.join(NEW_WALKS_DIR, csv_name)
        df_one.to_csv(csv_path, index=False)

        # ====== Guardar en historial de Firebase ======
        save_prediction_to_firebase(pred, confidence, steps_10s, capture_date)

        flash("Última caminata clasificada correctamente.", "success")

        # ====== Obtener historial actualizado ======
        history = get_prediction_history(limit=10)

        return render_template(
            "classify_walk.html",
            predicted_label=pred,
            confidence=confidence,
            probs=probs,
            filename=csv_name,
            steps_10s=steps_10s,
            capture_date=capture_date,
            history=history
        )

    except Exception as e:
        flash(f"Error al clasificar la última caminata: {e}", "danger")
        return redirect(url_for("classify_walk"))



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
