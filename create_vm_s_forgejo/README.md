# Forgejo Provisioning Script Overview

This document outlines the steps performed by the Forgejo provisioning script.

- Set strict bash options (`set -euo pipefail`)
- Define webhook function for notifications or a no-op if URL not provided
- Redirect all output to `/var/log/forgejo_setup.log`
- Set environment variables (domain, admin email/password, ports, directories, DNS hook, upload size, etc.)
- Generate LFS JWT secret
- Validate domain format and port number; exit on invalid input
- Install system dependencies (curl, git, nginx, certbot, python3-pip, python3-venv, jq, make, net-tools, python3-certbot-nginx, openssl, ufw)
- Install and initialize Git LFS (system-level, fallback to user-level if needed)
- Install Docker engine and plugins with retries, set up GPG key and repository
- Enable and start Docker, verify daemon is running
- Create Forgejo directories (`data`, `config`, `ssl`, `data/gitea/lfs`) with proper ownership and permissions
- Create Docker Compose configuration for Forgejo server
- Start Forgejo container using Docker Compose
- Wait for container readiness with health check and HTTP probe fallback
- Configure UFW firewall to allow SSH, HTTP, HTTPS, and Forgejo custom port
- Remove default nginx configuration and create temporary HTTP server for Certbot validation
- Download Let’s Encrypt recommended SSL configs (`options-ssl-nginx.conf`, `ssl-dhparams.pem`)
- Attempt SSL certificate issuance with Certbot; fallback to webroot if needed
- Update nginx configuration for HTTPS reverse proxy to Forgejo backend
- Test nginx configuration and reload if successful
- Setup cron job for daily SSL certificate renewal and nginx reload
- Perform final verification of Forgejo container health and HTTPS access
- Check Git LFS installation, initialization, and max file size environment variable inside container
- Wait 50 seconds to ensure all services are fully ready
- Display summary with access URL, admin email, default password, and useful Docker commands
- Send webhook notifications for all major steps, warnings, and errors
