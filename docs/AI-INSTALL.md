# Install Libre Trading Journal with an AI assistant

Open an AI coding assistant on the PC where you want to install Libre Trading Journal. The assistant needs terminal and file access. If you already downloaded the repository, open its folder in the assistant, then paste the installation prompt below.

A chat-only assistant can explain the commands but cannot run them on your PC. If your assistant runs on another computer, it will install the app there; that computer's `localhost` address will not open the app on yours.

## Copy this installation prompt

```text
Install and run Libre Trading Journal on this computer.
Repository: https://github.com/npcagomoc-del/libre-trading-journal

Use your terminal and file tools to complete setup. If those tools are
unavailable, explain what I need to run manually.

1. Check the operating system and current folder. If this is already a
   Libre Trading Journal checkout, use it and preserve local changes.
   Otherwise, clone the repository or extract its public ZIP into a new
   user-writable folder outside cloud-sync folders. Do not overwrite an
   existing folder or change an unrelated repository.

2. Read AGENTS.md, docs/PROJECT-STATUS.md, docs/INSTALL-WINDOWS.md,
   docs/DEVELOPER-GUIDE.md and docs/TROUBLESHOOTING.md. Run setup from the
   app root, which contains backend/, frontend/ and setup.bat.

3. Check Python 3.11+ and Node.js 24 with npm. Python 3.12 was tested on
   Windows. Install missing prerequisites from official sources, keeping
   existing installations intact. If an installer needs my approval or a
   click, tell me which action is needed and resume afterward.

4. Follow the setup commands for my operating system. Create or reuse
   .venv, install backend requirements with its Python interpreter, and
   run npm ci from frontend/. On Windows, use npm.cmd if PowerShell blocks
   npm.ps1. Use the manual commands if setup.bat waits for keyboard input.
   Create backend/.env from .env.example only if it is missing. Leave an
   existing .env and credential stores intact, without opening them.
   Use the repository's dependency versions. If a command fails, inspect
   its first error and fix the setup problem before continuing.

5. Keep existing journal data and uploads. Before starting an existing
   journal that may need migration, follow docs/DATA-GUIDE.md to take a
   consistent backup. Do not reset the database, seed demo data, restore
   a backup or import trades during installation. Leave API keys and
   sign-in credentials for me to enter in the app.

6. Check for an existing Libre Trading Journal server before launching
   another copy. Start one backend from backend/ on 127.0.0.1:8010.
   Start the frontend from frontend/ with HOST=127.0.0.1 and PORT=3010.
   Keep both processes running after your tool call ends. If either port
   is occupied, identify the process; do not stop an unrelated application.
   Keep these ports because ChatGPT sign-in uses them.

7. Check that http://127.0.0.1:8010/ returns {"status":"ok"} and
   http://localhost:3010 responds. If browser tools are available, open
   the journal and check for page or connection errors. Report HTTP and
   browser checks separately. Use docs/TROUBLESHOOTING.md for failures.

Send me the installation folder, app URL, checks performed, and commands
to stop and restart the app. Include any unresolved error and the next
action needed. Explain how to create my first journal account and where
to find AI provider settings and backup/restore. A new installation starts
empty. Do not make paid AI requests as part of setup.
```

If the assistant cannot keep its server sessions running, start the app with `launch.bat` on Windows after setup. Configure ChatGPT, API keys and MT5 separately through Settings.

## Copy this prompt if the app will not open

Open the existing Libre Trading Journal folder in your assistant and paste:

```text
Fix the startup problem in Libre Trading Journal on this computer.
Read AGENTS.md, docs/PROJECT-STATUS.md and docs/TROUBLESHOOTING.md.

Check the app folder, .venv, Python/Node/npm paths, existing server processes
and ports 8010/3010. Check backend health and the frontend response. Read
the first startup or connection error and fix its cause.

Keep journal records, uploads, .env and credentials intact. Do not open
credential files, reset the database, restore a backup or reimport trades.
Do not stop unrelated processes or change dependency versions to bypass
an error. Restart only the affected Libre Trading Journal process and
check both URLs again.

Report the cause, files or settings changed, app URL and checks performed.
If the problem remains, give me the error and the next action needed.
```

## Continue after installation

- [Windows installation](INSTALL-WINDOWS.md)
- [Accounts, imports and daily use](USER-GUIDE.md)
- [AI provider setup](AI-PROVIDERS.md)
- [Backup and restore](BACKUP-RESTORE.md)
- [Startup and error recovery](TROUBLESHOOTING.md)

Windows is the primary installation platform. Backend tests also run on Linux; a full macOS installation has not been tested. These prompts were checked against the setup guides but have not been used for an installation on a second physical PC.
