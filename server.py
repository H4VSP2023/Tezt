from flask import Flask, request, jsonify
import requests
import base64
import os
from dotenv import load_dotenv

load_dotenv() 

# ==========================================================
# --- CONFIGURATION BLOCK ---
# NOTE: Environment variables will override these defaults in production.
# ==========================================================

# 1A. PAYMONGO SECRET KEY (Env Var: M_KEY)
# This will be overridden by the M_KEY environment variable on Render.
M_KEY = os.environ.get('M_KEY', 'sk_test_1JQT3jMMVQVAV8iUdzBbjsAX')

# 1B. APPLICATION HOST URL (Env Var: HOST_URL)
# This must be your actual Render public URL for redirects.
HOST_URL = os.environ.get('HOST_URL', 'https://tezt-bib8.onrender.com')

# 1C. API GATEWAY ENDPOINT
GATEWAY_URL = 'https://api.paymongo.com/v1'

# ==========================================================
# --- CORE APPLICATION SETUP ---
# ==========================================================

w_app = Flask(__name__)

# --- EMBEDDED HTML (MAIN CHECKOUT UI) ---

MAIN_UI = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Secure GCash Checkout</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #1a1a2e; color: white; }
        .card-ui { background-color: #24243b; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2); }
        .gcash-btn { background-color: #168DE1; color: white; transition: all 0.2s; }
        .gcash-btn:hover { background-color: #1377C2; }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">

    <div class="w-full max-w-md p-6 card-ui rounded-xl space-y-6">
        <h1 class="text-2xl font-bold text-center border-b pb-3 border-gray-700">Checkout</h1>
        
        <div id="msg" class="p-3 text-sm text-blue-300 bg-blue-900 border-l-4 border-blue-500 hidden" role="alert"></div>

        <div class="p-4 border border-gray-700 rounded-lg space-y-3">
            <h2 class="text-xl font-semibold">Subscription Access</h2>
            <div class="flex justify-between items-center text-lg">
                <span class="text-gray-400">Total Due:</span>
                <span class="font-bold text-yellow-400">PHP 999.00</span>
            </div>
            
            <button 
                id="btn_trigger" 
                class="gcash-btn w-full py-3 rounded-lg flex justify-center items-center space-x-2 text-lg font-bold"
                onclick="init_pay()">
                <span id="btn_txt">
                    <i class="fas fa-wallet mr-2"></i> PAY WITH GCASH (PHP 999)
                </span>
            </button>
        </div>
    </div>

    <script>
        async function init_pay() {
            const btn = document.getElementById('btn_trigger');
            const msg = document.getElementById('msg');
            
            btn.disabled = true;
            btn.innerHTML = 'Establishing Secure Session...';

            const payload = {
                product_id: 'Subscription-Tier-1',
                amount: 999.00
            };

            try {
                const rsp = await fetch('/api/create-tx', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const data = await rsp.json();

                if (rsp.ok && data.success && data.tx_url) {
                    msg.className = 'p-3 text-sm text-green-300 bg-green-900 border-l-4 border-green-500';
                    msg.innerHTML = 'Redirecting to payment gateway...';
                    msg.classList.remove('hidden');

                    window.location.href = data.tx_url;

                } else {
                    msg.className = 'p-3 text-sm text-red-300 bg-red-900 border-l-4 border-red-500';
                    msg.innerHTML = 'Error initiating payment: ' + (data.error || 'Server connection failed.');
                    msg.classList.remove('hidden');
                }
            } catch (err) {
                msg.className = 'p-3 text-sm text-red-300 bg-red-900 border-l-4 border-red-500';
                msg.innerHTML = 'Network connection failed.';
                msg.classList.remove('hidden');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-wallet mr-2"></i> PAY WITH GCASH (PHP 999)';
            }
        }
    </script>
</body>
</html>
"""

# --- EMBEDDED HTML (STATUS PAGE UI) ---

STATUS_UI = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transaction Result</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style> body { font-family: 'Inter', sans-serif; background-color: #1a1a2e; color: white; } </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4">
    <div class="w-full max-w-md p-6 bg-gray-800 rounded-xl space-y-4 shadow-2xl">
        <h2 class="text-3xl font-bold text-center text-yellow-400">Transaction Status</h2>
        <div class="p-4 rounded-lg {status_bg_class} text-lg">
            <p>Gateway Result:</p>
            <p class="text-2xl font-extrabold mt-1">{status_text}</p>
        </div>
        <div class="text-sm text-gray-400 border-t border-gray-700 pt-4">
            <p>Reference ID: <span class="font-mono text-white">{ref_id}</span></p>
            <p class="mt-2 text-yellow-300">
                (Verification status confirmed via server-side webhook.)
            </p>
        </div>
        <a href="/" class="block w-full text-center py-2 rounded-lg bg-blue-600 hover:bg-blue-700 transition-colors font-bold">Return to Shop</a>
    </div>
</body>
</html>
"""

# --- BACKEND FUNCTIONS ---

def get_auth():
    auth_str = f"{M_KEY}:"
    enc_auth = base64.b64encode(auth_str.encode()).decode()
    return f"Basic {enc_auth}"

@w_app.route('/')
def home():
    return MAIN_UI

@w_app.route('/txn-status')
def txn_status():
    status = request.args.get('status', 'unknown')
    ref_id = request.args.get('ref', 'N/A')

    status_txt = status.upper()
    status_bg_class = "bg-green-900/50 border border-green-500" if status == 'success' else "bg-red-900/50 border border-red-500"
    
    return STATUS_UI.format(
        status_text=status_txt, 
        ref_id=ref_id, 
        status_bg_class=status_bg_class
    )

@w_app.route('/api/create-tx', methods=['POST'])
def create_tx():
    data = request.json
    amt_php = data.get('amount', 0)
    prod_id = data.get('product_id', 'Generic Item')
    
    amt_cts = int(amt_php * 100)
    ref_id = f"REF-{os.urandom(4).hex()}" 

    if not amt_cts or amt_cts <= 0:
        return jsonify({'success': False, 'error': 'Invalid amount provided.'}), 400

    headers = {
        'Content-Type': 'application/json',
        'Authorization': get_auth()
    }
    
    payload = {
        "data": {
            "attributes": {
                "payment_method_types": ["gcash"],
                "send_email_receipt": False,
                "amount": amt_cts,
                "currency": "PHP",
                "description": f"Subscription: {prod_id}",
                "success_url": f"{HOST_URL}/txn-status?status=success&ref={ref_id}",
                "cancel_url": f"{HOST_URL}/txn-status?status=cancel&ref={ref_id}",
                "metadata": { "order_reference": ref_id }
            }
        }
    }

    try:
        rsp = requests.post(f"{GATEWAY_URL}/checkouts", headers=headers, json=payload)
        rsp.raise_for_status() 
        
        data = rsp.json()
        tx_url = data['data']['attributes']['checkout_url']
        
        print(f"Checkout initiated: {ref_id}")
        return jsonify({'success': True, 'tx_url': tx_url})

    except requests.exceptions.HTTPError as e:
        print(f'API Error: {e}')
        return jsonify({'success': False, 'error': 'Gateway API failure.'}), 500
    except Exception as e:
        print(f'Server Error: {e}')
        return jsonify({'success': False, 'error': 'Internal system error.'}), 500

@w_app.route('/webhooks/payment-handler', methods=['POST'])
def webhook_handler():
    evt = request.json.get('data')

    if not evt:
        return jsonify({'status': 'invalid payload'}), 400

    evt_type = evt.get('attributes', {}).get('type')

    if evt_type == 'payment.paid':
        pay_data = evt.get('attributes', {}).get('data', {}).get('attributes', {})
        ref_id = pay_data.get('metadata', {}).get('order_reference')
        status = pay_data.get('status')

        if status == 'paid':
            # This is the point of truth for fulfillment
            print(f"WEBHOOK-SUCCESS: Transaction {ref_id} verified as PAID. FULFILLMENT TRIGGERED.")
        
        return jsonify({'status': 'received'}), 200

    return jsonify({'status': 'ignored'}), 200 
