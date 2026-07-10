import io
import warnings
import httpx
import asyncio
import os

from app import app, payment_messages
from telegram import Update , InlineKeyboardButton , InlineKeyboardMarkup
from telegram.ext import ConversationHandler ,filters , CommandHandler , MessageHandler , Application , CallbackQueryHandler , ContextTypes
from telegram.error import BadRequest
from telegram.warnings import PTBUserWarning
from threading import Thread
from razorpay_utils import create_payment_link




import cart_manager
import config
import sheets




#-------------------------------------------------------------------------
#-----------------------Helper Function-----------------------------------
#-------------------------------------------------------------------------
def build_category_keyboard(context=None):
    categories = sheets.get_all_categories()
    buttons = [
        [InlineKeyboardButton(cat, callback_data=f"cat_{cat}")]
        for cat in categories
    ]
    # cart count if context available
    cart_count = ""
    if context and not cart_manager.is_cart_empty(context):
        count = len(cart_manager.get_cart(context))
        cart_count = f" ({count})"
    buttons.append(
        [InlineKeyboardButton(f"🛒 View Cart{cart_count}", callback_data="view_cart"),
        InlineKeyboardButton("🚨 Complaint", callback_data="complaint"),
        InlineKeyboardButton("💬 Enquiry", callback_data="enquiry")]
    )
    return InlineKeyboardMarkup(buttons)


#-------------------------------------------------------------------------
#-----------------------Start Command-------------------------------------
#-------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "Unknown"

    await update.message.reply_text(
        f"👋 Welcome to <b>{config.STORE_NAME}</b>!\n\n"
        f"🛍️ Browse our products and place orders directly here.\n"
        f"📞 Need help? Use the Contact button inside any product.\n\n"
        f"<i>Choose a category to get started:</i>",
        parse_mode="HTML",
        reply_markup=build_category_keyboard(context)
    )
#----------------------------Saving user---------------------------------
    already_exists = await asyncio.to_thread(sheets.user_exists, user_id)
    if not already_exists:
        await asyncio.to_thread(sheets.add_user, user_id, user_name)
#----------------------------Sending Welcome Message---------------------


# fetching and printing categories as inline buttons
async def category_selected(update: Update , context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  category = query.data.replace("cat_","") # removing cat_ prefix from category name
  products = sheets.get_products_by_categories(category)
  buttons = []
  for p in products:
    label = f"{p["Product_name"]} 🏷️ ₹{p['Price']}"
    buttons.append([InlineKeyboardButton(label,callback_data=f"prod_{p["Product_ID"]}")])
  buttons.append([InlineKeyboardButton("⬅️ Back to Categories", callback_data="back_to_categories")])

  await query.edit_message_text(
    f"📦 {category}",
    reply_markup=InlineKeyboardMarkup(buttons)
  )


# back to categories function
async def back_to_categories(update: Update , context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await  query.answer()
  await query.message.delete()
  await context.bot.send_message(
    chat_id= update.effective_chat.id,
    text="Welcome to StoreBuddy! Choose a category:",
    reply_markup=build_category_keyboard(context)
  )


#-------------------------------------------------------------------------
#-----------------------Announcement Command------------------------------
#-------------------------------------------------------------------------
async def announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.OWNER_ID:
        return  # silently ignored for anyone else — command doesn't exist to them

    message_text = " ".join(context.args)
    if not message_text:
        await update.message.reply_text("Usage: /announce your message here")
        return

    await update.message.reply_text("📢 Broadcast started in background...")
    asyncio.create_task(broadcast_message(context.bot, message_text))


async def broadcast_message(bot, text):
    user_ids = await asyncio.to_thread(sheets.get_all_user_ids)
    sent_count = 0
    failed_count = 0

    for uid in user_ids:
        try:
            await bot.send_message(chat_id=int(uid), text=text)
            sent_count += 1
        except Exception as e:
            print(f"Failed to send to {uid}: {e}")
            failed_count += 1
        await asyncio.sleep(0.05)  # throttle to avoid Telegram rate limits

    await bot.send_message(
        chat_id=config.OWNER_ID,
        text=f"📢 Broadcast complete.\nSent: {sent_count}\nFailed: {failed_count}"
    )


#-------------------------------------------------------------------------
#-----------------------Caching Image-------------------------------------
#-------------------------------------------------------------------------
TELEGRAM_IMAGE_CACHE = {}  # Format: {"PRD-101": "AgACAgQAAx..."}

# product selected function
async def product_selected(update: Update , context: ContextTypes.DEFAULT_TYPE):
  query = update.callback_query
  await query.answer()
  await query.edit_message_text("⏳ Loading product...")
  
  product_id = query.data.replace("prod_","")
  
  # Checking if we already uploaded this image before, send it instantly!
  cached_file_id = TELEGRAM_IMAGE_CACHE.get(product_id)
  
  product = sheets.get_product_by_id(product_id)
  if not product: 
    await query.edit_message_text("Product not found.")
    return
  
  specs = sheets.get_product_specs(product_id)
  specs_text = ""
  if specs:
    specs_text = "\n".join(f"• {s['Spec_name']}: {s['Spec_value']}" for s in specs)
    
  caption = (
    f"📦 {product['Product_name']}\n"
    f"💰 Price: ₹{product['Price']}\n"
    f"📦 Stock: {product['Stock_quantity']} units\n\n"
    f"📝 {product['Description']}\n\n"
    f"<b>Specification:</b> \n"
    f"{specs_text}"
  )
  
  buttons = [
    [InlineKeyboardButton("🛒 Add to Cart", callback_data=f"addcart_{product_id}"),
    InlineKeyboardButton("⚡ Checkout", callback_data="checkout")],
    [InlineKeyboardButton("📞 Contact Store", callback_data="contact"),
    InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_categories")]
  ]
  

  # If it's cached, skip all download logic entirely
  if cached_file_id:
    print(f"Serving image for {product_id} from Telegram Cache!")
    await query.message.reply_photo(
        photo=cached_file_id, # Telegram reuses the existing file instantly
        caption=caption,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    await query.message.delete()
    return


  # 3. FALLBACK: If not cached, handle the image download (Only happens ONCE per product)
  image_url = product.get("Image_url", "").strip()
  is_valid_url = image_url.startswith("https://") or image_url.startswith("http://")

  if is_valid_url:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                image_url, 
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, 
                timeout=10.0
            )
            
        if response.status_code == 200:
            photo_file = io.BytesIO(response.content)
            photo_file.name = "product.jpg"
            
            # Capture the message object that Telegram returns
            sent_message = await query.message.reply_photo(
                photo=photo_file,
                caption=caption,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            
            # Extract Telegram's file ID and save it into our memory cache
            if sent_message.photo:
                # sent_message.photo[-1] targets the highest resolution version
                TELEGRAM_IMAGE_CACHE[product_id] = sent_message.photo[-1].file_id
                print(f"Saved {product_id} image to Telegram Cache.")

            await query.message.delete()
        else:
            raise Exception(f"Image host responded with status code {response.status_code}")
            
    except Exception as e:
        print(f"Failed to send image for {product_id}. Error: {e}")
        await query.edit_message_text(
            text=f"<i>[Image unavailable]</i>\n\n{caption}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
  else:
    await query.edit_message_text(
        text=caption,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


# preloading products to improve snappiness of bot
async def post_init(application):
  print("Preloading product cache...")
  sheets.get_all_products()
  print("Cache ready — bot is live!")


#-------------------------------------------------------------------------
#-----------------------Cart Function-------------------------------------
#-------------------------------------------------------------------------
# add to cart function:
async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    product_id = query.data.replace("addcart_", "")
    product = sheets.get_product_by_id(product_id)
    
    if not product:
        await query.answer("Product not found.", show_alert=True)
        return
    
    # check stock before adding
    if product["Stock_quantity"] <= 0:
        await query.answer("Sorry, this product is out of stock.", show_alert=True)
        return
    
    cart_manager.add_to_cart(context, product)
    await query.answer(f"✅ {product['Product_name']} added to cart!", show_alert=True)


#-------------------------------------------------------------------------
#----------------------View Cart Function---------------------------------
#-------------------------------------------------------------------------
async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    summary = cart_manager.get_cart_summary(context)
    
    if cart_manager.is_cart_empty(context):
        buttons = [[InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_categories")]]
    else:
        buttons = [
            [InlineKeyboardButton("✅ Checkout", callback_data="checkout")],
            [InlineKeyboardButton("🗑️ Clear Cart", callback_data="clear_cart"),
             InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_categories")]
        ]
    
    try:
        await query.message.delete()
    except Exception as e:
        print(f"Could not delete message: {e}")

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"🛒 <b>Your Cart</b>\n\n{summary}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons)
)
    

async def clear_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cart_manager.clear_cart(context)
    await query.edit_message_text(
        "🗑️ Cart cleared.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_categories")]
        ])
    )


#-------------------------------------------------------------------------
#-----------------------Checkout Function---------------------------------
#-------------------------------------------------------------------------

# WAITING_NAME, WAITING_UPI_ID ,WAITING_PHONE = range(3)  # conversation states

# async def checkout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()
    
#     if cart_manager.is_cart_empty(context):
#         await context.bot.send_message(
#            chat_id = query.message.chat_id,
#            text="Your cart is empty.")
#         return ConversationHandler.END
    
#     await query.message.delete()
#     await context.bot.send_message(
#         chat_id = query.message.chat_id,
#         text="📝 <b>Checkout:</b>\n\n<b>Please enter your full name</b>:",
#         parse_mode="HTML"
#     )
#     return WAITING_NAME


# async def checkout_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data["checkout_name"] = update.message.text.strip()
#     await update.message.reply_text("📱 <b>Now enter upi id you are going to use for payment</b>:", parse_mode="HTML")
#     return WAITING_UPI_ID


# async def checkout_upi_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     context.user_data["checkout_upi_id"] = update.message.text.strip()
#     await update.message.reply_text("📱 <b>Now enter your phone number</b>:", parse_mode="HTML")
#     return WAITING_PHONE


# async def checkout_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     phone = update.message.text.strip()
#     name = context.user_data.get("checkout_name", "Unknown")
#     upi_id = context.user_data.get("checkout_upi_id","Unknown")
#     user_id = update.effective_user.id
#     cart = cart_manager.get_cart(context)
    
#     await update.message.reply_text("⏳ Placing your order...")
    
#     try:
#         order_id = await asyncio.to_thread(
#             sheets.write_order, name, upi_id ,phone, user_id, cart
#         )
        
#         summary = cart_manager.get_cart_summary(context)
#         amount = cart_manager.get_cart_total(context)
#         cart_manager.clear_cart(context)
        
#         await update.message.reply_text(
#             f"✅ <b>Order Placed!</b>\n\n"
#             f"Order ID: <b>{order_id}</b>\n"
#             f"Name: {name}\n"
#             f"Phone: {phone}\n"
#             f"Upi Id: {upi_id}\n\n "
#             f"{summary}\n\n"
#             f"💳 <b>Pay By UPI:</b>\n"
#             f"UPI ID: <code>{config.UPI_ID}</code>\n {config.UPI_NAME}\n"
#             f"Amount: ₹{amount}\n\n"
#             f"After paying, tap <b>I've Paid</b> to notify the store.\n"
#             f"We'll contact you shortly to confirm delivery.",
#             parse_mode="HTML",
#             reply_markup=InlineKeyboardMarkup([
#                 [InlineKeyboardButton("✅ I've Paid", callback_data=f"paid_{order_id}")], 
#                 [InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order_id}")]
#             ])
#         )
#     except Exception as e:
#         print(f"Checkout error: {e}")
#         await update.message.reply_text(
#             "❌ Something went wrong placing your order. Please contact the store directly.",
#             reply_markup=InlineKeyboardMarkup([
#                 [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_categories")]
#             ])
#         )
    
#     return ConversationHandler.END

WAITING_NAME, WAITING_PHONE = range(2)  # removed WAITING_UPI_ID — was range(3)

async def checkout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if cart_manager.is_cart_empty(context):
        await context.bot.send_message(
           chat_id = query.message.chat_id,
           text="Your cart is empty.")
        return ConversationHandler.END
    
    await query.message.delete()
    await context.bot.send_message(
        chat_id = query.message.chat_id,
        text="📝 <b>Checkout:</b>\n\n<b>Please enter your full name</b>:",
        parse_mode="HTML"
    )
    return WAITING_NAME


async def checkout_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["checkout_name"] = update.message.text.strip()
    await update.message.reply_text("📱 <b>Now enter your phone number</b>:", parse_mode="HTML")
    return WAITING_PHONE

# checkout_upi_id function fully removed — not needed anymore


async def checkout_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    name = context.user_data.get("checkout_name", "Unknown")
    user_id = update.effective_user.id
    cart = cart_manager.get_cart(context)
    
    await update.message.reply_text("⏳ Placing your order...")
    
    try:
        order_id = await asyncio.to_thread(
            sheets.write_order, name, phone, user_id, cart
        )
        
        summary = cart_manager.get_cart_summary(context)
        amount = cart_manager.get_cart_total(context)
        cart_manager.clear_cart(context)
        
        # --- NEW: create Razorpay payment link instead of showing static UPI ---
        pay_url, payment_link_id = await asyncio.to_thread(
            create_payment_link,
            order_id, amount, name, phone, config.STORE_NAME
        )
        
        sent_message = await update.message.reply_text(
            f"✅ <b>Pay to confirm your order!</b>\n\n"
            f"Order ID: <b>{order_id}</b>\n"
            f"Name: {name}\n"
            f"Phone: {phone}\n\n"
            f"{summary}\n\n"
            f"💳 <b>Complete Payment:</b>\n"
            f"Amount: ₹{amount}\n"
            f"Pay here: {pay_url}\n\n"
            f"You'll get your invoice automatically once payment is confirmed.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel_order_{order_id}")]
            ])
        )
        payment_messages[order_id] = (update.effective_chat.id, sent_message.message_id)

    except Exception as e:
        print(f"Checkout error: {e}")
        await update.message.reply_text(
            "❌ Something went wrong placing your order. Please contact the store directly.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_categories")]
            ])
        )
    
    return ConversationHandler.END

async def checkout_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Checkout cancelled.")
    return ConversationHandler.END


#-------------------------------------------------------------------------
#-----------------------Payment Confirmation Function---------------------
#-------------------------------------------------------------------------
# async def payment_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     await query.answer()
#     order_id = query.data.replace("paid_", "")
    
#     # update status in sheet
#     await asyncio.to_thread(sheets.update_order_status, order_id, "Payment Confirmation Pending")
    
#     await query.edit_message_text(
#         f"🎉 Thank you! Order <b>{order_id}</b> payment claim received.\n"
#         f"Your invoice will be sent sortly after payment verification by the store,\n Please wait.",
#         parse_mode="HTML"
#     )
#     # notify owner
#     await context.bot.send_message(
#         chat_id=config.OWNER_ID,
#         text=f"💰 Payment claimed for Order {order_id}\nVerify UPI and confirm!"
#     )

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = query.data.replace("cancel_order_", "")
    
    await asyncio.to_thread(sheets.update_order_status, order_id, "Cancelled")
    
    await query.edit_message_text(
        "❌ Order cancelled.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_categories")]
        ])
    )




#-------------------------------------------------------------------------
#-----------------------Checkout handler Wrapper----------------------
#-------------------------------------------------------------------------
warnings.filterwarnings("ignore", message=".*per_message=False.*", category=PTBUserWarning)

checkout_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(checkout_start, pattern="^checkout$") , CommandHandler("checkout",checkout_start)],
    states={
        WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, checkout_name)],
        WAITING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, checkout_phone)]
    },
    fallbacks=[CommandHandler("cancel", checkout_cancel)],
    per_message= False
)


#-------------------------------------------------------------------------
#-----------------------Contact Handler-----------------------------------
#-------------------------------------------------------------------------
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"📞 <b>Contact Us</b>\n\n"
            f"📱 Phone: {config.STORE_PHONE}\n\n"
            f"📧 Email: {config.STORE_EMAIL}\n\n"
            f"📍 Address: {config.STORE_ADDRESS}\n\n"
            f"🕐 Hours: {config.STORE_HOURS}"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🚨 File Complaint", callback_data="complaint"),
            InlineKeyboardButton("💬 Enquiry", callback_data="enquiry")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_categories")]])
        )


#-------------------------------------------------------------------------  
#-----------------------Complaint Handler---------------------------------
#-------------------------------------------------------------------------
# conversation states
COMP_NAME, COMP_ORDER_ID, COMP_ISSUE = range(3, 6)


async def complaint_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="📝 <b>File a Complaint</b>\n\nPlease enter your <b>full name</b>:",
        parse_mode="HTML"
    )
    return COMP_NAME

async def complaint_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["comp_name"] = update.message.text.strip()
    await update.message.reply_text(
        "🔢 Enter your <b>Order ID</b> (e.g. ORD-20260623151230)\nIf you don't have one, type <b>N/A</b>:",
        parse_mode="HTML"
    )
    return COMP_ORDER_ID

async def complaint_order_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["comp_order_id"] = update.message.text.strip()
    await update.message.reply_text(
        "📣 Describe your <b>issue</b> in detail:",
        parse_mode="HTML"
    )
    return COMP_ISSUE

async def complaint_issue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    issue = update.message.text.strip()
    name = context.user_data.get("comp_name", "Unknown")
    order_id = context.user_data.get("comp_order_id", "N/A")
    user_id = update.effective_user.id

    await update.message.reply_text("⏳ Submitting your complaint...")

    try:
        complaint_id = await asyncio.to_thread(
            sheets.write_complaint, user_id, name, order_id, issue
        )
        await update.message.reply_text(
            f"✅ <b>Complaint Submitted!</b>\n\n"
            f"Complaint ID: <b>{complaint_id}</b>\n"
            f"We'll look into it and contact you shortly.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_categories")]
            ])
        )
        await context.bot.send_message(
            chat_id=config.OWNER_ID,
            text=f"🚨 New complaint from {name}\nOrder: {order_id}\nIssue: {issue}\nID: {complaint_id}"
        )
    except Exception as e:
        print(f"Complaint error: {e}")
        await update.message.reply_text(
            "❌ Something went wrong. Please contact the store directly.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_categories")]
            ])
        )
    return ConversationHandler.END

async def complaint_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Complaint cancelled.")
    return ConversationHandler.END


#-------------------------------------------------------------------------
#-----------------------Complaint Handler Wrapper-------------------------
#-------------------------------------------------------------------------
complaint_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(complaint_start, pattern="^complaint$"),
                  CommandHandler("complaint", complaint_start)],
    states={
        COMP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_name)],
        COMP_ORDER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_order_id)],
        COMP_ISSUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_issue)]
    },
    fallbacks=[CommandHandler("cancel", complaint_cancel)],
    per_message=False
)


#-------------------------------------------------------------------------
#-----------------------Enquiry Handler-----------------------------------
#-------------------------------------------------------------------------
ENQ_NAME, ENQ_PHONE, ENQ_PRODUCT, ENQ_MESSAGE = range(6, 10)


async def enquiry_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="💬 <b>Product Enquiry</b>\n\nPlease enter your <b>full name</b>:",
        parse_mode="HTML"
    )
    return ENQ_NAME

async def enquiry_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["enq_name"] = update.message.text.strip()
    await update.message.reply_text("📱 Enter your <b>phone number</b>:", parse_mode="HTML")
    return ENQ_PHONE

async def enquiry_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["enq_phone"] = update.message.text.strip()
    await update.message.reply_text(
        "🛍️ Which <b>product</b> are you enquiring about?",
        parse_mode="HTML"
    )
    return ENQ_PRODUCT

async def enquiry_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["enq_product"] = update.message.text.strip()
    await update.message.reply_text(
        "💬 Enter your <b>message or question</b>:",
        parse_mode="HTML"
    )
    return ENQ_MESSAGE

async def enquiry_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text.strip()
    name = context.user_data.get("enq_name", "Unknown")
    phone = context.user_data.get("enq_phone", "Unknown")
    product = context.user_data.get("enq_product", "Unknown")
    user_id = update.effective_user.id

    await update.message.reply_text("⏳ Submitting your enquiry...")

    try:
        enquiry_id = await asyncio.to_thread(
            sheets.write_enquiry, user_id, name, phone, product, message
        )
        await update.message.reply_text(
            f"✅ <b>Enquiry Submitted!</b>\n\n"
            f"Enquiry ID: <b>{enquiry_id}</b>\n"
            f"We'll get back to you shortly.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_categories")]
            ])
        )
        await context.bot.send_message(
            chat_id=config.OWNER_ID,
            text=f"💬 New enquiry from {name}\nPhone: {phone}\nProduct: {product}\nMessage: {message}\nID: {enquiry_id}"
        )
    except Exception as e:
        print(f"Enquiry error: {e}")
        await update.message.reply_text(
            "❌ Something went wrong. Please contact the store directly.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_categories")]
            ])
        )
    return ConversationHandler.END

async def enquiry_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Enquiry cancelled.")
    return ConversationHandler.END


#-------------------------------------------------------------------------
#-----------------------Enquiry Handler Wrapper---------------------------
#-------------------------------------------------------------------------
enquiry_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(enquiry_start, pattern="^enquiry$"),
                  CommandHandler("enquiry", enquiry_start)],
    states={
        ENQ_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enquiry_name)],
        ENQ_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enquiry_phone)],
        ENQ_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enquiry_product)],
        ENQ_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enquiry_message)]
    },
    fallbacks=[CommandHandler("cancel", enquiry_cancel)],
    per_message=False
)



#-------------------------------------------------------------------------
#-----------------------Refresh Command-----------------------------------
#-------------------------------------------------------------------------
async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.OWNER_ID:
        return
    sheets.clear_cache()
    await update.message.reply_text("✅ Cache cleared — next request fetches fresh data.")


#-------------------------------------------------------------------------
#-----------------------Error Handler-------------------------------------
#-------------------------------------------------------------------------
async def error_handler(update, context):
    print(f"ERROR: {context.error}")
    
    # notify user something went wrong
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ Something went wrong. Please try again or use /start to restart.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_categories")]
            ])
        )


#------------------------------------------------------------------------
#--------------------------Running flask Function------------------------
#------------------------------------------------------------------------
def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


#-------------------------------------------------------------------------
#-----------------------Main Function-------------------------------------
#-------------------------------------------------------------------------
def main():
    # handlers
    app.add_handler(CommandHandler("start",start))
    # error handler
    app.add_error_handler(error_handler)
  
    # Callback query handlers:
    app.add_handler(CallbackQueryHandler(add_to_cart, pattern="^addcart_"))
    app.add_handler(CallbackQueryHandler(clear_cart, pattern="^clear_cart$"))
    app.add_handler(CallbackQueryHandler(category_selected,pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(product_selected, pattern="^prod_"))
    app.add_handler(CallbackQueryHandler(back_to_categories,    pattern="^back_to_categories$"))

    # conversation handler:
    app.add_handler(checkout_conv)
    app.add_handler(complaint_conv)
    app.add_handler(enquiry_conv)

    # Payment handler:
    # app.add_handler(CallbackQueryHandler(payment_confirmed, pattern="^paid_"))
    app.add_handler(CallbackQueryHandler(cancel_order, pattern="^cancel_order_"))


    # contact handler:
    app.add_handler(CallbackQueryHandler(contact, pattern="^contact$"))
    app.add_handler(CommandHandler("contact",contact))

    # refresh command:
    app.add_handler(CommandHandler("refresh", refresh))

    # announcement handler:
    app.add_handler(CommandHandler("announce", announce))

    # View Cart handlers:
    app.add_handler(CallbackQueryHandler(view_cart, pattern="^view_cart$"))
    app.add_handler(CommandHandler("view_cart",view_cart))

    # fetching updates
    app.run_polling()



# calling main()
if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()
    main()