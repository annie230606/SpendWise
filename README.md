# SpendWise: Intelligent Financial Agent

SpendWise is a local-first, agentic financial assistant designed to provide real-time budget tracking and spending analysis via automated message processing. By leveraging local LLMs and a modular agentic architecture, SpendWise ensures that sensitive financial data never leaves your local execution environment.

## 🏗️ Architecture Philosophy
This project utilizes a multi-agent orchestration framework (**LangGraph**) to separate concerns, ensuring high reliability and maintainability:

*   **The Auditor**: Responsible for parsing raw, unstructured financial SMS/text inputs into clean, normalized JSON.
*   **The Coach**: Analyzes processed transaction data against historical budget goals to provide actionable financial insights.
*   **Orchestration**: All workflows are managed by a central graph controller to guarantee transactional integrity.

## 🚀 Key Features (In Development)
- [ ] **Privacy-First**: 100% local execution using Phi-3-mini-4k-instruct.
- [ ] **Agentic Workflow**: Sequential processing pipeline for parsing, analysis, and validation.
- [ ] **Budget Awareness**: Real-time logic to track spending against monthly caps.
- [ ] **Automated Alerting**: Integrated WhatsApp notification system.

## 🛠️ Tech Stack
- **Orchestration**: LangGraph
- **LLM Engine**: Phi-3-mini-4k-instruct (Local)
- **Database**: Supabase (PostgreSQL)
- **API/Communication**: FastAPI & Twilio

## 📋 Status
*Phase 1: Architecture & Core Logic Initialization.* 
(Currently building out modular agent nodes and orchestration flow.)