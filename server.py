import os
import json
import requests
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

gcash_sec_key = os.environ.get(
    'PAYMONGO_SECRET_KEY',
    'sk_test_1JQT3jMMVQVAV8iUdzBbjsAX'  # Default for testing
)

tx_req_url = 'https://api.paymongo.com/v1/sources'
app_name = 'pay_proc_serv'

payment_serv = Flask(app_name)
CORS(payment_serv) # Allows frontend to hit API locally

# Base route check
@payment_serv.route('/')
def root_check():
    """Confirms server status."""
    return "Payment Processor Service running successfully. Use /tx-init for transactions."

@payment_serv.route('/tx-init', methods=['POST'])
def source_generator():
    """
    Handles POST request to create the PayMongo GCash Source.
    The secret key is used here to securely generate the source object.
    """
    try:
        json_input = request.json
        peso_val = json_input.get('amount')
        callback_link = json_input.get('return_url') # Where PayMongo redirects

        if not peso_val or not callback_link:
            return jsonify({'err': 'Missing required fields (amt or redir_url)'}), 400

        # Convert peso amount to centavos (required by PayMongo API)
        centavos_amt = int(float(peso_val) * 100)

        # 1. Build the Source creation payload
        tx_payload = {
            'data': {
                'attributes': {
                    'amount': centavos_amt,
                    'redirect': {
                        'success': callback_link,
                        'failed': callback_link
                    },
                    'type': 'gcash',
                    'currency': 'PHP',
                    'billing': {
                        'name': 'Dummy Customer',
                        'email': 'dummy@example.dev'
                    }
                }
            }
        }

        # 2. Set up headers for Basic Auth (hex-encoded key)
        auth_header = f'Basic {gcash_sec_key.encode("utf8").hex()}'
        req_headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': auth_header
        }

        # 3. Call PayMongo API
        paymon_resp = requests.post(tx_req_url, headers=req_headers, json=tx_payload)
        paymon_resp.raise_for_status() # Check for non-2xx response

        # 4. Extract the critical redirection link
        resp_data = paymon_resp.json()
        checkout_link = resp_data['data']['attributes']['redirect']['checkout_url']

        # 5. Return success and the link to the client
        return jsonify({'ok': True, 'redir_link': checkout_link})

    except requests.exceptions.HTTPError as e:
        print(f"PM Error: {e.response.text}")
        try:
            err_details = e.response.json()
        except json.JSONDecodeError:
            err_details = {'msg': 'Unspecified API error'}

        return jsonify({
            'ok': False,
            'err_type': 'API Failure',
            'details': err_details
        }), e.response.status_code

    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({'ok': False, 'err_type': f'Internal issue: {str(e)}'}), 500

if __name__ == '__main__':
    # Standard host/port for Render deployment or local test
    payment_serv.run(host='0.0.0.0', port=5000, debug=True)
