# Security Policy

## Supported Versions

Libre Trading Journal is based on Trading-Journal-AI. This source preview is intended for local, single-user operation on loopback, with optional external AI and price providers. It is not an authenticated shared web service.

Security fixes are generally applied to the latest released version and the current `main` branch.

| Version               | Supported |
| --------------------- | --------- |
| Latest release        | ✅         |
| Current `main` branch | ✅         |
| Older releases        | ❌         |

## Reporting a Vulnerability

If you discover a security vulnerability in Libre Trading Journal, please **do not open a public GitHub issue**.

Use [GitHub's private vulnerability reporting](https://github.com/npcagomoc-del/libre-trading-journal/security/advisories/new), enabled for this repository. If a fork has no private reporting option, obtain a private maintainer contact before sending reproduction details or secrets. Do not route Libre-specific reports to the upstream project's maintainers.

Please include, when possible:

* A description of the vulnerability
* Steps to reproduce the issue
* The potential impact
* Any affected files or components
* Suggested fixes, if you have any

Please avoid publicly disclosing the vulnerability until it has been reviewed and, when necessary, a fix has been released.

## Security-Sensitive Areas

Libre Trading Journal works with potentially sensitive information including:

* Broker trade exports
* Trading history and performance data
* Locally stored journal data
* API keys for optional external services
* Uploaded diary files and images

Reports involving exposure of this information, unauthorized access, credential handling, unexpected network communication, or unsafe file handling are particularly important.

## Data and Credentials

Libre Trading Journal is designed as a local-first application. AI provider keys and ChatGPT/MT5 credentials are installation-specific and excluded from journal backup ZIPs. On Windows those credential stores use DPAPI; AI API/ChatGPT stores on other platforms use restricted file permissions without encryption. Optional Alpaca keys are stored in the local plaintext `backend/.env`, which is also excluded from backups and source control. Keep all keys, runtime data and backups private.

Users should never commit API keys, `.env` files, local databases, broker exports, or other private trading data to the repository.

API credentials should only be stored using the configuration methods documented by the project.

## Responsible Disclosure

Please allow reasonable time to investigate and address a reported vulnerability before publicly discussing it.

Security researchers who responsibly report valid vulnerabilities are appreciated and may be credited in the corresponding release notes or security advisory if they wish.
