import config
import gspread
import json
import os
from google.oauth2.service_account import Credentials
from config import SHEET_NAME , GOOGLE_CREDENTIALS
from datetime import datetime , timedelta

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets", 
    "https://www.googleapis.com/auth/drive"
]


ORDERS_HEADERS = {
    "Order ID": 1,
    "Timestamp": 2,
    "User ID": 3,
    "Customer Name": 4,
    "Customer Phone": 5,
    "Product ID": 6,
    "Product Name": 7,
    "Quantity": 8,
    "Unit Price": 9,
    "Total": 10,
    "Status": 11
}
# creating client
_gc = None
_workbook = None
def get_sheet_client():
    global _gc
    if _gc is None:
        creds_dict = GOOGLE_CREDENTIALS
        if creds_dict:
              creds_json = json.loads(creds_dict)
              creds = Credentials.from_service_account_info(creds_json,scopes = SCOPES)
        else:
             print("unable to access google api credentials") 
        _gc = gspread.authorize(creds)
    return _gc

# getting workbook
def get_workbook():
    global _workbook , _gc
    if _workbook is None:
        _workbook = get_sheet_client().open(SHEET_NAME)
    return _workbook

# getting specified worksheet
def get_worksheet(sheet_tab_name):
    return get_workbook().worksheet(sheet_tab_name)


# internal cache variables:
_cached_products = None
_last_cache_time = None
_cache_duration = timedelta(minutes=30)

def get_all_products():
	global _cached_products , _last_cache_time
  
	# computing if new fetch is required
	current_time = datetime.now()	
	is_cache_expired = (_last_cache_time is None) or (current_time -	_last_cache_time > _cache_duration)

	# fetching again:
	if _cached_products is None or is_cache_expired:
		print("Please wait refreshing/fetching product list")
		ws = get_worksheet("Products")
		_cached_products = ws.get_all_records()
		_last_cache_time = current_time
	else: 
		print("Returning Catched Data")
	return _cached_products


# /refresh:
def clear_cache():
	"""Forcibly clears the cache so the next request is forced to pull from Google	if owner uses /refresh command"""
	global _cached_products , _last_cache_time
	_cached_products = None
	_last_cache_time = None



# different functions
def get_all_categories():
	products = get_all_products()
	categories = sorted(set(p["Category"] for p in products))
	return categories



def get_products_by_categories(category):
	products = get_all_products()
	return [ p for p in products if p["Category"] == category and p["Stock_quantity"] > 0]


# fetching products by their product ID:
def get_product_by_id(product_id):
	products = get_all_products()
	for p in products:
		if p["Product_ID"] == product_id:
			return p
	return None


# fetching specs of a product:
def get_product_specs(product_id):
    ws = get_worksheet("Product_specs")
    data = ws.get_all_records(expected_headers=["Product_ID", "Spec_name",  "Spec_value"])
    specs = [d for d in data if d["Product_ID"] == product_id]
    if specs:
        return specs
    else:
        print("Nothing found for this product id")
        return []

# write order:
def write_order(customer_name,customer_phone, user_id, cart):
    ws = get_worksheet("Orders")
    all_orders = ws.get_all_records()
    
    order_id = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # one row per cart item
    for pid, item in cart.items():
        ws.append_row([
            order_id,
            timestamp,
            str(user_id),
            customer_name,
            customer_phone,
            pid,
            item["name"],
            item["qty"],
            item["price"],
            item["qty"] * item["price"],
            "Payment Confirmation Pending"
        ])
    
    return order_id

# # update order status:
# def update_order_status(order_id, status):
#     ws = get_worksheet("Orders")
#     cell = ws.find(order_id)
#     if cell:
#         # status column is column 11
#         ws.update_cell(cell.row, 11, status)


#-------------------------------------------------------------------------
#-----------------------update order status----------------------------------
#-------------------------------------------------------------------------
def update_order_status(order_id, status):
    ws = get_worksheet("Orders")
    cells = ws.findall(order_id)  # findall, not find — gets every matching row
    for cell in cells:
        ws.update_cell(cell.row, 11, status)


#-------------------------------------------------------------------------
#-----------------------get_order_details---------------------------------
#-------------------------------------------------------------------------
def get_order_details(order_id):
    ws = get_worksheet("Orders")
    all_orders = ws.get_all_records()
    matching_rows = [row for row in all_orders if row["Order ID"] == order_id]

    if not matching_rows:
        return None

    first = matching_rows[0]
    items = [
        {"name": row["Product Name"], "qty": row["Quantity"], "price": row["Unit Price"]}
        for row in matching_rows
    ]
    total = sum(item["qty"] * item["price"] for item in items)

    return {
        "shop_name": config.STORE_NAME,
        "date": first["Timestamp"],
        "customer_name": first["Customer Name"],
        "user_id": first["User ID"],
        "status": first["Status"],   # NEW
        "items": items,
        "total": total
    }




# customer complainst:
def write_complaint(user_id, customer_name, order_id, issue):
    ws = get_worksheet("Complaints")
    complaint_id = f"CMP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws.append_row([complaint_id, timestamp, str(user_id), customer_name, order_id, issue, "Open", "Pending"])
    return complaint_id


# Customer Enquiry  
def write_enquiry(user_id, customer_name, phone, product_interest, message):
    ws = get_worksheet("Enquiries")
    enquiry_id = f"ENQ-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws.append_row([enquiry_id, timestamp, str(user_id), customer_name, phone, product_interest, message, "Open"])
    return enquiry_id