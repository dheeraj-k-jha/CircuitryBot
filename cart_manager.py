# cart structure in context.user_data:
# {
#     "cart": {
#         "PRD-101": {"name": "Pro Laptop 15", "price": 1200, "qty": 2},
#         "PRD-102": {"name": "Smartphone X", "price": 800, "qty": 1}
#     }
# }

def get_cart(context):
    if "cart" not in context.user_data:
        context.user_data["cart"] = {}
    return context.user_data["cart"]


# add to cart function
def add_to_cart(context, product):
    cart = get_cart(context)
    pid = product["Product_ID"]
    if pid in cart:
        cart[pid]["qty"] += 1
    else:
        cart[pid] = {
            "name": product["Product_name"],
            "price": product["Price"],
            "qty": 1
        }

def remove_from_cart(context, product_id):
    cart = get_cart(context)
    if product_id in cart:
        del cart[product_id]

def clear_cart(context):
    context.user_data["cart"] = {}

def get_cart_total(context):
    cart = get_cart(context)
    return sum(item["price"] * item["qty"] for item in cart.values())

def get_cart_summary(context):
    cart = get_cart(context)
    if not cart:
        return "🛒 Your cart is empty."
    lines = []
    for pid, item in cart.items():
        lines.append(f"• {item['name']} x{item['qty']} — ₹{item['price'] * item['qty']}")
    lines.append(f"\n💰 Total: ₹{get_cart_total(context)}")
    return "\n".join(lines)

def is_cart_empty(context):
    return len(get_cart(context)) == 0