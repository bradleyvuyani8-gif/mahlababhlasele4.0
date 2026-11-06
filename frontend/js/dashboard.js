async function fetchTelemetryStatus() {
    try {
        const response = await fetch('/api/telemetry');
        const data = await response.json();
        
        const engineStateElem = document.getElementById('engine-state');
        const telemetryStatusElem = document.getElementById('telemetry-status');
        const balanceElem = document.getElementById('live-balance');

        if (engineStateElem) engineStateElem.innerText = data.status || 'IDLE';
        if (telemetryStatusElem) telemetryStatusElem.innerText = data.telemetry_status || 'Disconnected';
        
        if (balanceElem) {
            if (data.balance !== undefined) {
                balanceElem.innerText = `$${parseFloat(data.balance).toFixed(2)}`;
            } else {
                balanceElem.innerText = "$0.00";
            }
        }

        if (data.message) {
            appendLog(`[INFO] ${data.message}`);
        }
    } catch (err) {
        const telemetryStatusElem = document.getElementById('telemetry-status');
        if (telemetryStatusElem) telemetryStatusElem.innerText = 'Connection Error';
        appendLog(`[ERROR] Telemetry sync failed: ${err.message}`);
    }
}

async function saveAndAuthorizeKeys() {
    const exchangeSelect = document.getElementById('exchange-select');
    const apiKeyInput = document.getElementById('api-key');
    const secretKeyInput = document.getElementById('secret-key');

    const exchange = exchangeSelect ? exchangeSelect.value : 'auto';
    const apiKey = apiKeyInput ? apiKeyInput.value.trim() : '';
    const secretKey = secretKeyInput ? secretKeyInput.value.trim() : '';

    if (!apiKey || !secretKey) {
        appendLog("[ERROR] API Key and Secret Key cannot be empty.");
        return;
    }

    appendLog("[INFO] Authenticating API credentials...");

    try {
        const response = await fetch('/api/auth/configure', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ exchange, api_key: apiKey, secret_key: secretKey, testnet: true })
        });
        
        const data = await response.json();
        if (response.ok) {
            appendLog(`[SUCCESS] Connected to ${data.exchange}. True Balance: $${parseFloat(data.balance).toFixed(2)}`);
            fetchTelemetryStatus();
        } else {
            appendLog(`[ERROR] Handshake rejected: ${JSON.stringify(data.detail)}`);
        }
    } catch (err) {
        appendLog(`[ERROR] Network failure during auth: ${err.message}`);
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
