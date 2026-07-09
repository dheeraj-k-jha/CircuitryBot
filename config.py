import os
from dotenv import load_dotenv

load_dotenv() 

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
STORE_NAME = os.getenv("STORE_NAME")
# UPI_ID = os.getenv("UPI_ID")
# UPI_NAME = os.getenv("UPI_NAME")
STORE_PHONE = os.getenv("STORE_PHONE")
STORE_EMAIL = os.getenv("STORE_EMAIL")
STORE_ADDRESS = os.getenv("STORE_ADDRESS")
STORE_HOURS = os.getenv("STORE_HOURS")
SHEET_NAME = "Circuitry"
RAZORPAY_KEY_ID=os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET=os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET=os.getenv("RAZORPAY_WEBHOOK_SECRET")
print(f"DEBUG: Key ID loaded: {RAZORPAY_KEY_ID[:10] if RAZORPAY_KEY_ID else 'MISSING'}...")
GOOGLE_CREDENTIALS=os.getenv("GOOGLE_CREDENTIALS")