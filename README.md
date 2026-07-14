# SpendWise: Your AI-Powered Financial Intelligence Agent

SpendWise is a personal finance assistant that lives in WhatsApp, helping you manage your money through simple, real-time conversations instead of complex manual tracking.

---

### 💡 Problem Statement
Traditional finance apps are passive. They require you to manually log expenses, categorize them, and open the app to check your balance. Most people quit after a week because it feels like a chore. The money is usually gone by the time you realize you’ve overspent.

### 🚀 Solution Overview
SpendWise acts as an **intelligent, event-driven agent**. The system reads SMS from banks when you make a purchase and automatically logs it, categorizes it, and checks it against your budget. It stays silent when you’re doing well and only alerts you when your budget is at risk.

**Why WhatsApp?**
* **Zero-Download Friction:** SpendWise lives inside the app you already use every day. No new app to download, no new account to manage.
* **Always-On Notifications:** By leveraging WhatsApp’s existing notification infrastructure, you receive budget alerts exactly where you already communicate, ensuring high engagement without "notification fatigue."

### 🧠 On-Device AI Explanation
To ensure financial privacy, SpendWise uses an **In-Process LLM (Phi-3-mini-4k-instruct-q4.gguf)**. By running the AI audit locally, your sensitive transaction data never leaves your local environment, while still providing human-like understanding of your spending habits.

### 🛠️ Technical Deep Dive & Optimization
* **Target Hardware:** Optimized for consumer-grade laptop CPUs (Windows/macOS), ensuring **100% data privacy** by maintaining a strictly local execution environment.
* **Model Footprint:** Uses a quantized **4-bit (2.3GB) Phi-3-mini-4k-instruct** model. This quantization reduced the memory footprint by over 40%, allowing it to run comfortably in local RAM.
* **Performance Metrics:** Maintains a steady inference rate of **~12–15 tokens per second** on standard laptop CPUs, providing a fluid, near-instantaneous experience.
* **Customization (Agentic Orchestration):** We implemented a **Stateful Multi-Agent Architecture** using **LangGraph**, delegating tasks to three nodes:
    * **The Auditor:** Specialized entity extraction for transaction parsing.
    * **The Coach:** Logic-driven budgetary analysis and guardrail enforcement.
    * **The Gatekeeper:** Secure command-processing and MFA verification.

### 🛡️ Privacy & Execution Transparency
SpendWise is designed for 100% data sovereignty:
* **On-Device (Local):** Entity extraction, categorization, and coaching logic run entirely in-process. No transaction data ever hits an external AI API.
* **Cloud (Backend):** We use Supabase and Twilio for secure, persistent storage and messaging only. No transaction text is shared with these services in a way that allows them to "train" on your private data.

---

### 📋 Prerequisites
Before installation, ensure you have:
* **Python 3.9+** installed on your system.
* A **Supabase** account (for PostgreSQL storage).
* A **Twilio** account (with WhatsApp Sandbox access).
* An **SMS Forwarder** app (e.g., [SMS Forwarder](https://play.google.com/store/apps/details?id=com.sms.forwarder)) installed on your Android device to relay bank notifications to the bot.

### 🧠 Model Setup (Required)
To run SpendWise locally, you must provide the LLM file:
1. Download `Phi-3-mini-4k-instruct-q4.gguf` from [Hugging Face](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf).
2. Place the file inside the `/models` directory.
3. Your final path should be `models/Phi-3-mini-4k-instruct-q4.gguf`.

### 🛠️ Tech Stack
* **Language:** Python 3.9+
* **Frameworks:** FastAPI, LangGraph
* **Intelligence:** Phi-3-mini-4k-instruct-q4.gguf (via HuggingFace)
* **Database:** Supabase (PostgreSQL)
* **Messaging:** Twilio API for WhatsApp
* **Data Processing:** Pandas

---

### ⚙️ Setup Instructions
1. **Clone the repo:** `git clone https://github.com/annie230606/SpendWise`
2. **Install:** `pip install -r requirements.txt`
3. **Configure:** Create a `.env` file (see `.env.example`).
4. **Run:** `uvicorn api.webhook:app --reload --port 8000`
5. **Expose:** Use `ngrok http 8000` to tunnel your local webhook to Twilio.

### 📱 Usage Instructions
* **Onboarding:** Send "Hi" to your Twilio WhatsApp number.
* **Logging:** The system automatically processes bank SMS alerts.
* **Status:** Send `/status` to view your current budget balance.
* **Reset:** Send `/reset-all-data` to clear the database.

---

### 🎥 Demo & Visuals
* **Demo Video + Screenshots:** [https://drive.google.com/drive/folders/1KGVj-Zla1izhoSc_UfcaHCaSWnS176BY?usp=sharing]

### 🚧 Future Scope & Limitations
* **Limitations:** Requires sufficient local RAM for the LLM to perform audits quickly.
* **Future Scope:** Integrating real-time bank account syncing (via Plaid/Salt Edge) and multi-currency support.

### 📝 License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.