# Watchy Parkinson Platform

Plataforma para la detección de temblor y *freezing of gait* (FOG) en personas con
Parkinson, usando un smartwatch **Watchy** (ESP32) como sensor inercial (IMU),
Bluetooth Low Energy para la transmisión de datos y un modelo de Machine Learning
(Random Forest) para clasificar los patrones de marcha capturados.

Este proyecto es el resultado del trabajo de tesis de maestría del autor y dio
origen al artículo *"Wearable sensors for gait analysis"* (Revista Mexicana de
Ingeniería Biomédica, aceptado 2026).

> **Estado del proyecto:** funcional y probado, pero de uso local/experimental.
> No está desplegado en ningún servidor público; se ejecuta en `localhost`.

## Arquitectura

```
Watchy (ESP32, IMU)
   │  Bluetooth Low Energy
   ▼
App móvil "watchy_sync" (Flutter)  ──┐
   │                                  │  Firebase Realtime Database
   ▼                                  ▼
Phyphox (visualización en tiempo real)   Backend web (Flask)
                                           │
                                           ▼
                                  Modelo Random Forest
                                  (clasificación de marcha)
```

El repositorio contiene tres componentes:

| Componente | Tecnología | Carpeta |
|---|---|---|
| Firmware del smartwatch | Arduino / ESP32, BLE | `watchy_bluetooth_phyphox.ino` |
| App móvil de sincronización | Flutter + Firebase | `watchy_sync/` |
| Backend web + Machine Learning | Python / Flask, scikit-learn | raíz del proyecto |

## Funcionalidades del backend web

- **Login** con sesión de usuario (Flask-Login/session).
- **Dashboard** con el histórico de predicciones del usuario.
- **Visualización de datos crudos** (`/rawdata`) capturados desde Firebase.
- **Clasificación de caminatas** (`/classify_walk`, `/predict_walk`): sube un
  CSV con datos de acelerómetro/giroscopio y el modelo Random Forest predice
  el patrón de marcha (normal / temblor / FOG) junto con su nivel de confianza.
- **Clasificación de la última captura** (`/predict_last_walk`) directamente
  desde la última sesión guardada en Firebase.

## Pipeline de datos y modelo

- `create_dataset.py`, `limpiar_rawdata.py`: extracción y limpieza de datos
  crudos desde Firebase Realtime Database.
- `analyze_vibration.py`, `validacion_rpm.py`, `validation_walk.py`: scripts de
  validación de las capturas contra una mesa vibradora de referencia (RPM
  conocidos) para verificar la fidelidad del sensor.
- `train_model.py` / `train_rf.py` / `randomforest.py`: entrenamiento del
  modelo Random Forest (`rf_model.joblib`) a partir de las características
  extraídas (`features_order.json`).
- Notebooks (`prueba1.ipynb`, `prueba2.ipynb`, `validations.ipynb`): análisis
  exploratorio y validación de resultados.

## Configuración local

### 1. Backend Flask

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Copia `.env.example` a `.env` y completa tus propios valores (clave secreta de
Flask, credenciales de tu proyecto de Firebase, usuario de prueba):

```bash
copy .env.example .env
```

Coloca tu propio `serviceAccountKey.json` (descargado desde Firebase Console →
Configuración del proyecto → Cuentas de servicio) en la raíz del proyecto.
**Este archivo nunca debe subirse a git** — ya está excluido en `.gitignore`.

```bash
python app.py
```

La app quedará disponible en `http://localhost:5000`.

### 2. App móvil (`watchy_sync/`)

Proyecto Flutter estándar:

```bash
cd watchy_sync
flutter pub get
flutter run
```

Requiere su propia configuración de Firebase (`google-services.json` /
`GoogleService-Info.plist`, no incluidos en el repositorio).

### 3. Firmware del Watchy

Ver [`GUIA_BLUETOOTH_PHYPHOX.md`](GUIA_BLUETOOTH_PHYPHOX.md) para el
procedimiento completo de flasheo (Arduino IDE) y emparejamiento BLE con
Phyphox.

## Variables de entorno

Ver [`.env.example`](.env.example) para la lista completa. Ninguna credencial
real vive en el código fuente: todo se carga vía `python-dotenv`.

## Autor

Miguel Alcaraz Vázquez — proyecto desarrollado como parte de la tesis de
maestría en Ciencias de la Computación.
