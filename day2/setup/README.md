# Day 2 Environment Setup

This guide walks you through installing Docker, Portainer, and N8N locally for the Day 2 of MCP and A2A workshop.

**Prerequisites:**
- Mac: Homebrew installed (`/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`)
- Linux: sudo access and curl installed
- At least 4GB of free RAM for containers

---

## Table of Contents

1. [Install Docker](#1-install-docker)
2. [Verify Docker Installation](#2-verify-docker-installation)
3. [Install Portainer](#3-install-portainer)
4. [Install N8N](#4-install-n8n)
5. [Verify All Services](#5-verify-all-services)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Install Docker

### Mac (Homebrew)

```bash
# Install Docker Desktop
brew install --cask docker

# Launch Docker Desktop (required on Mac)
open -a Docker
```

Docker Desktop will start in the menu bar. Wait for it to show "Docker Desktop is running" before proceeding.

**Note:** On first launch, Docker Desktop may request permissions for networking and file sharing. Grant these permissions.

### Linux (Ubuntu/Debian)

```bash
# Update package index
sudo apt-get update

# Install prerequisites
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up the repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add your user to the docker group (so you don't need sudo)
sudo usermod -aG docker $USER

# Apply group changes (or log out and back in)
newgrp docker
```

### Linux (RHEL/CentOS/Fedora)

```bash
# Install prerequisites
sudo dnf install -y dnf-plugins-core

# Add Docker repository
sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo

# Install Docker Engine
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to the docker group
sudo usermod -aG docker $USER
newgrp docker
```

---

## 2. Verify Docker Installation

Run these commands to confirm Docker is working:

```bash
# Check Docker version
docker --version

# Expected output: Docker version 24.x.x or higher

# Check Docker is running
docker ps

# Expected output: Empty table with headers (CONTAINER ID, IMAGE, etc.)

# Test with hello-world
docker run hello-world

# Expected output: "Hello from Docker!" message
```

If `docker ps` returns an error about connecting to the daemon:
- **Mac:** Make sure Docker Desktop is running (check menu bar)
- **Linux:** Run `sudo systemctl start docker`

---

## 3. Install Portainer

Portainer provides a web UI for managing Docker containers, images, and volumes.

### Create Portainer Volume

```bash
docker volume create portainer_data
```

### Run Portainer Container

```bash
docker run -d \
  --name portainer \
  --restart=always \
  -p 9000:9000 \
  -p 9443:9443 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce:latest
```

### Access Portainer

1. Open your browser to: **https://localhost:9443**
   - You will see a certificate warning — this is expected for local self-signed certs
   - Click "Advanced" → "Proceed to localhost"
   - Alternative: Use **http://localhost:9000** (non-HTTPS)

2. Create your admin account:
   - Username: `admin` (or your preference)
   - Password: Choose a strong password (minimum 12 characters)

3. Select environment:
   - Click **"Get Started"**
   - Click **"local"** to manage your local Docker environment

You should now see the Portainer dashboard with your Docker environment.

---

## 4. Install N8N

N8N is a workflow automation tool we'll use to orchestrate our A2A agents.

### Run N8N Container

```bash
docker run -d \
  --name n8n \
  --restart=always \
  -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  -e GENERIC_TIMEZONE="America/Chicago" \
  -e TZ="America/Chicago" \
  n8nio/n8n
```

**Note:** Adjust the timezone to your location. Common options:
- `America/New_York`
- `America/Los_Angeles`
- `Europe/London`
- `Asia/Tokyo`

### Access N8N

1. Open your browser to: **http://localhost:5678**

2. Create your local account:
   - Enter your email address
   - Choose a password
   - Complete the setup wizard

3. You should see the N8N workflow editor

**Important:** This is a local N8N instance, completely separate from any cloud N8N account you may have. Workflows and credentials are stored locally in the `n8n_data` Docker volume.

---

## 5. Verify All Services

### Check All Containers Are Running

```bash
docker ps
```

Expected output (should show 2 containers):

```
CONTAINER ID   IMAGE                           STATUS          PORTS                                            NAMES
xxxxxxxxxxxx   n8nio/n8n                       Up X minutes    0.0.0.0:5678->5678/tcp                           n8n
xxxxxxxxxxxx   portainer/portainer-ce:latest   Up X minutes    0.0.0.0:9000->9000/tcp, 0.0.0.0:9443->9443/tcp   portainer
```

### Service URLs

| Service   | URL                        | Purpose                          |
|-----------|----------------------------|----------------------------------|
| Portainer | https://localhost:9443     | Docker container management UI   |
| Portainer | http://localhost:9000      | Docker management (non-HTTPS)    |
| N8N       | http://localhost:5678      | Workflow automation platform     |

### Quick Health Check

```bash
# Check Portainer is responding
curl -k https://localhost:9443/api/status

# Check N8N is responding
curl http://localhost:5678/healthz
```

---

## 6. Troubleshooting

### Docker Desktop Not Starting (Mac)

```bash
# Reset Docker Desktop
rm -rf ~/Library/Group\ Containers/group.com.docker
rm -rf ~/Library/Containers/com.docker.docker
rm -rf ~/.docker

# Reinstall
brew uninstall --cask docker
brew install --cask docker
```

### Permission Denied on Docker Socket (Linux)

```bash
# Check docker group exists
getent group docker

# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker
```

### Port Already in Use

```bash
# Find what's using the port (example: 5678)
lsof -i :5678

# Kill the process if needed
kill -9 <PID>

# Or choose a different port when running the container
docker run -d --name n8n -p 5679:5678 ...
```

### Container Won't Start

```bash
# Check container logs
docker logs n8n
docker logs portainer

# Remove and recreate if needed
docker rm -f n8n
docker run -d --name n8n ...
```

### Reset Everything and Start Fresh

```bash
# Stop and remove all containers
docker rm -f n8n portainer

# Remove volumes (WARNING: deletes all data)
docker volume rm n8n_data portainer_data

# Start over from Step 3
```

---

## Managing Containers

### Start/Stop Commands

```bash
# Stop containers
docker stop n8n portainer

# Start containers
docker start n8n portainer

# Restart containers
docker restart n8n portainer
```

### View Logs

```bash
# View N8N logs
docker logs n8n

# Follow logs in real-time
docker logs -f n8n

# View last 100 lines
docker logs --tail 100 n8n
```

### Using Portainer

Once logged into Portainer, you can:
- Start/stop containers with one click
- View container logs in the browser
- Inspect container details and resource usage
- Manage Docker volumes and networks

---

## Next Steps

With Docker, Portainer, and N8N running, you're ready to:

1. Review Day 1 and Introduction to A2A (Session 1)
2. Build A2A agents with existing MCP servers (Session 2)
3. Orchestrate agents with N8N workflows (Session 3)

Your A2A agents will run on localhost ports:
- **Production Agent (A2A):** http://localhost:8001
- **MES HTTP Server (N8N):** http://localhost:8002

Use the startup script from the project root:
```bash
cd /path/to/MCP_A2A_Workshop
./start_servers.sh
```

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `docker ps` | List running containers |
| `docker ps -a` | List all containers (including stopped) |
| `docker logs <name>` | View container logs |
| `docker stop <name>` | Stop a container |
| `docker start <name>` | Start a container |
| `docker restart <name>` | Restart a container |
| `docker rm -f <name>` | Force remove a container |
| `docker volume ls` | List Docker volumes |
| `docker system prune` | Clean up unused resources |
