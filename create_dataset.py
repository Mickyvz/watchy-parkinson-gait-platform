# -*- coding: utf-8 -*-
import os
import pandas as pd
import numpy as np
from scipy import signal
from scipy.fft import fft, fftfreq
from scipy.signal import find_peaks
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv

load_dotenv()

# ================== CONFIGURACIÓN DE FIREBASE ==================

def initialize_firebase():
    """Inicializa conexión con Firebase Realtime Database."""
    cred = credentials.Certificate(
        os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH", "serviceAccountKey.json")
    )

    # Evita error si se ejecuta más de una vez en la misma sesión
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            'databaseURL': os.environ["FIREBASE_URL"]
        })
        print("✓ Firebase inicializado")
    else:
        print("✓ Firebase ya estaba inicializado")

# ================== EXTRACCIÓN DE CARACTERÍSTICAS ==================

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
        'dominant_frequency': dominant_freq,
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

    # Cadencia aproximada (por picos)
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
        print("⚠ Warning: NaN values detected in samples")
        return None

    feats = {}
    feats.update(extract_temporal_features(x, y, z))
    feats.update(extract_movement_features(x, y, z, sampling_rate))
    feats.update(extract_frequency_features(x, y, z, sampling_rate))
    feats.update(extract_fog_features(x, y, z, sampling_rate))
    return feats

# ================== CONSTRUCCIÓN DEL DATASET DESDE FIREBASE ==================

def build_dataset_from_firebase(
    user_uid='2sDny0TUnwc6X8SfnU1XrL733HE3',
    device_id='watchy-v2-01',
    path_suffix='rawdata'
):
    """
    Lee capturas desde Firebase RTDB y crea un dataset (1 fila por captura ~10s),
    agregando steps_interval como steps_10s.
    """
    path = f'users/{user_uid}/devices/{device_id}/{path_suffix}'
    print("\n=== CONSTRUYENDO DATASET DESDE FIREBASE ===\n")
    print(f"Ruta: {path}\n")

    ref = db.reference(path)
    captures = ref.get()

    if not captures:
        print("❌ No se encontraron capturas en Firebase")
        return None

    print(f"📊 Total de capturas encontradas: {len(captures)}")

    dataset = []
    skipped = 0

    for capture_id, capture_data in captures.items():
        # Validaciones
        samples = capture_data.get('samples', None)
        label = capture_data.get('label', None)

        if samples is None or not isinstance(samples, list) or len(samples) < 10:
            skipped += 1
            continue

        if label is None:
            skipped += 1
            continue

        feats = extract_all_features(samples, sampling_rate=capture_data.get('sampleRate', 50))
        if feats is None:
            skipped += 1
            continue

        # ======== PASOS DURANTE LA CAPTURA (10s) =========
        # Tu Firebase ya trae steps_interval (pasos dentro del intervalo)
        steps_interval = capture_data.get('steps_interval', np.nan)
        try:
            steps_interval = int(steps_interval) if steps_interval is not None else np.nan
        except Exception:
            steps_interval = np.nan

        feats['steps_10s'] = steps_interval

        # (Opcional) guardar también start/end si existen (útil para auditoría)
        feats['steps_start'] = capture_data.get('steps_start', np.nan)
        feats['steps_end'] = capture_data.get('steps_end', np.nan)

        # Metadatos
        feats['captureId'] = capture_id
        feats['label'] = label
        feats['subjectId'] = capture_data.get('subjectId', 'unknown')
        feats['activityContext'] = capture_data.get('activityContext', 'unknown')
        feats['captureDate'] = capture_data.get('captureDate', '')
        feats['timestamp'] = capture_data.get('timestamp', 0)
        feats['sampleRate'] = capture_data.get('sampleRate', 50)
        feats['duration_ms'] = capture_data.get('duration', 10000)
        feats['numSamples'] = len(samples)

        dataset.append(feats)

    print(f"\n✓ Procesadas: {len(dataset)} capturas")
    print(f"⚠ Omitidas: {skipped} capturas")

    if not dataset:
        return None

    df = pd.DataFrame(dataset)

    # Asegura numéricos
    for c in ['steps_10s', 'steps_start', 'steps_end']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')

    print("\n=== RESUMEN DEL DATASET ===")
    print(f"Filas: {len(df)}")
    print(f"Columnas: {len(df.columns)}")
    print("\nDistribución label:")
    print(df['label'].value_counts())
    print("\nDistribución subjectId:")
    print(df['subjectId'].value_counts())

    # Quick sanity-check: si hay start/end, comprobar diferencia
    if 'steps_start' in df.columns and 'steps_end' in df.columns:
        valid = df[['steps_start', 'steps_end', 'steps_10s']].dropna()
        if len(valid) > 0:
            valid['diff'] = valid['steps_end'] - valid['steps_start']
            mismatch = (valid['diff'] != valid['steps_10s']).sum()
            print(f"\nCheck steps: mismatches (end-start vs steps_10s): {mismatch} de {len(valid)}")

    return df

def save_dataset(df, filename='watchy_gait_dataset.csv'):
    df.to_csv(filename, index=False, encoding='utf-8')
    print(f"\n✓ Dataset guardado en: {filename}")
    print(f"→ Filas: {len(df)} | Columnas: {len(df.columns)}")

# ================== MAIN ==================

if __name__ == '__main__':
    initialize_firebase()

    df = build_dataset_from_firebase(
        user_uid='2sDny0TUnwc6X8SfnU1XrL733HE3',
        device_id='watchy-v2-01',
        path_suffix='rawdata'
    )

    if df is not None and len(df) > 0:
        save_dataset(df, filename='watchy_gait_dataset2.csv')

        print("\n=== PRIMERAS FILAS ===")
        print(df[['captureId', 'label', 'subjectId', 'steps_10s', 'steps_start', 'steps_end']].head())
    else:
        print("❌ No se pudo construir el dataset (0 capturas válidas)")
