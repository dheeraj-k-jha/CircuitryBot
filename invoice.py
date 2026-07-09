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

#-------------------------Items--------------------------------------------------
    pdf.set_font("Arial", "B", 11)
    pdf.cell(90, 8, "Item", border=1)
    pdf.cell(20, 8, "Qty", border=1, align="C")
    pdf.cell(35, 8, "Price", border=1, align="R")
    pdf.cell(35, 8, "Subtotal", border=1, align="R", ln=True)

    pdf.set_font("Arial", "", 10)
    row_height = 6

    for item in order["items"]:
        item_name = item["name"]
        qty = item["qty"]
        price = item["price"]
        subtotal = qty * price

        # how many lines will the item name take at this column width?
        lines_needed = pdf.multi_cell(90, row_height, item_name, border=0, split_only=True)
        num_lines = len(lines_needed)
        cell_h = row_height * num_lines

        x_start = pdf.get_x()
        y_start = pdf.get_y()

        # draw the wrapped item name
        pdf.multi_cell(90, row_height, item_name, border=1)

        # move cursor back up to draw the other 3 columns at matching height
        pdf.set_xy(x_start + 90, y_start)
        pdf.cell(20, cell_h, str(qty), border=1, align="C")
        pdf.cell(35, cell_h, f"Rs.{price}", border=1, align="R")
        pdf.cell(35, cell_h, f"Rs.{subtotal}", border=1, align="R", ln=True)

    #--------------------------Total------------------------    
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Total: Rs.{order['total']}", ln=True, align="R")

    output_path = f"/tmp/invoice_{order_id}.pdf"
    pdf.output(output_path)
    return output_path