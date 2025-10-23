from flask import Flask, request, jsonify, render_template
import requests
import base64
import os
from dotenv import load_dotenv

load_dotenv() 

PAYMONGO_SECRET_KEY = os.environ.get('PAYMONGO_SECRET_KEY') 
API_BASE_URL = 'https://api.paymongo.com/v1'
SERVER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'http://127.0.0.1:5000')

if not PAYMONGO_SECRET_KEY and '127.0.0.1' in SERVER_URL:
    PAYMONGO_SECRET_KEY = 'sk_test_PLACEHOLDER_FOR_LOCAL_DEV'

app = Flask(__name__, template_folder='templates')

def get_auth_header():
    auth_string = f"{PAYMONGO_SECRET_KEY}:"
    encoded_auth = base64.b64encode(auth_string.encode()).decode()
    return f"Basic {encoded_auth}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/payment-status')
def payment_status():
    status = request.args.get('status', 'unknown')
    reference = request.args.get('ref', 'N/A')
    
    return f"""
    <div style="text-align: center; padding: 50px; font-family: sans-serif; background-color: #1a1a2e; color: white;">
        <h2>Payment Redirect Status</h2>
        <p>Status: <strong>{status.upper()}</strong></p>
        <p>Order Ref: <strong>{reference}</strong></p>
        <p style="color: yellow;">
            Verification logs are available in your Render service console.
        </p>
        <a href="/" style="color: #168DE1;">Go Home</a>
    </div>
    """

@app.route('/api/create-gcash-payment', methods=['POST'])
def create_checkout():
    data = request.json
    amount_php = data.get('amount', 0)
    product_id = data.get('product_id', 'Unknown Product')
    
    amount_in_centavos = int(amount_php * 100)
    order_ref = f"ORD-{os.urandom(4).hex()}" 

    if not amount_in_centavos or amount_in_centavos <= 0:
        return jsonify({'success': False, 'error': 'Invalid amount.'}), 400

    print(f"[INIT] Creating checkout for {product_id}. Amount: {amount_in_centavos} centavos.")

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
    event = request.json.get('data')

    if not event:
        return jsonify({'status': 'invalid payload'}), 400

    print(f"\n--- WEBHOOK RECEIVED ---")
    event_type = event.get('attributes', {}).get('type')
    print(f"Event Type: {event_type}")

    if event_type == 'payment.paid':
        payment_data = event.get('attributes', {}).get('data', {}).get('attributes', {})
        order_ref = payment_data.get('metadata', {}).get('order_reference')
        status = payment_data.get('status')

        if status == 'paid':
            print(f"!!! FULFILLMENT TRIGGERED !!! Order {order_ref} is PAID and VERIFIED.")
        
        return jsonify({'status': 'received and processed'}), 200

    return jsonify({'status': 'event ignored'}), 200 
