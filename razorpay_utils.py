import config
import razorpay
import os


#-------------------------------Razorpay Credentials-----------------------------
RAZORPAY_KEY_ID = config.RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET = config.RAZORPAY_KEY_SECRET
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

def create_payment_link(order_id, amount_rupees, customer_name, customer_phone, shop_name):
    amount_paise = int(amount_rupees * 100)

    link_data = {
        "amount": amount_paise,
        "currency": "INR",
        "description": f"Order #{order_id} - {shop_name}",
        "customer": {
            "name": customer_name,
            "contact": customer_phone
        },
        "notify": {"sms": True, "email": False},
        "reference_id": str(order_id),
        "callback_url": "https://your-actual-app-name.onrender.com/",
        "callback_method": "get"
    }

    response = client.payment_link.create(link_data)
    return response["short_url"], response["id"]