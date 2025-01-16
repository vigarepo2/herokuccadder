from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO, emit
import aiohttp
import asyncio
import json
import uuid
import queue
import threading
from datetime import datetime

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

cc_queue = queue.Queue(maxsize=50)
current_proxy = None
processing = False

# HTML Template as a string
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CC Checker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f0f2f5; }
        .container-box {
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            background-color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .results-container {
            height: 400px;
            overflow-y: auto;
        }
        .result-item {
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            font-family: monospace;
        }
        .success { 
            background-color: #d4edda; 
            border-left: 4px solid #28a745;
        }
        .error { 
            background-color: #f8d7da; 
            border-left: 4px solid #dc3545;
        }
        .btn { font-weight: 500; }
        .status-badge {
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="container mt-4">
        <div class="row">
            <div class="col-md-4">
                <div class="container-box">
                    <h4>Heroku API Key</h4>
                    <input type="text" id="apiKey" class="form-control mb-3" placeholder="Enter Heroku API Key">
                    <button id="startBtn" class="btn btn-primary w-100 mb-3">Start Checking</button>
                    <div id="status" class="alert alert-info">Ready</div>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="container-box">
                    <h4>CC List (<span id="ccCount">0</span>/50)</h4>
                    <textarea id="ccInput" class="form-control mb-3" rows="4" 
                        placeholder="Format: 4242424242424242|12|2024|123"></textarea>
                    <button id="addCC" class="btn btn-success w-100">Add CC</button>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="container-box">
                    <h4>Proxy Settings (Optional)</h4>
                    <input type="text" id="proxyInput" class="form-control mb-3" 
                        placeholder="ip:port:user:pass">
                    <button id="setProxy" class="btn btn-secondary w-100">Set Proxy</button>
                </div>
            </div>
        </div>
        
        <div class="container-box results-container">
            <h4>Live Results</h4>
            <div id="resultsList"></div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        const socket = io();
        let isProcessing = false;
        
        document.getElementById('addCC').addEventListener('click', async () => {
            const ccs = document.getElementById('ccInput').value.split('\\n').filter(cc => cc.trim());
            for (const cc of ccs) {
                const response = await fetch('/add_cc', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: `cc=${encodeURIComponent(cc)}`
                });
                const data = await response.json();
                updateStatus(data.message);
            }
            document.getElementById('ccInput').value = '';
        });

        document.getElementById('setProxy').addEventListener('click', async () => {
            const proxy = document.getElementById('proxyInput').value;
            const response = await fetch('/set_proxy', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: `proxy=${encodeURIComponent(proxy)}`
            });
            const data = await response.json();
            updateStatus(data.message);
        });

        document.getElementById('startBtn').addEventListener('click', async () => {
            if (!isProcessing) {
                const apiKey = document.getElementById('apiKey').value;
                const response = await fetch('/start_checking', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: `api_key=${encodeURIComponent(apiKey)}`
                });
                const data = await response.json();
                updateStatus(data.message);
                isProcessing = true;
                document.getElementById('startBtn').textContent = 'Processing...';
            }
        });

        socket.on('cc_result', (data) => {
            const resultsList = document.getElementById('resultsList');
            const resultItem = document.createElement('div');
            resultItem.className = `result-item ${data.status === 'success' || data.status === 'insufficient_funds' ? 'success' : 'error'}`;
            resultItem.innerHTML = `
                <strong>${data.timestamp}</strong> - 
                CC: ${data.cc} - 
                <span class="status-badge ${data.status === 'success' || data.status === 'insufficient_funds' ? 'bg-success' : 'bg-danger'} text-white">
                    ${data.status.toUpperCase()}
                </span>
                ${data.message ? `<br>Message: ${data.message}` : ''}
            `;
            resultsList.insertBefore(resultItem, resultsList.firstChild);
        });

        socket.on('queue_update', (data) => {
            document.getElementById('ccCount').textContent = data.size;
            if (data.size === 0 && isProcessing) {
                isProcessing = false;
                document.getElementById('startBtn').textContent = 'Start Checking';
            }
        });

        function updateStatus(message) {
            const status = document.getElementById('status');
            status.textContent = message;
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/set_proxy', methods=['POST'])
def set_proxy():
    global current_proxy
    proxy_data = request.form.get('proxy')
    if proxy_data:
        current_proxy = proxy_data
        return jsonify({'status': 'success', 'message': 'Proxy set successfully'})
    return jsonify({'status': 'error', 'message': 'Invalid proxy format'})

@app.route('/add_cc', methods=['POST'])
def add_cc():
    cc = request.form.get('cc')
    try:
        if cc_queue.qsize() < 50:
            cc_queue.put(cc)
            return jsonify({
                'status': 'success',
                'message': 'CC added successfully',
                'queue_size': cc_queue.qsize()
            })
        return jsonify({
            'status': 'error',
            'message': 'Queue is full (max 50 CCs)'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

async def check_single_cc(session, cc, api_key):
    try:
        cc, mon, year, cvv = cc.split("|")
        guid = str(uuid.uuid4())
        muid = str(uuid.uuid4())
        sid = str(uuid.uuid4())

        headers = {
            "accept": "application/vnd.heroku+json; version=3",
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json"
        }

        proxy = None
        if current_proxy:
            proxy_parts = current_proxy.split(':')
            if len(proxy_parts) == 4:
                proxy = f"http://{proxy_parts[2]}:{proxy_parts[3]}@{proxy_parts[0]}:{proxy_parts[1]}"
            else:
                proxy = f"http://{current_proxy}"

        async with session.get(
            "https://api.heroku.com/account",
            headers=headers,
            proxy=proxy
        ) as response:
            if response.status != 200:
                return {"status": "error", "message": "Invalid API Key"}

        # Add your existing Heroku checking logic here
        # This is a simplified version for demonstration
        return {
            "status": "success",
            "message": "Card Added Successfully"
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

async def process_cc_queue_async(api_key):
    async with aiohttp.ClientSession() as session:
        while not cc_queue.empty():
            cc = cc_queue.get()
            result = await check_single_cc(session, cc, api_key)
            
            socketio.emit('cc_result', {
                'cc': cc,
                'status': result['status'],
                'message': result['message'],
                'timestamp': datetime.now().strftime('%H:%M:%S')
            })
            
            socketio.emit('queue_update', {'size': cc_queue.qsize()})
            await asyncio.sleep(2)  # Rate limiting

def process_cc_queue_thread(api_key):
    asyncio.run(process_cc_queue_async(api_key))

@app.route('/start_checking', methods=['POST'])
def start_checking():
    global processing
    api_key = request.form.get('api_key')
    
    if not api_key:
        return jsonify({'status': 'error', 'message': 'API Key required'})
    
    if not processing:
        processing = True
        threading.Thread(
            target=process_cc_queue_thread,
            args=(api_key,),
            daemon=True
        ).start()
        return jsonify({'status': 'success', 'message': 'Started processing'})
    return jsonify({'status': 'error', 'message': 'Already processing'})

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)
