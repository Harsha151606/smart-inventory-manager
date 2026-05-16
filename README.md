# 📦 Smart Inventory Manager

A modern, mobile-first inventory management system powered by AI. Built with a sleek glassmorphism UI, this app allows you to track stock, predict inventory depletion, and generate/scan QR codes for fast access.

## ✨ Features

- **📱 Mobile-First Design**: A beautiful, app-like interface using Tailwind CSS and custom glassmorphism styles.
- **🧠 AI Intelligence Engine**: Automatically calculates daily consumption rates, predicts when stock will run out, detects anomalies, and suggests optimal low-stock thresholds.
- **📷 QR Code Integration**: Auto-generates a unique QR code for every item. Includes a built-in camera scanner to instantly look up items physically.
- **⚡ Real-time Dynamic Sync**: A global auto-sync engine polls the database in the background every 10 seconds, ensuring that stock numbers are always up-to-date across multiple devices without needing a page refresh.
- **🏷️ Custom Categories**: Add, manage, and categorize items smoothly with on-the-fly category creation.
- **📊 Interactive Dashboard**: Keep an eye on your inventory health with at-a-glance stats, critical low-stock alerts, and recent transaction logs.

## 🛠️ Tech Stack

- **Backend**: Python, Flask, SQLite
- **Frontend**: HTML5, Vanilla JavaScript, Tailwind CSS (via CDN)
- **Background Tasks**: APScheduler
- **Hardware Integrations**: `html5-qrcode` for camera scanning, `qrcode[pil]` for generation.

## 🚀 Getting Started

### Prerequisites
Make sure you have Python 3 installed on your system.

### 1. Clone the repository
```bash
git clone https://github.com/Harsha151606/smart-inventory-manager.git
cd smart-inventory-manager
```

### 2. Install Dependencies
Install the required Python packages:
```bash
pip install -r requirements.txt
```

### 3. Run the App
Start the Flask backend and AI engine:
```bash
python3 app.py
```

### 4. Access the App
Open your web browser and navigate to:
**[http://127.0.0.1:5000](http://127.0.0.1:5000)**

## 💡 How the AI Works

The `InventoryAI` class monitors all inventory transactions (additions and removals). It calculates a rolling average of your "burn rate" (how fast an item is consumed). Based on standard deviation and historical data, the AI will issue alerts on the dashboard suggesting new inventory thresholds to prevent you from ever running out of stock.
