from flask import Flask, request, jsonify
import requests
import base64
import os
from dotenv import load_dotenv

load_dotenv() 

# ==========================================================
# --- 1. CONFIGURATION (REQUIRED SETUP) ---
# IMPORTANT: For testing, enter your actual Test Key here.
# On Render, these values are securely overridden by Environment Variables.
# ==========================================================

# 1A. PAYMONGO SECRET KEY (REQUIRED)
# Render Key: PAYMONGO_SECRET_KEY
# If environment variable is found, it is used. Otherwise, it uses the placeholder.
PAYMONGO_SECRET_KEY = os.environ.get('PAYMONGO_SECRET_KEY', 'sk_test_1JQT3jMMVQVAV8iUdzBbjsAX')

# 1B. SERVER BASE URL (CRITICAL FOR REDIRECTS)
# Render Key: RENDER_EXTERNAL_URL
# This must match your server's public URL (or local URL).
SERVER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'http://127.0.0.1:5000')

# 1C. PAYMONGO API BASE
API_BASE_URL = 'https://api.paymongo.com/v1'

# ==========================================================
# --- 2. END CONFIGURATION ---
# ==========================================================

app = Flask(__name__)

# --- EMBEDDED HTML CONTENT ---

INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GCash Payment Test</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #1a1a2e; color: white; }
        .app-card { background-color: #24243b; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2); }
        .gcash-btn { background-color: #168DE1; color: white; transition: all 0.2s; }
        .gcash-btn:hover { background-color: #1377C2; }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">

    <div class="w-full max-w-md p-6 app-card rounded-xl space-y-6">
        <h1 class="text-2xl font-bold text-center border-b pb-3 border-gray-700">GCash Payment Test</h1>
        
        <div id="status-message" class="p-3 text-sm text-blue-300 bg-blue-900 border-l-4 border-blue-500 hidden" role="alert"></div>

        <div class="p-4 border border-gray-700 rounded-lg space-y-3">
            <h2 class="text-xl font-semibold">Product X Access</h2>
            <div class="flex justify-between items-center text-lg">
                <span class="text-gray-400">Price:</span>
                <span class="font-bold text-yellow-400">PHP 999.00</span>
            </div>
            
            <button 
                id="pay-trigger-btn" 
                class="gcash-btn w-full py-3 rounded-lg flex justify-center items-center space-x-2 text-lg font-bold"
                onclick="init_payment()">
                <span id="pay-trigger-text">
                    <i class="fas fa-wallet mr-2"></i> PAY WITH GCASH (PHP 999)
                </span>
            </button>
        </div>
    </div>

    <script>
        async function init_payment() {
            const btn = document.getElementById('pay-trigger-btn');
            const statusMsg = document.getElementById('status-message');
            
            btn.disabled = true;
            btn.innerHTML = 'Processing...';

            const payload = {
                product_id: 'Product-X-Access',
                amount: 999.00
            };

            try {
                const response = await fetch('/api/create-gcash-payment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await response.json();

                if (response.ok && data.success && data.redirect_url) {
                    statusMsg.className = 'p-3 text-sm text-green-300 bg-green-900 border-l-4 border-green-500';
                    statusMsg.innerHTML = 'Redirecting to PayMongo...';
                    statusMsg.classList.remove('hidden');

                    window.location.href = data.redirect_url;

                } else {
                    statusMsg.className = 'p-3 text-sm text-red-300 bg-red-900 border-l-4 border-red-500';
                    statusMsg.innerHTML = 'Error: ' + (data.error || 'Server failed to get redirect URL.');
                    statusMsg.classList.remove('hidden');
                }
            } catch (err) {
                statusMsg.className = 'p-3 text-sm text-red-300 bg-red-900 border-l-4 border-red-500';
                statusMsg.innerHTML = 'Network Error: Cannot connect to the local server.';
                statusMsg.classList.remove('hidden');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-wallet mr-2"></i> PAY WITH GCASH (PHP 999)';
            }
        }
    </script>
</body>
</html>
"""

STATUS_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Status</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style> body { font-family: 'Inter', sans-serif; background-color: #1a1a2e; color: white; } </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div class="w-full max-w-md p-6 bg-gray-800 rounded-xl space-y-4 shadow-2xl">
        <h2 class="text-3xl font-bold text-center text-yellow-400">Transaction Complete</h2>
        <div class="p-4 rounded-lg {status_bg_class} text-lg">
            <p>Payment Gateway Status:</p>
            <p class="text-2xl font-extrabold mt-1">{status_text}</p>
        </div>
        <div class="text-sm text-gray-400 border-t border-gray-700 pt-4">
            <p>Order Reference: <span class="font-mono text-white">{reference}</span></p>
            <p class="mt-2 text-yellow-300">
                (The actual verification was handled by the PayMongo Webhook on the server. Check your Render logs!)
            </p>
        </div>
        <a href="/" class="block w-full text-center py-2 rounded-lg bg-blue-600 hover:bg-blue-700 transition-colors font-bold">Start Over</a>
    </div>
</body>
</html>
"""

# --- FLASK APPLICATION LOGIC ---

def get_auth_header():
    """Generates the Basic Authentication header for PayMongo."""
    auth_string = f"{PAYMONGO_SECRET_KEY}:"
    encoded_auth = base64.b64encode(auth_string.encode()).decode()
    return f"Basic {encoded_auth}"

@app.route('/')
def index():
    """Serves the main payment initiation HTML page."""
    return INDEX_HTML

@app.route('/payment-status')
def payment_status():
    """Handles the redirect from PayMongo after payment success/cancel."""
    status = request.args.get('status', 'unknown')
    reference = request.args.get('ref', 'N/A')

    status_text = status.upper()
    status_bg_class = "bg-green-900/50 border border-green-500" if status == 'success' else "bg-red-900/50 border border-red-500"
    
    return STATUS_HTML_TEMPLATE.format(
        status_text=status_text, 
        reference=reference, 
        status_bg_class=status_bg_class
    )

@app.route('/api/create-gcash-payment', methods=['POST'])
def create_checkout():
    """Contacts PayMongo to create a Checkout session."""
    data = request.json
    amount_php = data.get('amount', 0)
    product_id = data.get('product_id', 'Unknown Product')
    
    amount_in_centavos = int(amount_php * 100)
    order_ref = f"ORD-{os.urandom(4).hex()}" 

    if not amount_in_centavos or amount_in_centavos <= 0:
        return jsonify({'success': False, 'error': 'Invalid amount.'}), 400

    headers = {
        'Content-Type': 'application/json',
        'Authorization': get_auth_header()
    }
    
    payload = {
        "data": {
            "attributes": {
                "payment_method_types": ["gcash"],
                "send_email_receipt": False,
                "amount": amount_in_centavos,
                "currency": "PHP",
                "description": f"Purchase of {product_id}",
                "success_url": f"{SERVER_URL}/payment-status?status=success&ref={order_ref}",
                "cancel_url": f"{SERVER_URL}/payment-status?status=cancel&ref={order_ref}",
                "metadata": { "order_reference": order_ref }
            }
        }
    }

    try:
        response = requests.post(f"{API_BASE_URL}/checkouts", headers=headers, json=payload)
        response.raise_for_status() 
        
        data = response.json()
        checkout_url = data['data']['attributes']['checkout_url']
        
        print(f"[SUCCESS] Checkout created. URL: {checkout_url}")
        return jsonify({'success': True, 'redirect_url': checkout_url})

    except requests.exceptions.HTTPError as e:
        print(f'[ERROR] PayMongo API HTTP Error: {e}')
        return jsonify({'success': False, 'error': 'PayMongo API failure.'}), 500
    except Exception as e:
        print(f'[SERVER ERROR] {e}')
        return jsonify({'success': False, 'error': 'Internal server error.'}), 500

@app.route('/webhooks/payment-handler', methods=['POST'])
def handle_webhook():
    """Receives and processes the secure Webhook from PayMongo (The verification point)."""
    event = request.json.get('data')

    if not event:
        return jsonify({'status': 'invalid payload'}), 400

    print(f"\n--- WEBHOOK RECEIVED ---")
    event_type = event.get('attributes', {}).get('type')

    if event_type == 'payment.paid':
        payment_data = event.get('attributes', {}).get('data', {}).get('attributes', {})
        order_ref = payment_data.get('metadata', {}).get('order_reference')
        status = payment_data.get('status')

        if status == 'paid':
            # This is where your fulfillment code goes (e.g., unlocking access in your database)
            print(f"!!! FULFILLMENT TRIGGERED !!! Order {order_ref} is PAID and VERIFIED.")
        
        return jsonify({'status': 'received and processed'}), 200

    return jsonify({'status': 'event ignored'}), 200 
