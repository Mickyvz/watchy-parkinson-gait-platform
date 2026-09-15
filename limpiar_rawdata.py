import firebase_admin
from firebase_admin import credentials, db

# 1. Ruta a tu archivo JSON de cuenta de servicio
cred = credentials.Certificate(
    r"C:\Users\Michi\Documents\Plataforma de Enfermedad de Parkinson\watchy-e7e51-firebase-adminsdk-fbsvc-000cba4f90.json"
)

# 2. Inicializar la app con la URL de tu Realtime Database
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://watchy-e7e51-default-rtdb.firebaseio.com"
})

# 3. Ruta al nodo rawdata
path = "users/2sDny0TUnwc6X8SfnU1XrL733HE3/devices/watchy-v2-01/rawdata"
ref = db.reference(path)

data = ref.get()

if data is None:
    print(f"No hay datos en {path}")
else:
    # data es un dict: { id1: {...}, id2: {...}, ... }
    keys = list(data.keys())
    total = len(keys)
    print(f"Se encontraron {total} registros en {path}")

    batch_size = 20  # puedes subir o bajar este número

    for i in range(0, total, batch_size):
        batch = keys[i:i + batch_size]
        print(f"Eliminando batch {i//batch_size + 1} con {len(batch)} registros...")

        # Construimos un diccionario de actualizaciones a null (delete)
        updates = {k: None for k in batch}

        # Esto borra solo estos hijos en un request
        ref.update(updates)

    print(f"Todos los registros de '{path}' fueron eliminados por lotes.")
