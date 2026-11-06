async function fetchTelemetryStatus() {
    try {
        const response = await fetch('/api/telemetry');
        const data = await response.json();
        
        document.getElementById('engine-state').innerText = data.status || 'IDLE';
        document.getElementById('telemetry-status').innerText = data.telemetry_status || 'Disconnected';
        
        // Display exact balance returned from exchange API (no fake default placeholders)
        const balanceElem = document.getElementById('live-balance');
        if (data.balance !== undefined) {
            balanceElem.innerText = `$${parseFloat(data.balance).toFixed(2)}`;
        } else {
            balanceElem.innerText = "$0.00";
        }

        if (data.message) {
            appendLog(`[INFO] ${data.message}`);
        }
    } catch (err) {
        document.getElementById('telemetry-status').innerText = 'Connection Error';
        appendLog(`[ERROR] Telemetry sync failed: ${err.message}`);
    }
}

function appendLog(message) {
    const logContainer = document.getElementById('engine-activity-log');
    if (!logContainer) return;
    const timestamp = new Date().toTimeString().split(' ')[0];
    const logEntry = document.createElement('div');
    logEntry.innerText = `[${timestamp}] ${message}`;
    logContainer.prepend(logEntry);
}

// Poll telemetry every 5 seconds
setInterval(fetchTelemetryStatus, 5000);
window.onload = fetchTelemetryStatus;
