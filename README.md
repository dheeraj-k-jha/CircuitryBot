# CircuitryBot 🤖🔌

An automated, Python-based storefront bot designed to manage shopping carts, process orders, and streamline operations for the "Circuitry" store. Whether you are managing custom PC components or general electronics, this bot handles the checkout flow while logging everything directly to Google Sheets.

## 🌟 Features

* **Interactive Shopping Cart (`cart_manager.py`):** Allows users to seamlessly add products, review their selections, and manage their cart before checkout.
* **Google Sheets Database (`sheets.py`):** Acts as the central database, automatically syncing inventory and logging incoming orders to the "Circuitry" spreadsheet via the Google Drive API.
* **UPI Payment Integration:** Automatically provides customers with the store's UPI ID, Name, and QR details for frictionless payments.
* **Always-On Hosting (`keep_alive.py`):** Built-in Flask/web server script designed to ping the bot and keep it awake 24/7 on platforms like Render or Replit.

## 🛠️ Tech Stack

* **Language:** Python 3
* **Database:** Google Sheets API (`gspread` / `google-auth`)
* **Environment Management:** `python-dotenv`

## 🚀 Installation & Local Setup

### 1. Clone the Repository
```bash
git clone [https://github.com/dheeraj-k-jha/CircuitryBot.git](https://github.com/dheeraj-k-jha/CircuitryBot.git)
cd CircuitryBot

### Try it on:

[Telegram Link](https://t.me/StoreBuddyy_Bot)