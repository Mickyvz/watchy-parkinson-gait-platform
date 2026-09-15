#include <Watchy.h>
#include "settings.h"
#include <bma.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <Preferences.h>

// ========== CONFIGURACIÓN BLUETOOTH ==========
#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHAR_PASOS_UUID     "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define CHAR_CALORIAS_UUID  "beb5483e-36e1-4688-b7f5-ea07361b26a9"
#define CHAR_DISTANCIA_UUID "beb5483e-36e1-4688-b7f5-ea07361b26aa"
#define DEVICE_NAME         "Watchy-Steps"

// ========== CONFIGURACIÓN DE DATOS ==========
#define MAX_DATOS_COLA 50

watchySettings settings;
Preferences preferences;

BLEServer* pServer = NULL;
BLECharacteristic* pCharPasos = NULL;
BLECharacteristic* pCharCalorias = NULL;
BLECharacteristic* pCharDistancia = NULL;
bool deviceConnected = false;
bool oldDeviceConnected = false;

struct DatosPendientes {
  uint32_t pasos;
  float calorias;
  float distancia;
  uint32_t timestamp;
  char fecha[11];
  char hora[6];
};

class ServerCallbacks: public BLEServerCallbacks {
  void onConnect(BLEServer* pServer) {
    deviceConnected = true;
    Serial.println("📱 Cliente conectado!");
  }

  void onDisconnect(BLEServer* pServer) {
    deviceConnected = false;
    Serial.println("📱 Cliente desconectado");
  }
};

class StepBluetooth : public Watchy {
private:
  const float PESO_KG = 52.0;
  const float ALTURA_CM = 170.0;
  const float CALORIAS_POR_PASO = 0.04;
  
  unsigned long ultimoEnvio = 0;
  const unsigned long INTERVALO_ENVIO = 5000;  // Enviar cada 5 segundos
  uint32_t pasosUltimoEnvio = 0;
  unsigned long ultimaVerificacionSensor = 0;
  
  bool modoAutonomo = false;
  unsigned long tiempoUltimaActividad = 0;
  const unsigned long TIMEOUT_DEEP_SLEEP = 300000;
  
  DatosPendientes datosGuardados[MAX_DATOS_COLA];
  int indiceDatos = 0;
  
  uint32_t pasosPrevios = 0;
  unsigned long ultimaActualizacionPantalla = 0;
  
public:
  StepBluetooth() : Watchy(settings) {}
  
  void init() {
    Serial.begin(115200);
    delay(2000);
    
    Serial.println("\n\n========================================");
    Serial.println("   WATCHY BLUETOOTH + PHYPHOX V4.0");
    Serial.println("   [Transmisión BLE Activa]");
    Serial.println("========================================\n");
    
    preferences.begin("watchy-ble", false);
    
    Serial.println("[1/9] Inicializando I2C...");
    Wire.begin(SDA, SCL);
    Wire.setClock(400000);
    Serial.println("      ✓ I2C OK");
    
    Serial.println("[2/9] Inicializando RTC...");
    RTC.init();
    tmElements_t tm;
    RTC.read(tm);
    Serial.print("      ✓ RTC OK - Hora: ");
    Serial.print(tm.Hour);
    Serial.print(":");
    Serial.println(tm.Minute);
    
    Serial.println("[3/9] Inicializando Display...");
    display.init(0, false);
    display.setRotation(0);
    Serial.println("      ✓ Display OK");
    
    Serial.println("[4/9] Limpiando pantalla...");
    display.setFullWindow();
    display.fillScreen(GxEPD_BLACK);
    display.display(false);
    delay(500);
    display.fillScreen(GxEPD_WHITE);
    display.display(false);
    delay(500);
    Serial.println("      ✓ Pantalla limpia");
    
    detectarModoOperacion();
    
    Serial.println("[5/9] Inicializando Bluetooth LE...");
    inicializarBluetooth();
    
    Serial.println("[6/9] Mostrando pantalla de inicio...");
    mostrarPantallaInicio();
    
    Serial.println("[7/9] Inicializando sensor BMA423...");
    if (!inicializarSensor()) {
      Serial.println("      ✗ ERROR CRÍTICO: Sensor falló");
      mostrarError("Sensor Error");
      while(1) delay(1000);
    }
    Serial.println("      ✓ Sensor BMA423 OK");
    
    Serial.println("[8/9] Reseteando contador de pasos...");
    sensor.resetStepCounter();
    delay(200);
    uint32_t pasosIniciales = sensor.getCounter();
    Serial.print("      ✓ Pasos iniciales: ");
    Serial.println(pasosIniciales);
    pasosPrevios = pasosIniciales;
    
    Serial.println("[9/9] Cargando datos guardados...");
    cargarDatos();
    
    Serial.println("\n========================================");
    Serial.println("   *** SISTEMA LISTO - MODO BLE ***");
    Serial.println("========================================");
    Serial.println("Dispositivo: " + String(DEVICE_NAME));
    Serial.println("Bluetooth:   ✓ Activo y visible");
    Serial.println("Sensor:      ✓ Activo");
    Serial.print("Datos:       ");
    Serial.print(indiceDatos);
    Serial.println(" registros guardados");
    Serial.println("\n>>> ABRE PHYPHOX Y CONECTA <<<");
    Serial.println(">>> Busca: " + String(DEVICE_NAME) + " <<<");
    Serial.println(">>> Comandos: 'estado', 'exportar', 'ayuda' <<<\n");
    
    mostrarPantalla(pasosIniciales);
    ultimaActualizacionPantalla = millis();
    ultimoEnvio = millis();
  }
  
  void inicializarBluetooth() {
    Serial.println("      - Creando dispositivo BLE...");
    BLEDevice::init(DEVICE_NAME);
    
    Serial.println("      - Creando servidor BLE...");
    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new ServerCallbacks());
    
    Serial.println("      - Creando servicio...");
    BLEService *pService = pServer->createService(SERVICE_UUID);
    
    Serial.println("      - Creando características...");
    
    // Característica de Pasos
    pCharPasos = pService->createCharacteristic(
                      CHAR_PASOS_UUID,
                      BLECharacteristic::PROPERTY_READ |
                      BLECharacteristic::PROPERTY_NOTIFY
                    );
    pCharPasos->addDescriptor(new BLE2902());
    
    // Característica de Calorías
    pCharCalorias = pService->createCharacteristic(
                      CHAR_CALORIAS_UUID,
                      BLECharacteristic::PROPERTY_READ |
                      BLECharacteristic::PROPERTY_NOTIFY
                    );
    pCharCalorias->addDescriptor(new BLE2902());
    
    // Característica de Distancia
    pCharDistancia = pService->createCharacteristic(
                      CHAR_DISTANCIA_UUID,
                      BLECharacteristic::PROPERTY_READ |
                      BLECharacteristic::PROPERTY_NOTIFY
                    );
    pCharDistancia->addDescriptor(new BLE2902());
    
    Serial.println("      - Iniciando servicio...");
    pService->start();
    
    Serial.println("      - Iniciando advertising...");
    BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->setScanResponse(true);
    pAdvertising->setMinPreferred(0x06);
    pAdvertising->setMinPreferred(0x12);
    BLEDevice::startAdvertising();
    
    Serial.println("      ✓ Bluetooth LE activo");
    Serial.print("      ✓ Nombre: ");
    Serial.println(DEVICE_NAME);
  }
  
  void detectarModoOperacion() {
    if (Serial) {
      modoAutonomo = false;
      Serial.println("      🔌 Modo USB detectado");
    } else {
      modoAutonomo = true;
    }
  }
  
  bool inicializarSensor() {
    Serial.println("      - Verificando comunicación I2C...");
    Wire.beginTransmission(BMA4_I2C_ADDR_PRIMARY);
    if (Wire.endTransmission() != 0) {
      Serial.println("      ✗ No se detecta BMA423 en I2C");
      return false;
    }
    Serial.println("      ✓ BMA423 detectado en I2C");
    
    Serial.println("      - Inicializando BMA423...");
    if (!sensor.begin(readRegister, writeRegister, delayCallback, BMA4_I2C_ADDR_PRIMARY)) {
      Serial.println("      ✗ sensor.begin() falló");
      return false;
    }
    Serial.println("      ✓ sensor.begin() OK");
    delay(100);
    
    Serial.println("      - Habilitando acelerómetro...");
    if (!sensor.enableAccel(true)) {
      Serial.println("      ✗ No se pudo habilitar acelerómetro");
      return false;
    }
    Serial.println("      ✓ Acelerómetro habilitado");
    delay(100);
    
    Serial.println("      - Configurando parámetros...");
    Acfg cfg;
    cfg.odr = BMA4_OUTPUT_DATA_RATE_100HZ;
    cfg.range = BMA4_ACCEL_RANGE_2G;
    cfg.bandwidth = BMA4_ACCEL_NORMAL_AVG4;
    cfg.perf_mode = BMA4_CONTINUOUS_MODE;
    
    if (!sensor.setAccelConfig(cfg)) {
      Serial.println("      ✗ No se pudo configurar acelerómetro");
      return false;
    }
    Serial.println("      ✓ Configuración aplicada");
    delay(100);
    
    Serial.println("      - Habilitando contador de pasos...");
    if (!sensor.enableFeature(BMA423_STEP_CNTR, true)) {
      Serial.println("      ✗ No se pudo habilitar contador");
      return false;
    }
    Serial.println("      ✓ Contador de pasos habilitado");
    
    sensor.enableStepCountInterrupt(false);
    return true;
  }
  
  void mantenerSensorActivo() {
    bool accelEnabled = sensor.getAccelEnable();
    
    if (!accelEnabled) {
      Serial.println("⚠ Acelerómetro deshabilitado - Reactivando...");
      
      sensor.enableAccel(true);
      delay(100);
      
      Acfg cfg;
      cfg.odr = BMA4_OUTPUT_DATA_RATE_100HZ;
      cfg.range = BMA4_ACCEL_RANGE_2G;
      cfg.bandwidth = BMA4_ACCEL_NORMAL_AVG4;
      cfg.perf_mode = BMA4_CONTINUOUS_MODE;
      sensor.setAccelConfig(cfg);
      delay(50);
      
      sensor.enableFeature(BMA423_STEP_CNTR, true);
      delay(50);
      
      Serial.println("✓ Sensor reactivado");
    }
  }
  
  void mostrarPantallaInicio() {
    display.setFullWindow();
    display.firstPage();
    do {
      display.fillScreen(GxEPD_WHITE);
      display.setTextColor(GxEPD_BLACK);
      display.setFont(NULL);
      
      display.setCursor(40, 60);
      display.setTextSize(2);
      display.println("WATCHY");
      
      display.setCursor(20, 90);
      display.setTextSize(1);
      display.println("Bluetooth V4.0");
      
      display.setCursor(30, 110);
      display.println("Phyphox Ready");
      
      display.setCursor(15, 140);
      display.println("Iniciando...");
      
    } while (display.nextPage());
    
    delay(2000);
  }
  
  float calcularCalorias(uint32_t pasos) {
    return pasos * CALORIAS_POR_PASO;
  }
  
  float calcularDistancia(uint32_t pasos) {
    float longitudPaso = ALTURA_CM * 0.415;
    return (pasos * longitudPaso) / 100.0;
  }
  
  void enviarDatosBluetooth(uint32_t pasos, float calorias, float distancia) {
    if (!deviceConnected) {
      return;
    }
    
    // Enviar pasos como uint32_t (4 bytes)
    pCharPasos->setValue(pasos);
    pCharPasos->notify();
    
    // Enviar calorías como float (4 bytes)
    pCharCalorias->setValue(calorias);
    pCharCalorias->notify();
    
    // Enviar distancia como float (4 bytes)
    pCharDistancia->setValue(distancia);
    pCharDistancia->notify();
    
    Serial.print("📤 BLE → Pasos: ");
    Serial.print(pasos);
    Serial.print(" | Cal: ");
    Serial.print(calorias, 1);
    Serial.print(" | Dist: ");
    Serial.print(distancia, 0);
    Serial.println("m");
  }
  
  void agregarDato(uint32_t pasos, float calorias, float distancia) {
    if (indiceDatos >= MAX_DATOS_COLA) {
      Serial.println("⚠ Almacenamiento lleno");
      for (int i = 0; i < MAX_DATOS_COLA - 1; i++) {
        datosGuardados[i] = datosGuardados[i + 1];
      }
      indiceDatos = MAX_DATOS_COLA - 1;
    }
    
    tmElements_t tm;
    RTC.read(tm);
    
    sprintf(datosGuardados[indiceDatos].fecha, "%04d-%02d-%02d", 
            tm.Year + 1970, tm.Month, tm.Day);
    sprintf(datosGuardados[indiceDatos].hora, "%02d:%02d", tm.Hour, tm.Minute);
    
    datosGuardados[indiceDatos].pasos = pasos;
    datosGuardados[indiceDatos].calorias = calorias;
    datosGuardados[indiceDatos].distancia = distancia;
    datosGuardados[indiceDatos].timestamp = millis() / 1000;
    
    indiceDatos++;
    guardarDatos();
  }
  
  void guardarDatos() {
    preferences.putInt("indiceDatos", indiceDatos);
    for (int i = 0; i < indiceDatos && i < MAX_DATOS_COLA; i++) {
      String key = "dato_" + String(i);
      preferences.putBytes(key.c_str(), &datosGuardados[i], sizeof(DatosPendientes));
    }
  }
  
  void cargarDatos() {
    indiceDatos = preferences.getInt("indiceDatos", 0);
    if (indiceDatos > 0) {
      Serial.print("      Cargando ");
      Serial.print(indiceDatos);
      Serial.println(" datos...");
      
      for (int i = 0; i < indiceDatos && i < MAX_DATOS_COLA; i++) {
        String key = "dato_" + String(i);
        preferences.getBytes(key.c_str(), &datosGuardados[i], sizeof(DatosPendientes));
      }
      
      Serial.println("      ✓ Datos cargados");
    }
  }
  
  void limpiarDatos() {
    Serial.println("\n🗑️  Limpiando datos...");
    indiceDatos = 0;
    guardarDatos();
    Serial.println("✓ Datos eliminados");
  }
  
  void exportarDatos() {
    if (indiceDatos == 0) {
      Serial.println("\n⚠️  No hay datos");
      return;
    }
    
    Serial.println("\n// ========== DATOS JSON ==========");
    Serial.println("{\"data\":[");
    
    for (int i = 0; i < indiceDatos; i++) {
      Serial.print("{\"fecha\":\"");
      Serial.print(datosGuardados[i].fecha);
      Serial.print("\",\"hora\":\"");
      Serial.print(datosGuardados[i].hora);
      Serial.print("\",\"pasos\":");
      Serial.print(datosGuardados[i].pasos);
      Serial.print(",\"calorias\":");
      Serial.print(datosGuardados[i].calorias, 2);
      Serial.print(",\"distancia\":");
      Serial.print(datosGuardados[i].distancia, 2);
      Serial.print("}");
      
      if (i < indiceDatos - 1) {
        Serial.println(",");
      }
    }
    
    Serial.println("\n]}");
    Serial.println("// ========== FIN ==========\n");
  }
  
  static uint16_t readRegister(uint8_t address, uint8_t reg, uint8_t *data, uint16_t len) {
    Wire.beginTransmission(address);
    Wire.write(reg);
    Wire.endTransmission();
    Wire.requestFrom((uint8_t)address, (uint8_t)len);
    uint8_t i = 0;
    while (Wire.available()) {
      data[i++] = Wire.read();
    }
    return 0;
  }
  
  static uint16_t writeRegister(uint8_t address, uint8_t reg, uint8_t *data, uint16_t len) {
    Wire.beginTransmission(address);
    Wire.write(reg);
    Wire.write(data, len);
    return (0 != Wire.endTransmission());
  }
  
  static void delayCallback(uint32_t period) {
    delay(period);
  }
  
  void procesarComandosSerial() {
    if (Serial.available()) {
      String comando = Serial.readStringUntil('\n');
      comando.trim();
      comando.toLowerCase();
      
      if (comando == "estado" || comando == "status") {
        mostrarEstado();
      } else if (comando == "exportar" || comando == "export") {
        exportarDatos();
      } else if (comando == "limpiar" || comando == "clear") {
        limpiarDatos();
      } else if (comando == "ayuda" || comando == "help") {
        Serial.println("\n📖 COMANDOS:");
        Serial.println("═══════════════════════════");
        Serial.println("  estado   - Ver estado");
        Serial.println("  exportar - Exportar JSON");
        Serial.println("  limpiar  - Borrar datos");
        Serial.println("  ayuda    - Esta ayuda");
        Serial.println("═══════════════════════════");
      }
    }
  }
  
  void mostrarEstado() {
    Serial.println("\n📊 ESTADO:");
    Serial.println("═══════════════════════════");
    Serial.print("Bluetooth: ");
    Serial.println(deviceConnected ? "✓ Conectado" : "⊘ Sin conexión");
    Serial.print("Datos:     ");
    Serial.print(indiceDatos);
    Serial.print("/");
    Serial.print(MAX_DATOS_COLA);
    Serial.println(" registros");
    Serial.print("Pasos:     ");
    Serial.println(sensor.getCounter());
    Serial.println("═══════════════════════════");
  }
  
  void actualizar() {
    procesarComandosSerial();
    
    // Manejar reconexión BLE
    if (!deviceConnected && oldDeviceConnected) {
      delay(500);
      pServer->startAdvertising();
      Serial.println("📱 Esperando conexión...");
      oldDeviceConnected = deviceConnected;
    }
    
    if (deviceConnected && !oldDeviceConnected) {
      oldDeviceConnected = deviceConnected;
    }
    
    if (millis() - ultimaVerificacionSensor > 30000) {
      mantenerSensorActivo();
      ultimaVerificacionSensor = millis();
    }
    
    uint32_t pasosActuales = sensor.getCounter();
    
    if (pasosActuales != pasosPrevios) {
      tiempoUltimaActividad = millis();
      
      float calorias = calcularCalorias(pasosActuales);
      float distancia = calcularDistancia(pasosActuales);
      
      Serial.println("\n╔═══════════════════════╗");
      Serial.print("║ PASOS: ");
      Serial.println(pasosActuales);
      Serial.print("║ CAL: ");
      Serial.print(calorias, 1);
      Serial.print(" | DIST: ");
      Serial.print(distancia, 0);
      Serial.println("m");
      Serial.println("╚═══════════════════════╝");
      
      pasosPrevios = pasosActuales;
      mostrarPantalla(pasosActuales);
      ultimaActualizacionPantalla = millis();
    }
    
    // Enviar por Bluetooth cada 5 segundos
    if (millis() - ultimoEnvio >= INTERVALO_ENVIO) {
      float calorias = calcularCalorias(pasosActuales);
      float distancia = calcularDistancia(pasosActuales);
      
      if (deviceConnected) {
        enviarDatosBluetooth(pasosActuales, calorias, distancia);
      }
      
      agregarDato(pasosActuales, calorias, distancia);
      ultimoEnvio = millis();
    }
    
    if (millis() - ultimaActualizacionPantalla > 60000) {
      mostrarPantalla(pasosActuales);
      ultimaActualizacionPantalla = millis();
    }
    
    if (modoAutonomo && (millis() - tiempoUltimaActividad) > TIMEOUT_DEEP_SLEEP) {
      entrarModoAhorro();
    }
  }
  
  void entrarModoAhorro() {
    uint32_t pasosActuales = sensor.getCounter();
    preferences.putUInt("ultimos_pasos", pasosActuales);
    
    display.setFullWindow();
    display.firstPage();
    do {
      display.fillScreen(GxEPD_WHITE);
      display.setTextColor(GxEPD_BLACK);
      display.setFont(NULL);
      display.setCursor(40, 90);
      display.setTextSize(2);
      display.println("AHORRO");
    } while (display.nextPage());
    
    BLEDevice::deinit(false);
    sensor.enableStepCountInterrupt(true);
    esp_sleep_enable_ext0_wakeup(GPIO_NUM_14, 0);
    esp_deep_sleep_start();
  }
  
  void mostrarPantalla(uint32_t pasos) {
    float calorias = calcularCalorias(pasos);
    float distancia = calcularDistancia(pasos);
    
    display.setFullWindow();
    display.firstPage();
    do {
      display.fillScreen(GxEPD_WHITE);
      display.setTextColor(GxEPD_BLACK);
      display.setFont(NULL);
      
      display.drawRect(3, 3, 194, 194, GxEPD_BLACK);
      display.drawRect(5, 5, 190, 190, GxEPD_BLACK);
      
      display.setCursor(30, 20);
      display.setTextSize(2);
      display.println("BLE");
      
      display.setTextSize(1);
      display.setCursor(15, 35);
      if (deviceConnected) {
        display.print("Conectado");
      } else {
        display.print("Esperando...");
      }
      
      display.drawLine(15, 45, 185, 45, GxEPD_BLACK);
      
      display.setCursor(15, 58);
      display.println("PASOS:");
      display.setCursor(45, 75);
      display.setTextSize(4);
      display.println(pasos);
      
      display.drawLine(15, 105, 185, 105, GxEPD_BLACK);
      
      display.setCursor(15, 118);
      display.setTextSize(1);
      display.println("CALORIAS:");
      display.setCursor(40, 135);
      display.setTextSize(3);
      display.print(calorias, 1);
      display.setTextSize(1);
      display.println(" kcal");
      
      display.drawLine(15, 160, 185, 160, GxEPD_BLACK);
      
      display.setCursor(25, 172);
      display.setTextSize(1);
      display.print("Distancia: ");
      display.print(distancia, 0);
      display.println(" m");
      
    } while (display.nextPage());
  }
  
  void mostrarError(const char* mensaje) {
    display.setFullWindow();
    display.firstPage();
    do {
      display.fillScreen(GxEPD_WHITE);
      display.setTextColor(GxEPD_BLACK);
      display.setFont(NULL);
      display.setCursor(50, 80);
      display.setTextSize(2);
      display.println("ERROR");
      display.setTextSize(1);
      display.setCursor(20, 110);
      display.println(mensaje);
    } while (display.nextPage());
  }
  
  void drawWatchFace() override {}
};

StepBluetooth watchy;

void setup() {
  watchy.init();
}

void loop() {
  watchy.actualizar();
  delay(500);
}
