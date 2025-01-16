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
required_modules = ['fastapi', 'httpx', 'uvicorn']
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
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Heroku CC Checker</title>
    <style>
        body { font-family: Arial, sans-serif; }
        h1 { color: #4CAF50; }
        form { margin: 20px 0; }
        #response { white-space: pre-wrap; font-family: monospace; background-color: #f4f4f4; padding: 10px; border: 1px solid #ccc; margin-top: 20px; }
        .input-container { margin-bottom: 10px; }
        .input-container label { font-weight: bold; }
        .input-container input { width: 80%; padding: 8px; margin-top: 5px; }
        .btn { background-color: #4CAF50; color: white; padding: 10px 20px; border: none; cursor: pointer; }
        .btn:hover { background-color: #45a049; }
        .cc-list { margin-top: 20px; }
        .cc-item { background-color: #f9f9f9; padding: 10px; margin-bottom: 10px; border: 1px solid #ddd; }
    </style>
</head>
<body>
    <h1>Heroku CC Checker</h1>
    <form id="ccForm">
        <div class="input-container">
            <label for="api_key">API Key:</label><br>
            <input type="text" id="api_key" name="api_key" required><br><br>
        </div>
        <div class="input-container">
            <label for="ccs">Enter Credit Cards (up to 50, one per line):</label><br>
            <textarea id="ccs" name="ccs" rows="10" cols="50" required></textarea><br><br>
        </div>
        <button type="button" class="btn" onclick="submitForm()">Check Cards</button>
    </form>
    <div id="response"></div>
    <div id="ccList" class="cc-list"></div>

    <script>
        let ccs = [];
        let currentIndex = 0;

        async function submitForm() {
            const api_key = document.getElementById('api_key').value;
            const ccInput = document.getElementById('ccs').value.trim();
            ccs = ccInput.split('\n').map(cc => cc.trim()).filter(cc => cc !== "");

            if (ccs.length === 0 || ccs.length > 50) {
                alert("Please enter between 1 and 50 credit cards.");
                return;
            }

            document.getElementById('response').innerText = "Checking cards...\n";
            document.getElementById('ccList').innerHTML = "";
            await checkNextCC(api_key);
        }

        async function checkNextCC(api_key) {
            if (currentIndex >= ccs.length) {
                document.getElementById('response').innerText += "All credit cards checked.";
                return;
            }

            const cc = ccs[currentIndex];
            document.getElementById('ccList').innerHTML += `<div class="cc-item">Checking CC: ${cc}</div>`;
            const response = await fetch('/check_cc', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cc, api_key })
            });
            const result = await response.json();

            document.getElementById('response').innerText += `Result for CC ${cc}: ${JSON.stringify(result, null, 2)}\n`;

            if (result.status === 'success') {
                document.getElementById('response').innerText += `Card ${cc} added successfully. Stopping further checks.\n`;
                return;
            }

            currentIndex++;
            await checkNextCC(api_key);
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

        # Get client token
        url = "https://api.heroku.com/account/payment-method/client-token"
        req = await make_request(url, headers=headers)
        
        if not req:
            return {"status": "error", "message": "Failed to get client token"}
            
        client_secret = await parseX(req, '"token":"', '"')

        # Perform further requests using the client token
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
            "key": "pk_live_your_key",
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
            "key": "pk_live_your_key",
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
    result['cc'] = cc
    result['timestamp'] = datetime.now().strftime('%H:%M:%S')
    return result

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_json()
        await websocket.send_json({"status": "Message received", "data": data})

# Run the application using uvicorn
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
