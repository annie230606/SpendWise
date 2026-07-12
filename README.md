# SpendWise: Your AI-Powered Financial Intelligence Agent

SpendWise is a personal finance assistant that lives in WhatsApp, helping you manage your money through simple, real-time conversations instead of complex manual tracking.

---

### 💡 Problem Statement

Traditional finance apps are passive. They require you to manually log expenses, categorize them, and open the app to check your balance. Most people quit after a week because it feels like a chore. The money is usually gone by the time you realize you’ve overspent.

### 🚀 Solution Overview

SpendWise acts as an **intelligent, event-driven agent**. The system reads SMS from banks when you make a purchase and automatically logs it, categorizes it, and checks it against your budget. It stays silent when you’re doing well and only alerts you when your budget is at risk.

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

---


### 🛠️ Tech Stack
* **Language:** Python 3.9+
* **Frameworks:** FastAPI, LangGraph
* **Intelligence:** Phi-3-mini-4k-instruct-q4.gguf (via HuggingFace)
* **Database:** Supabase (PostgreSQL)
* **Messaging:** Twilio API for WhatsApp
* **Data Processing:** Pandas

---

### 📱 Usage Instructions
* **Onboarding:** Send "Hi" to your Twilio WhatsApp number.
* **Manual Logging:** Simply text the bot (e.g., "Spent 500 on dinner") to log and categorize expenses instantly.
* **Status:** Send `/status` to view your current budget balance.
* **Reset:** Send `/reset-all-data` to clear the database.

---

### 🎥 Demo & Visuals
* **Demo Video:** [Insert Link Here]
* **Screenshots:** [Insert Link Here]

### 🚧 Future Scope & Limitations
* **Limitations:** Requires sufficient local RAM for the LLM to perform audits quickly.
* **Future Scope:** Integrating real-time bank account syncing (via Plaid/Salt Edge) and multi-currency support.

### 📝 License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.


