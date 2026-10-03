# Let an AI assistant install Libre

Use an AI coding assistant with permission to run terminal commands and edit local files **on the PC where you want the app installed**. Paste the prompt below into that assistant. A chat-only assistant can explain the steps, but cannot install software on your PC. If the assistant runs on another computer, that computer's `localhost` is not yours.

If you already downloaded Libre, open its extracted folder in your coding assistant first. Otherwise, the prompt asks it to download the public repository. Windows is the primary installation path; Linux backend CI passes, while a full macOS installation remains untested. Optional AI coaching is configured separately after the journal opens.

## Copy this installation prompt

```text
Install and run Libre Trading Journal on this computer.
Source: https://github.com/npcagomoc-del/libre-trading-journal

Complete the installation using your local terminal/file tools. Do not stop
at giving me a plan. If you cannot access this computer's terminal/files,
say so clearly and give me the manual installation steps instead.

1. Detect my operating system and whether this folder is already a Libre
   checkout. Reuse a matching checkout without discarding local changes.
   Otherwise clone or download/extract the source into a new, user-writable
   folder outside cloud-sync folders. Use the public ZIP if Git is absent.
   Do not overwrite an existing folder or modify an unrelated repository.

2. Read AGENTS.md, docs/PROJECT-STATUS.md, docs/INSTALL-WINDOWS.md,
   docs/DEVELOPER-GUIDE.md and docs/TROUBLESHOOTING.md before setup.
   Verify the app root contains backend/, frontend/ and setup.bat.

3. Check Python 3.11+ and Node.js 24 with npm. Python 3.12 was tested on
   Windows. Install missing prerequisites from official sources using the
   available package manager or official installers. Preserve existing
   installations. If an installer needs my click or administrator approval,
   tell me exactly what action is needed, then continue once it is done.
   Do not disable security protections to work around an installation error.

4. Follow the documented commands for my operating system: create/reuse
   the app's .venv, install backend requirements with that interpreter,
   and run npm ci from frontend/. On Windows use npm.cmd if PowerShell
   blocks npm.ps1. Create backend/.env from .env.example only if missing;
   do not read or overwrite an existing .env or credential store.
   Prefer the manual commands if setup.bat's pause needs interaction.
   Resolve PATH, permission or dependency errors before proceeding.
   Do not rewrite app code or change dependency versions just to hide an error.

5. Preserve all existing journal data and uploads. If this is an existing
   journal, read docs/DATA-GUIDE.md and take a consistent backup before
   startup that could migrate it. Never delete/reset a database, seed demo
   trades, restore a backup, or import broker records as an installation test.
   Do not ask me to paste API keys, passwords or tokens into this chat.

6. Check whether Libre is already running before starting another copy.
   Run one backend from backend/ on 127.0.0.1:8010 and the frontend from
   frontend/ on localhost:3010, setting HOST=127.0.0.1 and PORT=3010 in
   the appropriate shell environment to bind the frontend to loopback.
   Keep both processes
   running in sessions that survive your tool call. Do not terminate an
   unrelated process when a port is occupied; investigate and report it.
   Keep these ports for the existing ChatGPT callback.

7. Confirm http://127.0.0.1:8010/ returns {"status":"ok"} and the frontend
   responds at http://localhost:3010. If browser tools are available, open
   the journal and check that the page renders without a connection error.
   Report exactly which checks passed; do not claim a browser check if you
   only made an HTTP request. If startup fails, inspect the first relevant
   error and follow the troubleshooting guide before retrying.

Finish with the installation folder, app URL, verified checks, how to stop
and restart it, and any remaining blocker. Explain that a new install starts
empty. Show where to create a journal account and where Settings holds the
optional AI provider and backup controls. Leave AI sign-in/API entry to me
in the app; do not make paid inference requests or claim AI is verified.
```

The installer may still need a human action for operating-system permissions. An assistant also needs a way to keep the two app processes running; if its terminal sessions end when the task finishes, use `launch.bat` afterward on Windows. Successful setup does not mean ChatGPT/API credentials or MT5 are connected.

## Copy this prompt if the app will not open

Use this in the assistant that has access to the existing app folder:

```text
Diagnose why Libre Trading Journal will not open on this computer.
Read AGENTS.md, docs/PROJECT-STATUS.md and docs/TROUBLESHOOTING.md first.

Check the actual app folder, Python/Node/npm paths, existing server processes,
ports 8010/3010, backend health and frontend response. Inspect the first
relevant startup or browser connection error. Use the correct .venv and
working directories. Preserve all journal records, uploads, .env files and
credentials. Do not reset/recreate the database, restore backups, kill
unrelated processes, change dependency versions, or reimport trades to fix
startup. Do not expose secrets in logs or chat.

Apply the smallest setup/runtime fix supported by the error, restart only
the affected Libre process if needed, and verify the result. Report the
cause, what changed, the app URL and what remains unresolved. If a human
action is required, tell me the exact action rather than claiming success.
```

## Continue after installation

- [Windows manual installation](INSTALL-WINDOWS.md)
- [User tutorial: accounts, imports and daily use](USER-GUIDE.md)
- [AI provider setup](AI-PROVIDERS.md)
- [Backup and restore](BACKUP-RESTORE.md)
- [Startup and error recovery](TROUBLESHOOTING.md)

These prompts follow the documented setup and preserve existing data. They have been reviewed against the repository instructions; execution by every AI assistant and installation on a second physical PC have not been tested.
