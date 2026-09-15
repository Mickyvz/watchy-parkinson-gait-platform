import 'package:flutter/material.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_database/firebase_database.dart';
import 'dart:convert';
import 'dart:async';
import 'package:permission_handler/permission_handler.dart';
import 'dart:io';
import 'package:path_provider/path_provider.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:audioplayers/audioplayers.dart';

// Metadatos de pasos en la ventana de 10 s
int lastStepsInterval = 0;
int lastStepsStart = 0;
int lastStepsEnd = 0;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Watchy Sync',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF00BFA5),
          brightness: Brightness.light,
          primary: const Color(0xFF263238),
          secondary: const Color(0xFF00BFA5),
          surface: Colors.grey[50]!,
          background: Colors.grey[100]!,
        ),
        textTheme: GoogleFonts.interTextTheme(),
        appBarTheme: AppBarTheme(
          backgroundColor: Colors.white,
          elevation: 0,
          centerTitle: true,
          titleTextStyle: GoogleFonts.poppins(
            color: const Color(0xFF263238),
            fontSize: 20,
            fontWeight: FontWeight.w600,
          ),
          iconTheme: const IconThemeData(color: Color(0xFF263238)),
        ),
        cardTheme: CardThemeData(
          elevation: 2,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          color: Colors.white,
          surfaceTintColor: Colors.white,
        ),
        elevatedButtonTheme: ElevatedButtonThemeData(
          style: ElevatedButton.styleFrom(
            elevation: 0,
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
            textStyle: GoogleFonts.inter(fontWeight: FontWeight.w600),
          ),
        ),
      ),
      home: WatchySyncPage(),
    );
  }
}

class WatchySyncPage extends StatefulWidget {
  @override
  _WatchySyncPageState createState() => _WatchySyncPageState();
}

class _WatchySyncPageState extends State<WatchySyncPage> {
  BluetoothDevice? watchyDevice;
  BluetoothCharacteristic? fitnessCharacteristic;
  BluetoothCharacteristic? rawDataCharacteristic;

  final String SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b";
  final String CHAR_FITNESS_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8";
  final String CHAR_RAWDATA_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26ab";

  String status = "Desconectado";
  int steps = 0;
  double calories = 0.0;
  double distance = 0.0;

  bool isCapturing = false;
  List<Map<String, dynamic>> rawDataBuffer = [];

  // Etiquetado para dataset (marcha)
  String currentLabel = 'gait_normal';
  String subjectId = 'P001';
  String activityContext = 'walking';

  final DatabaseReference dbRef = FirebaseDatabase.instance.ref();

  // ====== AUDIO PLAYER ======
  final AudioPlayer _audioPlayer = AudioPlayer();

  Future<void> _playStartBeep() async {
    try {
      await _audioPlayer.play(
        AssetSource('sounds/start_beep.mp3'),
      );
    } catch (e) {
      print('Error reproduciendo start_beep: $e');
    }
  }

  Future<void> _playEndBeep() async {
    try {
      await _audioPlayer.play(
        AssetSource('sounds/end_beep.mp3'),
      );
    } catch (e) {
      print('Error reproduciendo end_beep: $e');
    }
  }

  @override
  void initState() {
    super.initState();
    requestPermissions();
  }

  @override
  void dispose() {
    disconnect();
    _audioPlayer.dispose();
    super.dispose();
  }

  Future<void> requestPermissions() async {
    await [
      Permission.bluetoothScan,
      Permission.bluetoothConnect,
      Permission.location,
    ].request();
  }

  // ================== SCAN ==================
  void scanForWatchy() async {
    setState(() => status = "Buscando Watchy...");

    try {
      try {
        await FlutterBluePlus.stopScan();
      } catch (_) {}

      for (var device in FlutterBluePlus.connectedDevices) {
        try {
          await device.disconnect();
        } catch (_) {}
      }

      await Future.delayed(const Duration(milliseconds: 500));

      await FlutterBluePlus.startScan(
        timeout: const Duration(seconds: 15),
        androidUsesFineLocation: true,
      );

      var subscription = FlutterBluePlus.scanResults.listen(
        (results) {
          for (ScanResult result in results) {
            String deviceName = result.device.platformName;

            if (deviceName.contains("Watchy") ||
                deviceName == "Watchy-Steps" ||
                deviceName.toLowerCase().contains("watchy")) {
              FlutterBluePlus.stopScan();
              connectToWatchy(result.device);
              return;
            }
          }
        },
        onError: (e) {
          setState(() => status = "Error en escaneo: $e");
        },
      );

      await Future.delayed(const Duration(seconds: 15));
      await FlutterBluePlus.stopScan();
      subscription.cancel();

      if (watchyDevice == null) {
        setState(() => status = "No encontrado. Reintentar.");
      }
    } catch (e) {
      setState(() => status = "Error: $e");
    }
  }

  // ================== CONEXIÓN ==================
  void connectToWatchy(BluetoothDevice device) async {
    setState(() => status = "Conectando...");

    try {
      device.connectionState.listen((state) {
        if (state == BluetoothConnectionState.disconnected) {
          if (watchyDevice != null) {
            setState(() {
              status = "Desconectado";
              watchyDevice = null;
            });
          }
        }
      });

      await device.connect(
          timeout: const Duration(seconds: 10), autoConnect: false);
      setState(() => status = "Conectado. Iniciando...");
      await Future.delayed(const Duration(seconds: 2));

      watchyDevice = device;
      setState(() => status = "Descubriendo servicios...");

      List<BluetoothService> services = await device.discoverServices();

      bool foundFitness = false;
      bool foundRawData = false;

      for (BluetoothService service in services) {
        String serviceUuid =
            service.uuid.toString().toLowerCase().replaceAll('-', '');
        String targetServiceUuid =
            SERVICE_UUID.toLowerCase().replaceAll('-', '');

        if (serviceUuid.contains(targetServiceUuid)) {
          for (BluetoothCharacteristic characteristic
              in service.characteristics) {
            String charUuid = characteristic.uuid
                .toString()
                .toLowerCase()
                .replaceAll('-', '');

            // FITNESS
            if (charUuid.contains(
                CHAR_FITNESS_UUID.toLowerCase().replaceAll('-', ''))) {
              fitnessCharacteristic = characteristic;
              foundFitness = true;
              await characteristic.setNotifyValue(true);

              characteristic.lastValueStream.listen((value) {
                if (value.isNotEmpty) {
                  try {
                    String jsonString = String.fromCharCodes(value);
                    Map<String, dynamic> data = json.decode(jsonString);
                    setState(() {
                      steps = data['steps'] ?? 0;
                      calories = (data['calories'] ?? 0.0).toDouble();
                      distance = (data['distance'] ?? 0.0).toDouble();
                      status = "Sincronizado";
                    });
                    sendToFirebase(data);
                  } catch (e) {
                    print("Error parseando JSON: $e");
                  }
                }
              });
            }

            // RAW DATA
            if (charUuid.contains(
                CHAR_RAWDATA_UUID.toLowerCase().replaceAll('-', ''))) {
              rawDataCharacteristic = characteristic;
              foundRawData = true;
              await characteristic.setNotifyValue(true);

              characteristic.lastValueStream.listen((value) async {
                if (value.isEmpty) return;

                String dataString = String.fromCharCodes(value);

                try {
                  final dynamic decoded = json.decode(dataString);

                  if (decoded is Map<String, dynamic> &&
                      decoded['event'] == 'END') {
                    // 🔹 JSON meta de fin de captura
                    lastStepsStart = decoded['steps_start'] ?? 0;
                    lastStepsEnd = decoded['steps_end'] ?? 0;
                    lastStepsInterval = decoded['steps_interval'] ?? 0;

                    await saveRawDataToCsv();
                    await saveRawDataToFirebase();

                    rawDataBuffer.clear();
                    await _playEndBeep();

                    setState(() {
                      isCapturing = false;
                      status =
                          "Captura guardada (${lastStepsInterval} pasos en 10s)";
                    });
                  } else if (decoded is Map<String, dynamic>) {
                    // 🔹 Muestra normal de raw data
                    rawDataBuffer.add(decoded);
                  }
                } catch (e) {
                  // Cualquier cosa que no sea JSON válido se ignora
                  print("Dato no-JSON en RAW: $dataString");
                }
              });
            }
          }
        }
      }

      if (!foundFitness || !foundRawData) {
        setState(() => status = "Error: Servicio no compatible");
        await device.disconnect();
        return;
      }

      setState(() => status = "Conectado y Listo");
    } catch (e) {
      setState(() => status = "Error de conexión");
      try {
        await device.disconnect();
      } catch (_) {}
      watchyDevice = null;
    }
  }

  // ================== FIREBASE STEPS ==================
  void sendToFirebase(Map<String, dynamic> data) async {
    try {
      final now = DateTime.now();
      final day =
          '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
      final bucket =
          '${now.hour.toString().padLeft(2, '0')}${(now.minute ~/ 15 * 15).toString().padLeft(2, '0')}';
      const userId = '2sDny0TUnwc6X8SfnU1XrL733HE3';
      const deviceId = 'watchy-v2-01';
      final path = 'users/$userId/devices/$deviceId/steps/$day/$bucket';

      await dbRef.child(path).set({
        'count': data['steps'] ?? 0,
        'delta': data['steps'] ?? 0,
        'calorias': data['calories'] ?? 0.0,
        'distancia': data['distance'] ?? 0.0,
        'timestamp': ServerValue.timestamp,
      });
    } catch (e) {
      print("Error Firebase: $e");
    }
  }

  // ================== FIREBASE RAW DATA ==================
  Future<void> saveRawDataToFirebase() async {
    if (rawDataBuffer.isEmpty) return;
    try {
      final now = DateTime.now();
      final timestamp = now.millisecondsSinceEpoch;
      const userId = '2sDny0TUnwc6X8SfnU1XrL733HE3';
      const deviceId = 'watchy-v2-01';
      final path = 'users/$userId/devices/$deviceId/rawdata/$timestamp';

      await dbRef.child(path).set({
        'timestamp': ServerValue.timestamp,
        'duration': 10000,
        'sampleRate': 50,
        'samples': rawDataBuffer,
        'label': currentLabel,
        'subjectId': subjectId,
        'activityContext': activityContext,
        'captureDate': now.toIso8601String(),
        // Metadatos de pasos en la ventana de 10 s
        'steps_start': lastStepsStart,
        'steps_end': lastStepsEnd,
        'steps_interval': lastStepsInterval,
      });
    } catch (e) {
      print("Error saving raw data: $e");
    }
  }

  // ================== CSV LOCAL ==================
  Future<void> saveRawDataToCsv() async {
    if (rawDataBuffer.isEmpty) return;
    try {
      final now = DateTime.now();
      final captureTs = now.millisecondsSinceEpoch;
      final fileName =
          '${subjectId}_${currentLabel}_${activityContext}_$captureTs.csv';
      final dir = await getApplicationDocumentsDirectory();
      final folder = Directory('${dir.path}/watchy_captures');
      if (!await folder.exists()) await folder.create(recursive: true);

      final file = File('${folder.path}/$fileName');
      final buffer = StringBuffer();
      buffer.writeln('t_ms,x_g,y_g,z_g,steps,label,subject,context,capture_ts');

      for (final sample in rawDataBuffer) {
        final t = sample['t'] ?? 0;
        final x = sample['x'] ?? 0.0;
        final y = sample['y'] ?? 0.0;
        final z = sample['z'] ?? 0.0;
        final s = sample['steps'] ?? 0;

        buffer.writeln(
            '$t,$x,$y,$z,$s,$currentLabel,$subjectId,$activityContext,$captureTs');
      }
      await file.writeAsString(buffer.toString());
    } catch (e) {
      print("Error saving CSV: $e");
    }
  }

  // ================== CAPTURA ==================
  void startCapture() async {
    if (rawDataCharacteristic == null) return;
    try {
      rawDataBuffer.clear();
      // Resetear metadatos de pasos para esta nueva ventana
      lastStepsStart = 0;
      lastStepsEnd = 0;
      lastStepsInterval = 0;

      setState(() {
        isCapturing = true;
        status = "Capturando datos...";
      });
      await _playStartBeep();
      await rawDataCharacteristic!.write(utf8.encode("START_CAPTURE"));
    } catch (e) {
      setState(() {
        isCapturing = false;
        status = "Error al iniciar";
      });
    }
  }

  // ================== DESCONECTAR ==================
  void disconnect() async {
    if (watchyDevice != null) {
      await watchyDevice!.disconnect();
      setState(() {
        status = "Desconectado";
        watchyDevice = null;
        fitnessCharacteristic = null;
        rawDataCharacteristic = null;
        steps = 0;
        calories = 0.0;
        distance = 0.0;
        isCapturing = false;
      });
    }
  }

  // ================== DIALOGO SUJETO ==================
  void showSubjectDialog() {
    final controller = TextEditingController(text: subjectId);
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          'ID del Sujeto',
          style: GoogleFonts.poppins(fontWeight: FontWeight.w600),
        ),
        content: TextField(
          controller: controller,
          decoration: InputDecoration(
            hintText: 'Ej: P001',
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () {
              if (controller.text.isNotEmpty) {
                setState(() => subjectId = controller.text.trim());
              }
              Navigator.pop(context);
            },
            child: const Text('Guardar'),
          ),
        ],
      ),
    );
  }

  // ================== UI ==================
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey[100],
      appBar: AppBar(
        title: const Text('Watchy Sync'),
        actions: [
          IconButton(
            icon: const Icon(Icons.person_outline),
            onPressed: showSubjectDialog,
            tooltip: 'Configurar Sujeto',
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildStatusCard(),
              const SizedBox(height: 24),
              Text(
                "Métricas en tiempo real",
                style: GoogleFonts.poppins(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: Colors.blueGrey[800],
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: _buildMetricCard(
                      'Pasos',
                      '$steps',
                      Icons.directions_walk,
                      Colors.blue,
                    ),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _buildMetricCard(
                      'Calorías',
                      '${calories.toStringAsFixed(0)}',
                      Icons.local_fire_department,
                      Colors.orange,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              _buildMetricCard(
                'Distancia',
                '${distance.toStringAsFixed(2)} m',
                Icons.straighten,
                Colors.green,
              ),
              const SizedBox(height: 32),
              Text(
                "Captura de Datos",
                style: GoogleFonts.poppins(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: Colors.blueGrey[800],
                ),
              ),
              const SizedBox(height: 16),
              _buildControlPanel(),
              const SizedBox(height: 32),
              _buildActionButtons(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatusCard() {
    bool isConnected = watchyDevice != null;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: isConnected ? const Color(0xFFE0F2F1) : Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: isConnected ? const Color(0xFF00BFA5) : Colors.grey[300]!,
          width: 1,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.05),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: isConnected ? const Color(0xFF00BFA5) : Colors.grey[200],
              shape: BoxShape.circle,
            ),
            child: Icon(
              isConnected
                  ? Icons.bluetooth_connected
                  : Icons.bluetooth_disabled,
              color: isConnected ? Colors.white : Colors.grey[500],
              size: 24,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isConnected ? "Conectado" : "Desconectado",
                  style: GoogleFonts.poppins(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                    color: isConnected
                        ? const Color(0xFF00695C)
                        : Colors.grey[700],
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  status,
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    color: Colors.grey[600],
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMetricCard(
      String title, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 20),
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: GoogleFonts.poppins(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: Colors.blueGrey[900],
            ),
          ),
          Text(
            title,
            style: GoogleFonts.inter(
              fontSize: 12,
              color: Colors.grey[600],
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildControlPanel() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.03),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          _buildInfoRow(Icons.person, "Sujeto", subjectId),
          Divider(height: 24, color: Colors.grey[100]),
          _buildDropdownRow(
            Icons.label,
            "Etiqueta",
            currentLabel,
            const [
              DropdownMenuItem(value: 'gait_slow', child: Text('Marcha lenta')),
              DropdownMenuItem(
                  value: 'gait_normal', child: Text('Marcha normal')),
              DropdownMenuItem(
                  value: 'gait_fast', child: Text('Marcha rápida')),
            ],
            (val) => setState(() => currentLabel = val!),
          ),
          Divider(height: 24, color: Colors.grey[100]),
          _buildInfoRow(
            Icons.directions_run,
            "Contexto",
            "Caminando",
          ),
        ],
      ),
    );
  }

  Widget _buildInfoRow(IconData icon, String label, String value) {
    return Row(
      children: [
        Icon(icon, size: 20, color: Colors.grey[400]),
        const SizedBox(width: 12),
        Text(
          label,
          style: GoogleFonts.inter(
            color: Colors.grey[600],
            fontWeight: FontWeight.w500,
          ),
        ),
        const Spacer(),
        Text(
          value,
          style: GoogleFonts.inter(
            fontWeight: FontWeight.w600,
            color: Colors.blueGrey[800],
          ),
        ),
      ],
    );
  }

  Widget _buildDropdownRow(
    IconData icon,
    String label,
    String value,
    List<DropdownMenuItem<String>> items,
    ValueChanged<String?> onChanged,
  ) {
    return Row(
      children: [
        Icon(icon, size: 20, color: Colors.grey[400]),
        const SizedBox(width: 12),
        Flexible(
          flex: 0,
          child: Text(
            label,
            style: GoogleFonts.inter(
              color: Colors.grey[600],
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: value,
              items: items,
              onChanged: onChanged,
              isExpanded: true,
              dropdownColor: Colors.white,
              style: GoogleFonts.inter(
                fontSize: 14,
                color: Colors.blueGrey[800],
                fontWeight: FontWeight.w600,
              ),
              icon: Icon(
                Icons.keyboard_arrow_down,
                size: 18,
                color: Colors.grey[400],
              ),
              alignment: Alignment.centerRight,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildActionButtons() {
    if (watchyDevice == null) {
      return SizedBox(
        height: 56,
        child: ElevatedButton.icon(
          onPressed: scanForWatchy,
          icon: const Icon(Icons.bluetooth_searching),
          label: const Text("BUSCAR WATCHY"),
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF263238),
            foregroundColor: Colors.white,
          ),
        ),
      );
    }

    return Column(
      children: [
        SizedBox(
          width: double.infinity,
          height: 56,
          child: ElevatedButton.icon(
            onPressed: isCapturing ? null : startCapture,
            icon: isCapturing
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.fiber_manual_record),
            label:
                Text(isCapturing ? "CAPTURANDO..." : "INICIAR CAPTURA (10s)"),
            style: ElevatedButton.styleFrom(
              backgroundColor:
                  isCapturing ? Colors.grey : const Color(0xFFD32F2F),
              foregroundColor: Colors.white,
            ),
          ),
        ),
        const SizedBox(height: 16),
        TextButton.icon(
          onPressed: disconnect,
          icon: const Icon(Icons.bluetooth_disabled, size: 18),
          label: const Text("Desconectar"),
          style: TextButton.styleFrom(
            foregroundColor: Colors.grey[600],
          ),
        ),
      ],
    );
  }
}
