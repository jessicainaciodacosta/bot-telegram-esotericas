# 🤖 Telegram Automation & Curation Bot (Python)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Poetry](https://img.shields.io/badge/Poetry-Dependency%20Management-blueviolet.svg)](https://python-poetry.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An automated Python system built for curation, data processing, and targeted content delivery on Telegram. This project focuses on clean architecture, asynchronous data handling, and continuous integration.

---

## 🚀 Architecture & Tech Stack

The project is built following professional backend development standards:

- **Language:** Python 3.10+
- **Dependency Management:** Poetry (`pyproject.toml`)
- **API Communication:** Asynchronous integration with the Telegram API and external partner APIs (e.g., Shopee GraphQL API).
- **Data Persistence:** Google Sheets API integration (`gspread-asyncio`) for tracking and history.
- **Automation & CI/CD:** Workflows configured via GitHub Actions for automated execution and maintenance.

---

## 📁 Project Structure

```text
bot-telegram-esotericas/
├── .github/workflows/    # CI/CD pipelines and automation (GitHub Actions)
├── config/               # Configuration modules and environment variable parsing
├── data/                 # Initial data files and persistence layers
├── modules/              # Business logic, API clients, and parsers
├── .env.example          # Template for required environment variables
├── .gitignore            # Files ignored by version control
├── main.py               # Application entrypoint
├── poetry.lock           # Locked dependency versions
└── pyproject.toml        # Project configuration and Poetry dependencies
⚙️ How to Run Locally
Follow the steps below to set up and run the project on your machine:

1. Prerequisites
Make sure you have Python and Poetry installed on your system.

2. Clone the repository
Bash
git clone [https://github.com/jessicainaciodacosta/bot-telegram-esotericas.git](https://github.com/jessicainaciodacosta/bot-telegram-esotericas.git)
cd bot-telegram-esotericas
3. Install dependencies
Bash
poetry install
4. Configure Environment Variables
Copy the example file .env.example to a new file named .env in the root directory:

Bash
cp .env.example .env
Open the generated .env file and fill in your actual credentials (Telegram tokens, App IDs, and API keys).

5. Run the application
Activate the Poetry virtual environment and execute the main script:

Bash
poetry run python main.py
🛡️ Security & Best Practices
Zero Hardcoded Secrets: No API keys or sensitive tokens are exposed in the source code. Credential management is handled strictly via environment variables (.env).

Git Protection: The .env file is properly declared in .gitignore to prevent accidental leaks in version control.


---

<FollowUp>
Would you like to copy this text directly into your GitHub repository, or is there any other project detail you'd like to tweak first?
</FollowUp>

<ElicitationsGroup>
</ElicitationsGroup>
