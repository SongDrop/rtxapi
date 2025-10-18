# Bytestash Provisioning Script Overview

This document outlines the steps performed by the Bytestash provisioning script.

- Set strict bash options (`set -euo pipefail`)
- Define webhook function for notifications or a no-op if URL not provided
- Redirect all output to `/var/log/bytestash_setup.log`
- Set environment variables (domain, admin email/password, port, directories, DNS hook, upload size, etc.)
- Generate a 64-byte JWT secret for Bytestash
- Validate domain format and port number; exit on invalid input
- Install system dependencies (curl, git, nginx, certbot, python3-pip, python3-venv, jq, make, net-tools, ufw, xxd, software-properties-common)
- Install Docker engine and Docker Compose (with retries and fallback to pip installation)
- Enable and start Docker, verify daemon is running
- Create Bytestash directories (`/opt/bytestash` and `data`) with proper ownership and permissions
- Create Docker Compose configuration for Bytestash server
- Pull and start Bytestash container using Docker Compose
- Wait for container readiness with health check and HTTP probe fallback
- Configure UFW firewall to allow SSH, HTTP, HTTPS, and Bytestash custom port
- Remove default nginx configuration and create temporary HTTP server for Certbot validation
- Download Let’s Encrypt recommended SSL configs (`options-ssl-nginx.conf`, `ssl-dhparams.pem`)
- Attempt SSL certificate issuance with Certbot; fallback to webroot if needed
- Update nginx configuration for HTTPS reverse proxy to Bytestash backend
- Test nginx configuration and reload if successful
- Setup cron job for daily SSL certificate renewal and nginx reload
- Perform final verification of Bytestash container health and HTTPS access
- Wait for container readiness and proper port binding
- Display summary with access URL, admin email, JWT secret, and useful Docker commands
- Send webhook notifications for all major steps, warnings, and errors
