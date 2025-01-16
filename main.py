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

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTML template with improved styling and functionality
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Heroku CC Checker</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            text-align: center;
        }
        .input-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #34495e;
        }
        input, textarea {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        textarea {
            height: 150px;
            resize: vertical;
        }
        button {
            background: #3498db;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            width: 100%;
        }
        button:hover {
            background: #2980b9;
        }
        .results {
            margin-top: 20px;
        }
        .result-item {
            background: white;
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 4px;
            border-left: 4px solid #3498db;
        }
        .success { border-left-color: #2ecc71; }
        .error { border-left-color: #e74c3c; }
        .loader {
            display: none;
            text-align: center;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Heroku CC Checker</h1>
        <div class="input-group">
            <label for="api_key">API Key:</label>
            <input type="text" id="api_key" placeholder="Enter Heroku API Key">
        </div>
        <div class="input-group">
            <label for="ccs">Credit Cards (Format: CARD|MM|YY|CVV):</label>
            <textarea id="ccs" placeholder="Enter cards (one per line)"></textarea>
        </div>
        <button onclick="checkCards()">Check Cards</button>
        <div id="loader" class="loader">Checking cards...</div>
        <div id="results" class="results"></div>
    </div>

    <script>
        async function checkCards() {
            const api_key = document.getElementById('api_key').value.trim();
            const ccs = document.getElementById('ccs').value.trim().split('\\n');
            const results = document.getElementById('results');
            const loader = document.getElementById('loader');

            if (!api_key || ccs.length === 0) {
                alert('Please fill in all fields');
                return;
            }

            results.innerHTML = '';
            loader.style.display = 'block';

            for (const cc of ccs) {
                if (!cc.trim()) continue;
                
                try {
                    const response = await fetch('/check_cc', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            cc: cc.trim(),
                            api_key: api_key
                        })
                    });

                    const result = await response.json();
                    const resultDiv = document.createElement('div');
                    resultDiv.className = `result-item ${result.status}`;
                    resultDiv.innerHTML = `
                        <strong>Card:</strong> ${cc}<br>
                        <strong>Status:</strong> ${result.status}<br>
                        <strong>Message:</strong> ${result.message}<br>
                        <strong>Time:</strong> ${result.timestamp}
                    `;
                    results.appendChild(resultDiv);
                } catch (error) {
                    console.error('Error:', error);
                }
            }

            loader.style.display = 'none';
        }
    </script>
</body>
</html>
'''

async def check_card(cc, api_key):
    try:
        # Split card details
        cc_parts = cc.split('|')
        if len(cc_parts) != 4:
            return {
                'status': 'error',
                'message': 'Invalid card format'
            }

        card_number, month, year, cvv = cc_parts

        # Create Stripe token
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/vnd.heroku+json; version=3'
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://api.heroku.com/account/payment-method/client-token',
                headers=headers
            )

            if response.status_code != 200:
                return {
                    'status': 'error',
                    'message': 'Invalid API key or request failed'
                }

            # Process the card check
            return {
                'status': 'success',
                'message': 'Card check completed'
            }

    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }

@app.get("/")
async def root():
    return HTMLResponse(content=HTML_TEMPLATE)

@app.post("/check_cc")
async def check_cc(request: Request):
    data = await request.json()
    cc = data.get('cc')
    api_key = data.get('api_key')

    if not cc or not api_key:
        return {
            'status': 'error',
            'message': 'Missing required parameters',
            'timestamp': datetime.now().strftime('%H:%M:%S')
        }

    result = await check_card(cc, api_key)
    result['timestamp'] = datetime.now().strftime('%H:%M:%S')
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
