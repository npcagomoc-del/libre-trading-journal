# Install Libre Trading Journal on Windows

Libre Trading Journal is based on [Trading-Journal-AI](https://github.com/simonro/Trading-Journal-AI) by Simon / simonro / Tape to Edge, under the original MIT license. This source preview runs on your own PC. Core journaling is free; optional API providers may charge for usage.

**Install with an AI assistant:** Paste the [installation prompt](AI-INSTALL.md#copy-this-installation-prompt) into an assistant with terminal and file access on this PC. You can also follow the manual steps below.

## 1. Download the source

Open [Libre Trading Journal on GitHub](https://github.com/npcagomoc-del/libre-trading-journal) and choose **Code → Download ZIP**, or [download main.zip directly](https://github.com/npcagomoc-del/libre-trading-journal/archive/refs/heads/main.zip).

Right-click the ZIP → **Extract All**. Move the extracted `libre-trading-journal-main` folder somewhere convenient, for example `C:\Projects\libre-trading-journal`. Prefer a folder outside OneDrive or other sync services because the running app writes a local SQLite database.

Open the folder containing `setup.bat`, `launch.bat`, `backend`, and `frontend`. Run commands from this folder, rather than from inside the ZIP or a parent directory.

If you prefer Git:

```powershell
git clone https://github.com/npcagomoc-del/libre-trading-journal.git
cd libre-trading-journal
```

## 2. Install prerequisites

1. Install [Python](https://www.python.org/downloads/) **3.11 or newer**. Select **Add python.exe to PATH** during installation. The Windows backend was checked with Python 3.12.10.
2. Install [Node.js](https://nodejs.org/) **24**, including npm. Leave the installer option to add it to PATH enabled.
3. Open a new PowerShell window and check:

```powershell
python --version
node --version
npm.cmd --version
```

If a command is missing, repair the corresponding installation and reopen PowerShell.

## 3. Set up and launch

1. Double-click **setup.bat** once. It downloads dependencies, creates `.venv`, and creates `backend\.env` from an empty optional market-data template. Internet access is needed for installation. Keep the terminal open until it reports **Setup finished**.
2. Double-click **launch.bat**. Keep the Backend and Frontend windows open while using the journal.
3. Wait for backend startup and frontend compilation, then open **http://localhost:3010** in a browser **on this PC**. Port 8010 is the API.
4. Create your first journal account, then import a broker CSV or add a trade. Follow the [user tutorial](USER-GUIDE.md).

For the next session, use `launch.bat`; setup is only needed initially or after dependency updates. Press **Ctrl+C** in both server windows to stop the app.

## 4. Optional AI and backups

In **More → Settings → AI provider**, choose ChatGPT sign-in, OpenAI API key, direct Claude API key, or OpenRouter API key. An OpenRouter key belongs in the OpenRouter option, even when you choose a Claude model. Follow the [provider tutorial](AI-PROVIDERS.md); provider tests can consume plan usage or paid API credits.

In **More → Settings → Backup & restore**, download a journal backup. Store it privately: it contains trading data and diary attachments. See the [backup tutorial](BACKUP-RESTORE.md).

The GitHub download starts with an **empty journal**. To move an existing journal, download its backup on the original PC, transfer that ZIP privately, then check and restore it on the new PC. Restore replaces the destination journal and creates a recovery copy first. Credentials are excluded; reconnect AI and market-data services on the new installation.

## 5. If it will not start

Open http://127.0.0.1:8010/ to check the backend. If it returns `{"status":"ok"}` but 3010 fails, inspect the Frontend window. If 8010 also fails, inspect the Backend window. Preserve the first error and use the [startup and error recovery guide](TROUBLESHOOTING.md), which includes manual commands, PATH and port problems, AI errors, and backup recovery.

Do not delete the database to repair startup. Do not post `.env`, keys, tokens, backups, or broker statements in public issues.
