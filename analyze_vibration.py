import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.fft import fft, fftfreq
from scipy.signal import butter, sosfilt, find_peaks, welch
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime  # ← AGREGADO
from dotenv import load_dotenv

load_dotenv()

FIREBASE_USER_ID = os.environ.get("FIREBASE_USER_ID")
FIREBASE_DEVICE_ID = os.environ.get("FIREBASE_DEVICE_ID")

def initialize_firebase():
    cred = credentials.Certificate(os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH", "serviceAccountKey.json"))
    firebase_admin.initialize_app(cred, {
        'databaseURL': os.environ["FIREBASE_URL"]
    })
    print("✓ Firebase inicializado")

def analyze_vibration_table(capture_id, expected_rpm):
    """Analiza captura de mesa vibradora"""

    ref = db.reference(f'users/{FIREBASE_USER_ID}/devices/{FIREBASE_DEVICE_ID}/rawdata/{capture_id}')
    capture_data = ref.get()
    
    if not capture_data or 'samples' not in capture_data:
        print("❌ Captura no encontrada")
        return
    
    samples = capture_data['samples']
    x = np.array([s['x'] for s in samples])
    y = np.array([s['y'] for s in samples])
    z = np.array([s['z'] for s in samples])
    t = np.array([s['t'] for s in samples]) / 1000
    
    magnitude = np.sqrt(x**2 + y**2 + z**2)
    sampling_rate = 50
    duration = t[-1] - t[0]
    
    # Frecuencia esperada
    expected_freq = expected_rpm / 60
    
    print("\n" + "="*80)
    print(f"ANÁLISIS DE MESA VIBRADORA")
    print("="*80)
    print(f"Captura: {capture_id}")
    print(f"RPM esperadas: {expected_rpm}")
    print(f"Frecuencia esperada: {expected_freq:.3f} Hz")
    print(f"Duración: {duration:.2f} seg")
    print(f"Muestras: {len(samples)}")
    
    # ========== ANÁLISIS FFT ==========
    n = len(magnitude)
    fft_values = fft(magnitude)
    fft_magnitude = np.abs(fft_values)
    freqs = fftfreq(n, 1/sampling_rate)
    
    positive_mask = freqs > 0
    positive_freqs = freqs[positive_mask]
    positive_fft = fft_magnitude[positive_mask]
    
    # Encontrar top 5 frecuencias
    top_indices = np.argsort(positive_fft)[-5:][::-1]
    
    print("\n" + "-"*80)
    print("TOP 5 FRECUENCIAS DETECTADAS")
    print("-"*80)
    for i, idx in enumerate(top_indices, 1):
        freq = positive_freqs[idx]
        power = positive_fft[idx]
        rpm = freq * 60
        print(f"{i}. Frecuencia: {freq:.3f} Hz → {rpm:.1f} RPM (Potencia: {power:.2f})")
    
    # ========== ANÁLISIS POR BANDAS ==========
    print("\n" + "-"*80)
    print("ANÁLISIS POR BANDAS")
    print("-"*80)
    
    bands = [
        (0, 0.5, "0-30 RPM"),
        (0.5, 1.0, "30-60 RPM"),
        (1.0, 2.0, "60-120 RPM"),
        (2.0, 5.0, "120-300 RPM"),
        (5.0, 10.0, "300-600 RPM"),
    ]
    
    for low, high, label in bands:
        mask = (positive_freqs >= low) & (positive_freqs < high)
        band_freqs = positive_freqs[mask]
        band_fft = positive_fft[mask]
        
        if len(band_fft) > 0:
            power = np.sum(band_fft**2)
            dominant_idx = np.argmax(band_fft)
            dominant_freq = band_freqs[dominant_idx]
            print(f"{label:20s}: Potencia={power:8.2f}, Freq. dominante={dominant_freq:.3f} Hz ({dominant_freq*60:.1f} RPM)")
    
    # ========== DETECCIÓN DE PICOS ==========
    print("\n" + "-"*80)
    print("DETECCIÓN DE PICOS (diferentes umbrales)")
    print("-"*80)
    
    # Probar diferentes filtros
    filter_configs = [
        ([0.1, 1], "Filtro 0.1-1 Hz (6-60 RPM)"),
        ([0.2, 2], "Filtro 0.2-2 Hz (12-120 RPM)"),
        ([0.5, 5], "Filtro 0.5-5 Hz (30-300 RPM)"),
    ]
    
    for freq_range, label in filter_configs:
        sos = butter(4, freq_range, btype='band', fs=sampling_rate, output='sos')
        filtered = sosfilt(sos, magnitude)
        
        peaks, _ = find_peaks(filtered, distance=sampling_rate//10, prominence=0.05)
        rpm_detected = (len(peaks) / duration) * 60
        
        print(f"{label:35s}: {len(peaks):2d} picos → {rpm_detected:.1f} RPM")
    
    # ========== VISUALIZACIÓN ==========
    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(5, 2, hspace=0.3, wspace=0.3)
    
    # 1. Señal temporal - Magnitud
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(t, magnitude, 'b-', linewidth=1, alpha=0.7)
    ax1.set_title(f'Señal de Magnitud - Mesa Vibradora a {expected_rpm} RPM', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Tiempo (s)')
    ax1.set_ylabel('Magnitud (g)')
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=np.mean(magnitude), color='r', linestyle='--', alpha=0.5, label='Media')
    ax1.legend()
    
    # 2. Señales por eje
    ax2 = fig.add_subplot(gs[1, :])
    ax2.plot(t, x, 'r-', label='X', alpha=0.7, linewidth=1)
    ax2.plot(t, y, 'g-', label='Y', alpha=0.7, linewidth=1)
    ax2.plot(t, z, 'b-', label='Z', alpha=0.7, linewidth=1)
    ax2.set_title('Aceleración por Eje', fontsize=12, fontweight='bold')
    ax2.set_xlabel('Tiempo (s)')
    ax2.set_ylabel('Aceleración (g)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Espectro FFT completo
    ax3 = fig.add_subplot(gs[2, 0])
    ax3.plot(positive_freqs, positive_fft, 'b-', linewidth=1)
    ax3.axvline(expected_freq, color='r', linestyle='--', linewidth=2, label=f'Esperado: {expected_freq:.3f} Hz')
    ax3.set_title('Espectro FFT Completo', fontsize=12, fontweight='bold')
    ax3.set_xlabel('Frecuencia (Hz)')
    ax3.set_ylabel('Amplitud')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.set_xlim(0, 10)
    
    # 4. Espectro FFT - Zoom en banda baja
    ax4 = fig.add_subplot(gs[2, 1])
    low_mask = (positive_freqs >= 0) & (positive_freqs <= 3)
    ax4.plot(positive_freqs[low_mask], positive_fft[low_mask], 'g-', linewidth=2)
    ax4.axvline(expected_freq, color='r', linestyle='--', linewidth=2, label=f'Esperado: {expected_freq:.3f} Hz')
    ax4.set_title('Espectro FFT - Banda 0-3 Hz (0-180 RPM)', fontsize=12, fontweight='bold')
    ax4.set_xlabel('Frecuencia (Hz)')
    ax4.set_ylabel('Amplitud')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    # 5. Señal filtrada 0.1-1 Hz
    ax5 = fig.add_subplot(gs[3, 0])
    sos = butter(4, [0.1, 1], btype='band', fs=sampling_rate, output='sos')
    filtered_low = sosfilt(sos, magnitude)
    peaks_low, _ = find_peaks(filtered_low, distance=sampling_rate//10, prominence=0.05)
    ax5.plot(t, filtered_low, 'g-', linewidth=1.5)
    ax5.plot(t[peaks_low], filtered_low[peaks_low], 'ro', markersize=8, label=f'{len(peaks_low)} picos')
    ax5.set_title(f'Señal Filtrada 0.1-1 Hz (6-60 RPM) - {(len(peaks_low)/duration)*60:.1f} RPM', fontsize=12, fontweight='bold')
    ax5.set_xlabel('Tiempo (s)')
    ax5.set_ylabel('Amplitud')
    ax5.legend()
    ax5.grid(True, alpha=0.3)
    
    # 6. Señal filtrada 0.2-2 Hz
    ax6 = fig.add_subplot(gs[3, 1])
    sos = butter(4, [0.2, 2], btype='band', fs=sampling_rate, output='sos')
    filtered_mid = sosfilt(sos, magnitude)
    peaks_mid, _ = find_peaks(filtered_mid, distance=sampling_rate//10, prominence=0.05)
    ax6.plot(t, filtered_mid, 'orange', linewidth=1.5)
    ax6.plot(t[peaks_mid], filtered_mid[peaks_mid], 'ro', markersize=8, label=f'{len(peaks_mid)} picos')
    ax6.set_title(f'Señal Filtrada 0.2-2 Hz (12-120 RPM) - {(len(peaks_mid)/duration)*60:.1f} RPM', fontsize=12, fontweight='bold')
    ax6.set_xlabel('Tiempo (s)')
    ax6.set_ylabel('Amplitud')
    ax6.legend()
    ax6.grid(True, alpha=0.3)
    
    # 7. Welch PSD
    ax7 = fig.add_subplot(gs[4, :])
    freqs_welch, psd_welch = welch(magnitude, fs=sampling_rate, nperseg=min(256, len(magnitude)//2))
    ax7.semilogy(freqs_welch, psd_welch, 'purple', linewidth=1.5)
    ax7.axvline(expected_freq, color='r', linestyle='--', linewidth=2, label=f'Esperado: {expected_freq:.3f} Hz')
    ax7.set_title('Densidad Espectral de Potencia (Welch)', fontsize=12, fontweight='bold')
    ax7.set_xlabel('Frecuencia (Hz)')
    ax7.set_ylabel('PSD')
    ax7.legend()
    ax7.grid(True, alpha=0.3, which='both')
    ax7.set_xlim(0, 10)
    
    plt.suptitle(f'Análisis Completo: Mesa Vibradora a {expected_rpm} RPM (Esperado: {expected_freq:.3f} Hz)', 
                 fontsize=16, fontweight='bold', y=0.995)
    
    filename = f'vibration_analysis_{expected_rpm}rpm_{capture_id}.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"\n✓ Visualización guardada: {filename}")
    plt.show()

if __name__ == '__main__':
    initialize_firebase()
    
    # Lista capturas
    ref = db.reference(f'users/{FIREBASE_USER_ID}/devices/{FIREBASE_DEVICE_ID}/rawdata')
    captures = ref.get()
    
    if not captures:
        print("❌ No hay capturas")
    else:
        print(f"\n📊 Capturas disponibles:")
        capture_list = list(captures.items())
        
        for i, (capture_id, data) in enumerate(capture_list[-10:], 1):
            date = datetime.fromtimestamp(int(capture_id)/1000)
            print(f"{i}. {capture_id} - {date}")
        
        print("\n" + "="*80)
        choice = input("Ingresa el número de captura (o Enter para la última): ").strip()
        
        if choice:
            idx = int(choice) - 1
            capture_id = capture_list[-(10-idx)][0]
        else:
            capture_id = capture_list[-1][0]
        
        expected_rpm = int(input("Ingresa las RPM esperadas de la mesa vibradora: "))
        
        print(f"\n🔍 Analizando captura: {capture_id}")
        print(f"🎯 RPM esperadas: {expected_rpm}")
        
        analyze_vibration_table(capture_id, expected_rpm)