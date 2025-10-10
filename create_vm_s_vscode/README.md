# VSCode Server Provisioning Script Overview

This document outlines the steps performed by the VSCode Server provisioning script.

- Set strict bash options (`set -euo pipefail`)
- Define webhook function for notifications or a no-op if URL not provided
- Redirect all output to `/var/log/code-server-install.log`
- Set environment variables (domain, admin email/password, ports, directories, location, resource group, webhook URL)
- Validate domain format and port number; exit on invalid input
- Check for port conflicts and attempt to free the port if in use
- Update system packages and install base dependencies (`curl`, `wget`, `gnupg2`, `lsb-release`, `ca-certificates`, `apt-transport-https`, `nginx`, `certbot`, `python3-certbot-nginx`, `ufw`, `git`, `build-essential`, `sudo`, `cron`, `python3`, `python3-pip`, `jq`, `software-properties-common`)
- Create service user (`coder`) if missing with proper sudo permissions
- Install Node.js LTS (20.x) and update npm
- Install global npm tools (`yarn`, `netlify-cli`)
- Install Pyenv and Python 3.9.7 for root and service user
- Install optional Electron dependencies (GTK, libnotify, libnss, libasound2, etc.)
- Install Docker engine, add service user to Docker group, and verify daemon
- Install `kubectl` and `Terraform`
- Install and configure code-server
  - Detect code-server binary or fallback paths
  - Setup config directories and permissions
  - Write `config.yaml` with authentication
  - Create systemd service and start code-server
  - Wait for code-server readiness
- Install VSCode extensions (list defined in script) with retries and marketplace fallback
- Ensure `code` CLI symlink exists
- Configure UFW firewall to allow SSH, HTTP, HTTPS, and code-server port
- Remove default nginx configuration and create temporary HTTP server for Certbot validation
- Download Let’s Encrypt recommended SSL configs (`options-ssl-nginx.conf`, `ssl-dhparams.pem`)
- Obtain SSL certificate using Certbot; fallback to webroot if needed
- Update nginx configuration for HTTPS reverse proxy to code-server
- Test nginx configuration and reload if successful
- Setup cron job for daily SSL certificate renewal and nginx reload
- Perform final verification of code-server service and HTTPS access
- Display summary with access URL, admin password, service user, and useful commands
- Send webhook notifications for all major steps, warnings, and errors
