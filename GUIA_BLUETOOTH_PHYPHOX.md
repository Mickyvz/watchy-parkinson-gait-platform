# 📱 Guía Completa: Watchy + Bluetooth + Phyphox

## 🎯 Cómo Funciona

```
Watchy (Bluetooth LE)
    ↓
Phyphox (Tu Celular)
    ↓
Visualización en Tiempo Real
    ↓
Exportar → Firebase/CSV
```

---

## 📋 PASO 1: Configurar el Watchy

### **1.1 Subir el Código**

1. Descarga: `watchy_bluetooth_phyphox.ino`
2. Abre Arduino IDE
3. **IMPORTANTE:** Asegúrate de tener:
   - `Erase All Flash Before Sketch Upload: Disabled`
4. Sube el código al Watchy

### **1.2 Verificar en Serial Monitor**

Debes ver:
```
========================================
   WATCHY BLUETOOTH + PHYPHOX V4.0
   [Transmisión BLE Activa]
========================================

[1/9] Inicializando I2C...
      ✓ I2C OK
[2/9] Inicializando RTC...
      ✓ RTC OK - Hora: 16:45
[3/9] Inicializando Display...
      ✓ Display OK
[4/9] Limpiando pantalla...
      ✓ Pantalla limpia
[5/9] Inicializando Bluetooth LE...
      - Creando dispositivo BLE...
      - Creando servidor BLE...
      - Creando servicio...
      - Creando características...
      - Iniciando servicio...
      - Iniciando advertising...
      ✓ Bluetooth LE activo
      ✓ Nombre: Watchy-Steps

========================================
   *** SISTEMA LISTO - MODO BLE ***
========================================
Dispositivo: Watchy-Steps
Bluetooth:   ✓ Activo y visible
Sensor:      ✓ Activo

>>> ABRE PHYPHOX Y CONECTA <<<
>>> Busca: Watchy-Steps <<<
```

✅ **Si ves esto, el Bluetooth está funcionando**

---

## 📱 PASO 2: Configurar Phyphox

### **2.1 Descargar Phyphox**

**Android:**
- Google Play Store: https://play.google.com/store/apps/details?id=de.rwth_aachen.phyphox
- O busca: "phyphox"

**iOS:**
- App Store: https://apps.apple.com/app/phyphox/id1127319693
- O busca: "phyphox"

### **2.2 Conectar al Watchy**

1. **Abre phyphox** en tu celular
2. Toca el menú **"⋮"** (tres puntos)
3. Selecciona **"Bluetooth LE"**
4. Busca **"Watchy-Steps"** en la lista
5. Toca para conectar

### **2.3 Verificar Conexión**

En el Serial Monitor del Watchy verás:
```
📱 Cliente conectado!
```

En la pantalla del Watchy verás:
```
BLE
Conectado
```

---

## 📊 PASO 3: Ver Datos en Phyphox

### **Opción A: Crear Experimento Personalizado**

Phyphox puede mostrar los datos del Watchy en tiempo real.

**Pasos:**
1. En phyphox, ve a **"+"** (Nuevo experimento)
2. Selecciona **"Bluetooth LE"**
3. Conecta a **"Watchy-Steps"**
4. Configurar características:
   - **UUID del Servicio:** `4fafc201-1fb5-459e-8fcc-c5c9c331914b`
   - **Características disponibles:**
     - Pasos: `beb5483e-36e1-4688-b7f5-ea07361b26a8`
     - Calorías: `beb5483e-36e1-4688-b7f5-ea07361b26a9`
     - Distancia: `beb5483e-36e1-4688-b7f5-ea07361b26aa`

### **Opción B: Usar Experimento Simple**

1. En phyphox, selecciona **"Bluetooth"**
2. Busca dispositivos
3. Conecta a **"Watchy-Steps"**
4. Los datos aparecerán automáticamente

---

## 📤 PASO 4: Exportar Datos desde Phyphox

### **4.1 Exportar Datos en Phyphox**

1. **Mientras está conectado:**
   - Toca el botón **"⋮"** (opciones)
   - Selecciona **"Exportar datos"**
   - Elige formato:
     - **CSV** - Para Excel/Google Sheets
     - **JSON** - Para programas personalizados
     - **Excel** - Formato .xlsx directo

2. **Compartir:**
   - Email
   - Google Drive
   - Dropbox
   - Cualquier app

### **4.2 Subir a Firebase (Manual)**

**Método 1: Desde Phyphox**
1. Exporta como **JSON**
2. Copia el contenido
3. Ve a Firebase Console
4. Realtime Database → Importar datos
5. Pega el JSON

**Método 2: Desde el Watchy (USB)**
1. Conecta Watchy por USB
2. Abre Serial Monitor
3. Escribe: `exportar`
4. Copia el JSON que aparece
5. Pégalo en Firebase

---

## 🔧 Comandos Disponibles (Serial Monitor)

Mientras el Watchy está conectado por USB:

```
estado   - Ver estado de conexión y datos guardados
exportar - Exportar todos los datos en formato JSON
limpiar  - Borrar datos guardados localmente
ayuda    - Ver lista de comandos
```

### **Ejemplo de Exportación:**

Escribe `exportar` y obtendrás:
```json
{
  "data": [
    {
      "fecha": "2025-01-04",
      "hora": "16:50",
      "pasos": 1250,
      "calorias": 50.00,
      "distancia": 881.25
    },
    ...
  ]
}
```

---

## 📊 Cómo Funcionan los Datos

### **Transmisión Bluetooth:**
- **Cada 5 segundos** el Watchy envía:
  - Contador de pasos actual
  - Calorías quemadas
  - Distancia recorrida

### **Almacenamiento Local:**
- Guarda **hasta 50 registros** en la memoria del Watchy
- Incluso si no hay conexión Bluetooth
- Los datos NO se pierden al desconectar

### **Formato de Datos:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| Pasos | uint32 (4 bytes) | Número total de pasos |
| Calorías | float (4 bytes) | Calorías quemadas |
| Distancia | float (4 bytes) | Metros recorridos |

---

## 🔋 Ahorro de Energía

### **Modo Autónomo:**
Si desconectas el USB:
- El Watchy seguirá contando pasos
- Bluetooth permanece activo
- Después de **5 minutos sin actividad** → Deep Sleep
- Para despertar: Mueve el Watchy o presiona botón

### **Consumo de Batería:**
- **Con Bluetooth activo:** ~2-3 días
- **Sin conexión activa:** ~3-4 días
- **En Deep Sleep:** Varios días

---

## 🎯 Flujo de Trabajo Recomendado

### **Opción 1: Uso Diario con Celular**
```
1. Enciende el Watchy
2. Abre phyphox y conecta
3. Camina normalmente
4. Los datos se guardan en tiempo real
5. Al final del día: Exportar desde phyphox
6. Subir a Firebase si quieres
```

### **Opción 2: Uso Autónomo (Sin Celular)**
```
1. Enciende el Watchy
2. Camina normalmente (sin celular)
3. Datos se guardan localmente (50 registros)
4. Al regresar: Conecta USB
5. Escribe 'exportar' en Serial
6. Copia y pega en Firebase
7. Escribe 'limpiar' para vaciar memoria
```

---

## 🆘 Solución de Problemas

### **Problema: No aparece "Watchy-Steps" en phyphox**

**Soluciones:**
1. Verifica que el Bluetooth del celular esté encendido
2. Cierra y abre phyphox
3. En Serial Monitor, verifica que diga "Bluetooth LE activo"
4. Reinicia el Watchy (desconecta y conecta)

### **Problema: "Cliente desconectado" constantemente**

**Causas:**
- Distancia muy grande (>10 metros)
- Obstáculos metálicos entre Watchy y celular
- Batería baja del Watchy

**Solución:**
- Acércate más al celular
- Evita obstáculos
- Carga el Watchy

### **Problema: Los datos no se actualizan**

**Solución:**
1. Camina más (el sensor necesita movimiento)
2. Verifica en Serial que los pasos cambien
3. Reconecta el Bluetooth en phyphox

### **Problema: "Almacenamiento lleno"**

**Solución:**
1. Conecta por USB
2. Escribe `exportar` para guardar los datos
3. Escribe `limpiar` para vaciar la memoria
4. Ya puedes seguir usando el Watchy

---

## 📱 Alternativa: Usar App BLE Scanner

Si phyphox no funciona bien, puedes usar apps más simples:

### **Android:**
- **nRF Connect** (Nordic Semiconductor)
- **BLE Scanner**

### **iOS:**
- **LightBlue**
- **BLE Scanner**

**Ventaja:** Más simples, solo leen los datos  
**Desventaja:** No grafican ni exportan automáticamente

---

## 🎓 Conceptos Técnicos

### **¿Qué es Bluetooth LE (BLE)?**
- Bluetooth de Baja Energía
- Consume muy poca batería
- Alcance: ~10-30 metros
- Perfecto para wearables

### **¿Qué son las Características (Characteristics)?**
Son "canales" de datos en BLE:
- **Característica de Pasos:** Transmite el contador
- **Característica de Calorías:** Transmite las kcal
- **Característica de Distancia:** Transmite los metros

### **¿Qué es un UUID?**
Identificador único para el servicio BLE del Watchy:
- Permite que phyphox encuentre el dispositivo correcto
- Es como una "dirección" única

---

## 🚀 Próximos Pasos Opcionales

### **1. Crear Script Automático**
Te puedo crear un script Python que:
- Lee datos de phyphox automáticamente
- Los sube a Firebase sin copiar/pegar
- Se ejecuta en segundo plano

### **2. Crear App Personalizada**
Puedes crear tu propia app que:
- Se conecte al Watchy directamente
- Muestre los datos en tu diseño
- Suba a Firebase automáticamente

### **3. Integración con Google Fit**
Los datos exportados de phyphox se pueden importar a Google Fit.

---

## ✅ Checklist de Configuración Inicial

- [ ] Código subido al Watchy
- [ ] Bluetooth activo (verificar en Serial Monitor)
- [ ] Phyphox instalado en el celular
- [ ] "Watchy-Steps" visible en phyphox
- [ ] Conexión establecida exitosamente
- [ ] Datos actualizándose cada 5 segundos
- [ ] Probado comando `exportar` funciona

---

## 📊 Comparación: Bluetooth vs WiFi

| Aspecto | Bluetooth LE | WiFi (Anterior) |
|---------|--------------|-----------------|
| **Consumo** | Bajo | Alto |
| **Alcance** | ~10m | ~50m |
| **Requiere** | Celular cerca | Router |
| **Conexión** | Siempre | Solo en rango |
| **Complejidad** | Simple | Compleja |
| **Confiabilidad** | Alta | Problemas (en tu caso) |

---

## 💡 Tips y Trucos

1. **Mantén el celular cerca** durante el día para transmisión continua
2. **Exporta datos semanalmente** para no llenar la memoria
3. **Usa modo autónomo** si no necesitas datos en tiempo real
4. **Revisa el estado** con el comando `estado` regularmente
5. **Limpia la memoria** después de exportar con `limpiar`

---

## 🎯 Resultado Final

Con esta configuración tendrás:

✅ **Watchy funcionando sin WiFi**  
✅ **Datos en tiempo real en tu celular**  
✅ **Exportación fácil a Firebase**  
✅ **Respaldo local de 50 registros**  
✅ **Bajo consumo de batería**  
✅ **Sistema confiable y simple**

---

## 🆘 Soporte

Si tienes problemas:

1. **Verifica Serial Monitor** - Todos los mensajes importantes aparecen ahí
2. **Escribe `estado`** - Te dice exactamente qué está pasando
3. **Reinicia el Watchy** - Muchos problemas se solucionan con un restart
4. **Contacta** - Envíame el output del Serial Monitor completo

---

¿Listo para probarlo? 🚀

**Siguiente paso:** Sube el código y prueba conectar con phyphox!
