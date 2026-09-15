import pandas as pd
import numpy as np
from scipy import signal
from scipy.fft import fft, fftfreq
from scipy.signal import find_peaks
import firebase_admin
from firebase_admin import credentials, db
import joblib
import time
from datetime import datetime

# Importar funciones de extracción de features
from create_dataset import extract_all_features, initialize_firebase

# ================== CARGAR MODELO ENTRENADO ==================
def load_model():
    """Carga el modelo y scaler entrenados"""
    try:
        clf = joblib.load('tremor_fog_classifier.pkl')
        scaler = joblib.load('scaler.pkl')
        print("✓ Modelo cargado exitosamente")
        return clf, scaler
    except FileNotFoundError:
        print("❌ Error: No se encontró el modelo entrenado")
        print("   Ejecuta 'python train_model.py' primero")
        return None, None

# ================== PREDICCIÓN ==================
def predict_capture(samples, clf, scaler, feature_cols):
    """Predice la clase de una captura"""
    # Extraer features
    features = extract_all_features(samples)
    
    if features is None:
        return None, None
    
    # Convertir a DataFrame con las columnas correctas
    features_df = pd.DataFrame([features])
    
    # Seleccionar solo las features usadas en entrenamiento
    X = features_df[feature_cols].values
    
    # Normalizar
    X_scaled = scaler.transform(X)
    
    # Predecir
    prediction = clf.predict(X_scaled)[0]
    probabilities = clf.predict_proba(X_scaled)[0]
    confidence = np.max(probabilities)
    
    # Crear dict con probabilidades por clase
    prob_dict = {
        cls: float(prob) 
        for cls, prob in zip(clf.classes_, probabilities)
    }
    
    return prediction, confidence, prob_dict

# ================== GUARDAR PREDICCIÓN EN FIREBASE ==================
def save_prediction_to_firebase(capture_id, prediction, confidence, prob_dict, features):
    """Guarda la predicción en Firebase"""
    try:
        # Path para guardar predicciones
        ref = db.reference(f'users/2sDny0TUnwc6X8SfnU1XrL733HE3/devices/watchy-v2-01/predictions/{capture_id}')
        
        prediction_data = {
            'timestamp': int(datetime.now().timestamp() * 1000),
            'prediction': prediction,
            'confidence': float(confidence),
            'probabilities': prob_dict,
            'captureId': capture_id,
            # Agregar algunas features clave para visualización
            'freeze_index': float(features.get('freeze_index', 0)),
            'dominant_frequency': float(features.get('dominant_frequency', 0)),
            'cadence': float(features.get('cadence', 0)),
            'mean_jerk': float(features.get('mean_jerk', 0)),
        }
        
        ref.set(prediction_data)
        print(f"✓ Predicción guardada para {capture_id}")
        
    except Exception as e:
        print(f"❌ Error guardando predicción: {e}")

# ================== MONITOREO CONTINUO ==================
def monitor_new_captures(clf, scaler, feature_cols):
    """Monitorea Firebase y predice capturas nuevas"""
    print("\n=== INICIANDO MONITOREO DE CAPTURAS ===")
    print("Esperando nuevas capturas...\n")
    
    # Referencia a rawdata
    ref = db.reference('users/2sDny0TUnwc6X8SfnU1XrL733HE3/devices/watchy-v2-01/rawdata')
    
    # Mantener track de capturas ya procesadas
    processed_captures = set()
    
    # Cargar capturas existentes
    existing_captures = ref.get()
    if existing_captures:
        processed_captures = set(existing_captures.keys())
        print(f"📊 {len(processed_captures)} capturas existentes (ya procesadas)")
    
    while True:
        try:
            # Obtener todas las capturas
            captures = ref.get()
            
            if captures:
                # Buscar nuevas capturas
                new_captures = set(captures.keys()) - processed_captures
                
                for capture_id in new_captures:
                    capture_data = captures[capture_id]
                    
                    # Verificar que tenga samples
                    if 'samples' not in capture_data:
                        continue
                    
                    print(f"\n🔍 Nueva captura detectada: {capture_id}")
                    print(f"   Sujeto: {capture_data.get('subjectId', 'unknown')}")
                    print(f"   Etiqueta real: {capture_data.get('label', 'unknown')}")
                    
                    # Extraer features
                    features = extract_all_features(capture_data['samples'])
                    
                    if features is None:
                        print("   ⚠ Error extrayendo features")
                        continue
                    
                    # Predecir
                    prediction, confidence, prob_dict = predict_capture(
                        capture_data['samples'], clf, scaler, feature_cols
                    )
                    
                    if prediction:
                        print(f"   🎯 Predicción: {prediction.upper()}")
                        print(f"   📊 Confianza: {confidence*100:.1f}%")
                        print(f"   📈 Probabilidades:")
                        for cls, prob in prob_dict.items():
                            print(f"      - {cls}: {prob*100:.1f}%")
                        
                        # Guardar predicción en Firebase
                        save_prediction_to_firebase(
                            capture_id, prediction, confidence, prob_dict, features
                        )
                    
                    # Marcar como procesada
                    processed_captures.add(capture_id)
            
            # Esperar 5 segundos antes de volver a revisar
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\n\n⚠ Monitoreo detenido por el usuario")
            break
        except Exception as e:
            print(f"❌ Error en monitoreo: {e}")
            time.sleep(10)

# ================== PREDICCIÓN DE CAPTURA ESPECÍFICA ==================
def predict_single_capture(capture_id, clf, scaler, feature_cols):
    """Predice una captura específica por su ID"""
    print(f"\n=== PREDICIENDO CAPTURA {capture_id} ===")
    
    # Obtener captura de Firebase
    ref = db.reference(f'users/2sDny0TUnwc6X8SfnU1XrL733HE3/devices/watchy-v2-01/rawdata/{capture_id}')
    capture_data = ref.get()
    
    if not capture_data:
        print("❌ Captura no encontrada")
        return
    
    if 'samples' not in capture_data:
        print("❌ Captura no tiene samples")
        return
    
    print(f"Sujeto: {capture_data.get('subjectId', 'unknown')}")
    print(f"Etiqueta real: {capture_data.get('label', 'unknown')}")
    print(f"Contexto: {capture_data.get('activityContext', 'unknown')}")
    
    # Extraer features y predecir
    features = extract_all_features(capture_data['samples'])
    
    if features:
        prediction, confidence, prob_dict = predict_capture(
            capture_data['samples'], clf, scaler, feature_cols
        )
        
        if prediction:
            print(f"\n🎯 Predicción: {prediction.upper()}")
            print(f"📊 Confianza: {confidence*100:.1f}%")
            print(f"\n📈 Probabilidades por clase:")
            for cls, prob in prob_dict.items():
                bar = '█' * int(prob * 50)
                print(f"   {cls:8s} [{bar:<50s}] {prob*100:5.1f}%")
            
            # Guardar
            save_prediction_to_firebase(
                capture_id, prediction, confidence, prob_dict, features
            )

# ================== BATCH PREDICTION ==================
def predict_all_existing_captures(clf, scaler, feature_cols):
    """Predice todas las capturas existentes en Firebase"""
    print("\n=== PREDICIENDO TODAS LAS CAPTURAS EXISTENTES ===")
    
    ref = db.reference('users/2sDny0TUnwc6X8SfnU1XrL733HE3/devices/watchy-v2-01/rawdata')
    captures = ref.get()
    
    if not captures:
        print("❌ No hay capturas en Firebase")
        return
    
    print(f"📊 Total capturas: {len(captures)}")
    
    results = []
    
    for i, (capture_id, capture_data) in enumerate(captures.items(), 1):
        if 'samples' not in capture_data:
            continue
        
        print(f"\nProcesando {i}/{len(captures)}: {capture_id}")
        
        features = extract_all_features(capture_data['samples'])
        
        if features:
            prediction, confidence, prob_dict = predict_capture(
                capture_data['samples'], clf, scaler, feature_cols
            )
            
            if prediction:
                real_label = capture_data.get('label', 'unknown')
                correct = '✓' if prediction == real_label else '✗'
                
                print(f"   Real: {real_label:8s} | Predicho: {prediction:8s} {correct}")
                print(f"   Confianza: {confidence*100:.1f}%")
                
                results.append({
                    'captureId': capture_id,
                    'real': real_label,
                    'predicted': prediction,
                    'correct': prediction == real_label,
                    'confidence': confidence
                })
                
                # Guardar predicción
                save_prediction_to_firebase(
                    capture_id, prediction, confidence, prob_dict, features
                )
    
    # Resumen
    if results:
        df = pd.DataFrame(results)
        accuracy = df['correct'].mean()
        print(f"\n{'='*50}")
        print(f"RESUMEN:")
        print(f"Total procesadas: {len(results)}")
        print(f"Accuracy: {accuracy*100:.1f}%")
        print(f"\nPor clase:")
        print(df.groupby('real')['correct'].agg(['count', 'sum', 'mean']))

# ================== MAIN ==================
if __name__ == '__main__':
    import sys
    
    # Inicializar Firebase
    initialize_firebase()
    
    # Cargar modelo
    clf, scaler = load_model()
    
    if clf is None:
        sys.exit(1)
    
    # Obtener feature columns del modelo
    # Cargar dataset de ejemplo para saber las columnas
    try:
        df = pd.read_csv('tremor_fog_dataset.csv')
        metadata_cols = ['captureId', 'label', 'subjectId', 'activityContext', 
                         'captureDate', 'timestamp', 'sampleRate', 'duration', 'numSamples']
        feature_cols = [col for col in df.columns if col not in metadata_cols]
        print(f"✓ {len(feature_cols)} features cargadas")
    except FileNotFoundError:
        print("❌ No se encontró tremor_fog_dataset.csv")
        sys.exit(1)
    
    # Menú
    print("\n" + "="*50)
    print("SISTEMA DE PREDICCIÓN EN TIEMPO REAL")
    print("="*50)
    print("\nOpciones:")
    print("1. Monitorear capturas nuevas (tiempo real)")
    print("2. Predecir captura específica")
    print("3. Predecir todas las capturas existentes")
    print("4. Salir")
    
    while True:
        choice = input("\nSelecciona opción (1-4): ").strip()
        
        if choice == '1':
            monitor_new_captures(clf, scaler, feature_cols)
        elif choice == '2':
            capture_id = input("Ingresa el ID de la captura: ").strip()
            predict_single_capture(capture_id, clf, scaler, feature_cols)
        elif choice == '3':
            predict_all_existing_captures(clf, scaler, feature_cols)
        elif choice == '4':
            print("Saliendo...")
            break
        else:
            print("Opción inválida")