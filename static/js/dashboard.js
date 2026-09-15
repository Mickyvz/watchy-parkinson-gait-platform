import { initializeApp } from "https://www.gstatic.com/firebasejs/12.4.0/firebase-app.js";
import { getAuth, signInWithEmailAndPassword } from "https://www.gstatic.com/firebasejs/12.4.0/firebase-auth.js";
import { getDatabase, ref, onValue } from "https://www.gstatic.com/firebasejs/12.4.0/firebase-database.js";

const firebaseConfig = {
    apiKey: "AIzaSyDodFRp_ojAx0XgQKc03VxXsmRF-QBitZw",
    authDomain: "watchy-e7e51.firebaseapp.com",
    databaseURL: "https://watchy-e7e51-default-rtdb.firebaseio.com",
    projectId: "watchy-e7e51",
    storageBucket: "watchy-e7e51.appspot.com",
    messagingSenderId: "1019655860469",
    appId: "1:1019655860469:web:fb73c8a2d4d7352e34d5bc",
    measurementId: "G-20PRNZM7VD"
};

const EMAIL = window.__WATCHY_DEVICE__.email;
const PASS = window.__WATCHY_DEVICE__.pass;
const USER_UID = window.__WATCHY_DEVICE__.userId;
const DEVICE_ID = window.__WATCHY_DEVICE__.deviceId;

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getDatabase(app);

// ======================
// Utilidades pasos diarios (para tarjetas)
// ======================
function flattenStepsTree(tree) {
    const out = [];
    if (!tree) return out;
    const days = Object.keys(tree).sort();
    for (const day of days) {
        const buckets = Object.keys(tree[day] || {}).sort();
        for (const hm of buckets) {
            const v = tree[day][hm] || {};
            out.push({
                label: `${day} ${hm.slice(0, 2)}:${hm.slice(2)}`,
                day, hm,
                count: Number(v.count || 0),
                delta: Number(v.delta || 0),
                calorias: Number(v.calorias || 0),
                distancia: Number(v.distancia || 0)
            });
        }
    }
    return out;
}

// ======================
// NUEVA GRÁFICA: pasos en 10 s por captura / sujeto
// ======================
let stepsCaptureChart = null;

function buildStepsCaptureChart() {
    const canvas = document.getElementById('signalChart');
    const data = window.CAPTURE_STEPS || [];

    if (!canvas || !window.Chart) {
        console.warn('signalChart o Chart no disponibles');
        return;
    }
    if (!Array.isArray(data) || data.length === 0) {
        console.warn('No hay capturas en CAPTURE_STEPS para graficar');
        return;
    }

    const ctx = canvas.getContext('2d');

    // Etiquetas del eje X: "P001 - 2025-12-10 10:47"
    const labels = data.map(item => `${item.subject} - ${item.ts_str}`);

    // Valores Y: pasos en la ventana de 10 s
    const stepsValues = data.map(item => item.steps_interval || 0);

    const borderColor = 'rgba(54,162,235,1)';
    const backgroundColor = 'rgba(54,162,235,0.15)';

    if (stepsCaptureChart) {
        // por si quieres actualizar en caliente en el futuro
        stepsCaptureChart.data.labels = labels;
        stepsCaptureChart.data.datasets[0].data = stepsValues;
        stepsCaptureChart.update();
        return;
    }

    stepsCaptureChart = new Chart(ctx, {
        type: 'bar',   // cámbialo a 'line' si prefieres línea
        data: {
            labels,
            datasets: [{
                label: 'Pasos en 10 s',
                data: stepsValues,
                borderWidth: 2,
                borderColor,
                backgroundColor,
                tension: 0.25
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        label: function (ctx) {
                            const y = ctx.parsed.y;
                            return `Pasos: ${y}`;
                        },
                        afterBody: function (items) {
                            const idx = items[0].dataIndex;
                            const item = data[idx];
                            return item.label ? `Etiqueta: ${item.label}` : '';
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Sujeto - Fecha/hora de captura'
                    },
                    ticks: {
                        maxRotation: 60,
                        minRotation: 30,
                        autoSkip: true
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Pasos en ventana de 10 s'
                    },
                    beginAtZero: true
                }
            }
        }
    });
}

// ======================
// Firebase para tarjetas de PASOS HOY / CALORÍAS
// ======================
signInWithEmailAndPassword(auth, EMAIL, PASS).then(() => {
    const stepsRef = ref(db, `users/${USER_UID}/devices/${DEVICE_ID}/steps`);
    onValue(stepsRef, (snap) => {
        const rows = flattenStepsTree(snap.val());
        if (!rows.length) return;

        const last = rows.at(-1);
        const currentDay = last.day;
        const todayRows = rows.filter(r => r.day === currentDay);
        const latestToday = todayRows.at(-1);

        const pasosHoy = latestToday?.count ?? 0;
        const caloriasHoy = latestToday?.calorias ?? 0;

        document.getElementById('totalStepsToday').textContent = String(pasosHoy);
        document.getElementById('batteryMv').textContent =
            caloriasHoy ? `${caloriasHoy.toFixed(1)} kcal` : '--';

        // ❌ Ya no llamamos a renderStepsChart aquí.
        // La gráfica principal usa CAPTURE_STEPS (rawdata) y se construye aparte.
    });

}).catch(err => console.error('Login web falló:', err));


// ======================
// Inicialización de gráfica de capturas
// ======================
document.addEventListener('DOMContentLoaded', () => {
    // 🔹 Gráfica principal de pasos en 10 s por captura
    buildStepsCaptureChart();
});
