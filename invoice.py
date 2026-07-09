from fpdf import FPDF
from sheets import get_order_details

def generate_invoice_pdf(order_id):
    order = get_order_details(order_id)

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, order["shop_name"], ln=True, align="C")

    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, f"Invoice - Order #{order_id}", ln=True, align="C")
    pdf.cell(0, 8, f"Date: {order['date']}", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", "B", 11)
    pdf.cell(100, 8, "Item", border=1)
    pdf.cell(20, 8, "Qty", border=1, align="C")
    pdf.cell(35, 8, "Price", border=1, align="R")
    pdf.cell(35, 8, "Subtotal", border=1, align="R", ln=True)

    pdf.set_font("Arial", "", 11)
    for item in order["items"]:
        pdf.cell(100, 8, item["name"], border=1)
        pdf.cell(20, 8, str(item["qty"]), border=1, align="C")
        pdf.cell(35, 8, f"Rs.{item['price']}", border=1, align="R")
        pdf.cell(35, 8, f"Rs.{item['qty'] * item['price']}", border=1, align="R", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Total: Rs.{order['total']}", ln=True, align="R")

    output_path = f"/tmp/invoice_{order_id}.pdf"
    pdf.output(output_path)
    return output_path