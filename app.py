from flask import Flask, request, jsonify
import asyncio
import config
import razorpay
import os
import sheets
from invoice import generate_invoice_pdf
from telegram import Bot


app = Flask(__name__)

#-------------------------------------------------------------------------
#-----------------------razorpay/telegram credentials---------------------
#-------------------------------------------------------------------------
RAZORPAY_WEBHOOK_SECRET = config.RAZORPAY_WEBHOOK_SECRET
TELEGRAM_BOT_TOKEN = config.BOT_TOKEN

bot = Bot(token=TELEGRAM_BOT_TOKEN)
verify_client = razorpay.Client(auth=("", ""))


#-------------------------------------------------------------------------
#-----------------------Keep Alive Function-------------------------------
#-------------------------------------------------------------------------
@app.route('/')
def home():
    return "Bot is alive!" , 200


#-------------------------------------------------------------------------
#-----------------------Razorpay Webhook----------------------------------
#-------------------------------------------------------------------------
@app.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():
    payload_body = request.get_data()
    signature = request.headers.get("X-Razorpay-Signature")

    try:
        verify_client.utility.verify_webhook_signature(
            payload_body.decode(), signature, RAZORPAY_WEBHOOK_SECRET
        )
    except razorpay.errors.SignatureVerificationError:
        return jsonify({"status": "invalid signature"}), 400

    data = request.get_json()

    if data["event"] == "payment_link.paid":
        entity = data["payload"]["payment_link"]["entity"]
        order_id = entity["reference_id"]

        order = sheets.get_order_details(order_id)          # fetches User ID
        if order is None:
            return jsonify({"status": "order not found"}), 404

        sheets.update_order_status(order_id, "Paid")   # updates status to Paid
        chat_id = order["user_id"]                     # pulled straight from order dict
        pdf_path = generate_invoice_pdf(order_id)

        asyncio.run(bot.send_document(chat_id=chat_id, document=open(pdf_path, "rb")))
        asyncio.run(bot.send_message(chat_id=chat_id, text="Payment received! Here's your invoice."))

    return jsonify({"status": "ok"}), 200


# #-------------------keep_alive()-------------------------------    
# def keep_alive():
#     t = Thread(target=run)
#     t.daemon = True
#     t.start()