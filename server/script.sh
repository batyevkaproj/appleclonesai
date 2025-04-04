#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
APP_NAME="mysecureapp"
APP_USER="mysecureappuser" # User to run the application
APP_GROUP="mysecureappgroup" # Group for the user
APP_DIR="/opt/${APP_NAME}"
VENV_DIR="${APP_DIR}/venv"
BACKEND_FILE="backend.py"
SERVICE_NAME="${APP_NAME}.service"
NGINX_CONF_NAME="${APP_NAME}"
# Change if your backend runs on a different port
GUNICORN_BIND_ADDRESS="127.0.0.1:8000"

# --- Check if running as root ---
if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root. Use sudo." >&2
  exit 1
fi

echo "--- Starting Deployment for ${APP_NAME} on Debian 12 ---"

# --- 1. System Update & Dependencies ---
echo "Updating package lists..."
apt update

echo "Installing required packages (Python3, pip, venv, Nginx, curl)..."
apt install -y python3 python3-pip python3-venv nginx curl

# --- 2. Create Application User and Directory ---
echo "Creating application group '${APP_GROUP}' (if it doesn't exist)..."
if ! getent group ${APP_GROUP} > /dev/null; then
    groupadd ${APP_GROUP}
else
    echo "Group '${APP_GROUP}' already exists."
fi

echo "Creating application user '${APP_USER}' (if it doesn't exist)..."
if ! id -u ${APP_USER} > /dev/null 2>&1; then
    # Create user, no password login, assign to group, create home dir implicitly
    useradd -r -g ${APP_GROUP} -s /usr/sbin/nologin ${APP_USER}
else
    echo "User '${APP_USER}' already exists."
fi

echo "Creating application directory '${APP_DIR}'..."
mkdir -p ${APP_DIR}

# Assume backend.py is in the same directory as deploy.sh
echo "Copying backend code (${BACKEND_FILE}) to ${APP_DIR}..."
if [ -f "${BACKEND_FILE}" ]; then
    cp "${BACKEND_FILE}" "${APP_DIR}/"
else
    echo "Error: ${BACKEND_FILE} not found in the current directory." >&2
    exit 1
fi

# --- 3. Create Python Virtual Environment & Install Dependencies ---
echo "Creating Python virtual environment at ${VENV_DIR}..."
python3 -m venv ${VENV_DIR}

echo "Activating virtual environment and installing dependencies..."
# Create requirements.txt
cat << EOF > ${APP_DIR}/requirements.txt
fastapi>=0.70.0
uvicorn[standard]>=0.15.0
gunicorn>=20.1.0
python-multipart>=0.0.5 # Often needed by FastAPI for form data, good practice to include
# itsdangerous # If you were using signed tokens instead of random
EOF

# Install using pip from the venv
${VENV_DIR}/bin/pip install --no-cache-dir -r ${APP_DIR}/requirements.txt

# --- 4. Set Permissions ---
echo "Setting ownership for ${APP_DIR} to ${APP_USER}:${APP_GROUP}..."
chown -R ${APP_USER}:${APP_GROUP} ${APP_DIR}
chmod -R 750 ${APP_DIR} # Read/execute for owner/group

# --- 5. Create Systemd Service File ---
echo "Creating systemd service file at /etc/systemd/system/${SERVICE_NAME}..."
cat << EOF > /etc/systemd/system/${SERVICE_NAME}
[Unit]
Description=Gunicorn instance to serve ${APP_NAME}
After=network.target

[Service]
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${APP_DIR}
Environment="PATH=${VENV_DIR}/bin"
# Command to start Gunicorn with Uvicorn workers
ExecStart=${VENV_DIR}/bin/gunicorn --workers 3 --worker-class uvicorn.workers.UvicornWorker --bind ${GUNICORN_BIND_ADDRESS} main:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
# NOTE: main:app assumes your FastAPI instance in backend.py is named 'app'
# Adjust --workers based on your server's CPU cores (e.g., 2 * cores + 1)

# --- 6. Enable and Start the Service ---
echo "Reloading systemd daemon, enabling and starting ${SERVICE_NAME}..."
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl start ${SERVICE_NAME}
systemctl status ${SERVICE_NAME} --no-pager # Display status

# --- 7. Configure Nginx as Reverse Proxy ---
echo "Configuring Nginx reverse proxy..."

# Disable default site if it exists and is enabled
if [ -L /etc/nginx/sites-enabled/default ]; then
    echo "Disabling default Nginx site..."
    rm /etc/nginx/sites-enabled/default
fi

# Create Nginx site configuration
cat << EOF > /etc/nginx/sites-available/${NGINX_CONF_NAME}
server {
    listen 80;
    listen [::]:80;

    # Replace _ with your actual domain name if you have one
    server_name _;

    # Increase max body size if needed (e.g., for file uploads)
    # client_max_body_size 10M;

    location / {
        # Forward requests to the Gunicorn server
        proxy_pass http://${GUNICORN_BIND_ADDRESS};

        # Set important proxy headers
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Optional: Improve proxy buffering/timeouts if needed
        # proxy_buffering off;
        # proxy_read_timeout 300s;
        # proxy_connect_timeout 75s;
    }

    # Optional: Serve static files directly via Nginx for better performance
    # location /static {
    #     alias ${APP_DIR}/static; # Assuming you have a static folder
    #     expires 30d;
    #     add_header Cache-Control "public";
    # }
}
EOF

# Enable the new site configuration
if [ ! -L /etc/nginx/sites-enabled/${NGINX_CONF_NAME} ]; then
    echo "Enabling Nginx site configuration for ${NGINX_CONF_NAME}..."
    ln -s /etc/nginx/sites-available/${NGINX_CONF_NAME} /etc/nginx/sites-enabled/
else
    echo "Nginx site ${NGINX_CONF_NAME} already enabled."
fi

# Test Nginx configuration
echo "Testing Nginx configuration..."
nginx -t

# Restart Nginx to apply changes
echo "Restarting Nginx..."
systemctl restart nginx

# --- 8. Firewall Configuration (Example using UFW) ---
echo "Configuring firewall (UFW)..."
if command -v ufw &> /dev/null; then
    ufw allow 'Nginx Full' # Allows both HTTP (80) and HTTPS (443)
    ufw enable # Ensure UFW is enabled (will prompt for confirmation)
    ufw status
else
    echo "UFW (Uncomplicated Firewall) not found. Please configure your firewall manually."
    echo "You need to allow traffic on port 80 (HTTP) and 443 (HTTPS)."
fi

# --- 9. Completion Message ---
echo ""
echo "--- Deployment Setup Complete ---"
echo "Your FastAPI application (${APP_NAME}) should be running."
echo " - Service: ${SERVICE_NAME} (use systemctl status ${SERVICE_NAME})"
echo " - Served by Gunicorn/Uvicorn at: ${GUNICORN_BIND_ADDRESS}"
echo " - Accessible via Nginx reverse proxy on port 80 (HTTP)."
echo ""
echo "--- IMPORTANT NEXT STEPS ---"
echo "1.  **TESTING:** Access your server's IP address in a browser. You should see the FastAPI root message or your frontend if served."
echo "2.  **HTTPS:** The current setup uses HTTP. For production, set up HTTPS using Let's Encrypt (Certbot):"
echo "   sudo apt install certbot python3-certbot-nginx"
echo "   sudo certbot --nginx -d your_domain.com # Replace with your domain"
echo "   (Follow Certbot prompts. It will automatically update the Nginx config)"
echo "3.  **FRONTEND:** Place your updated index.html file where Nginx can serve it (e.g., /var/www/html or configure Nginx to serve it from ${APP_DIR}/static if you prefer)."
echo "   Update API_BASE_URL in index.html to 'https://your_domain.com' after setting up HTTPS."
echo "4.  **DATABASE:** Replace the in-memory session store and mock user DB in backend.py with a persistent database (e.g., PostgreSQL, MySQL) or Redis."
echo "5.  **PASSWORD HASHING:** Implement proper password hashing (e.g., using passlib) in backend.py instead of plain text comparison."
echo "6.  **SECRETS MANAGEMENT:** Do not hardcode sensitive information. Use environment variables or a proper secrets management tool."
echo "7.  **MONITORING & LOGGING:** Set up monitoring and centralized logging for your application and server."
echo "------------------------------"