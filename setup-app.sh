#!/bin/bash
# Setup script for Python Agentic AI Application on EC2
# Usage: ./setup-app.sh <github-repo-url>
set -e

GITHUB_REPO_URL=${1:-"https://github.com/sunkavar/agentic-ai-sample-python-app-cloudwatch-monitoring.git"}
APP_DIR="/home/ec2-user/agentic-ai-app"
LOG_FILE="/var/log/app-setup.log"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a $LOG_FILE
}

# Get AWS region and instance ID using IMDSv2
log "Getting metadata using IMDSv2..."

# Get IMDSv2 token
TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" -s)

# Get AWS Region
AWS_REGION=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" \
    -s http://169.254.169.254/latest/meta-data/placement/region)

# Get Instance ID
INSTANCE_ID=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" \
    -s http://169.254.169.254/latest/meta-data/instance-id)

log "AWS Region: $AWS_REGION, Instance ID: $INSTANCE_ID"

log "Starting application setup..."

# Update system
log "Updating system packages..."
sudo yum update -y

# Install git and other essential tools
log "Installing git and essential tools..."
sudo yum install git -y

# Install CloudWatch Agent
log "Installing CloudWatch Agent..."
wget https://s3.amazonaws.com/amazoncloudwatch-agent/amazon_linux/amd64/latest/amazon-cloudwatch-agent.rpm
sudo rpm -U ./amazon-cloudwatch-agent.rpm

# Upgrade python to 3.12
log "Installing Python 3.12..."
sudo yum install python3.12 -y

# Create symbolic links
log "Creating symbolic links for Python 3.12..."
sudo ln -sf /usr/bin/python3.12 /usr/bin/python

# Install pip for Python 3.12
log "Installing pip for Python 3.12..."
curl -O https://bootstrap.pypa.io/get-pip.py
python3.12 get-pip.py

# Create symbolic link for pip
sudo ln -sf /usr/bin/pip3.12 /usr/bin/pip

# Verify installations
log "Python version: $(python --version)"
log "Pip version: $(pip --version)"

# Clone the application repository
log "Cloning application repository..."
cd /home/ec2-user
if [ -d "$APP_DIR" ]; then
    rm -rf "$APP_DIR"
fi
git clone "$GITHUB_REPO_URL" "$APP_DIR"
cd "$APP_DIR"

# Verify required files exist
log "Verifying application files..."
if [ ! -f "app.py" ]; then
    log "ERROR: app.py not found in repository"
    exit 1
fi

if [ ! -f "metrics_utils.py" ]; then
    log "ERROR: metrics_utils.py not found in repository"
    exit 1
fi

if [ ! -f "CW-AgentConfig.json" ]; then
    log "ERROR: CW-AgentConfig.json not found in repository"
    exit 1
fi

log "All required application files found"

# Install required packages based on the application imports
log "Installing strands and related packages..."
pip install strands-agents
pip install strands-agents-tools

log "Installing OpenTelemetry packages..."
pip install opentelemetry-api
pip install opentelemetry-sdk
pip install opentelemetry-exporter-otlp-proto-grpc
pip install opentelemetry-instrumentation
pip install aws-opentelemetry-distro

log "Installing additional AWS and utility packages..."
pip install boto3
pip install requests

# Set up CloudWatch Agent configuration
log "Setting up CloudWatch Agent..."
sudo mkdir -p /opt/aws/amazon-cloudwatch-agent/etc/

# Copy the CloudWatch Agent configuration
sudo cp CW-AgentConfig.json /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

# Update the log stream name with actual instance ID
log "Updating CloudWatch Agent configuration with instance ID: $INSTANCE_ID"
sudo sed -i "s/i-06ba0de6XXXXXX/$INSTANCE_ID/g" /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

log "CloudWatch Agent configuration updated with instance ID: $INSTANCE_ID and region: $AWS_REGION"

# Start CloudWatch Agent
log "Starting CloudWatch Agent..."
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

# Verify CloudWatch Agent is running
if sudo systemctl is-active --quiet amazon-cloudwatch-agent; then
    log "CloudWatch Agent is running"
else
    log "Warning: CloudWatch Agent failed to start"
fi

# Set proper permissions for all application files
sudo chown -R ec2-user:ec2-user "$APP_DIR"
chmod +x "$APP_DIR/app.py"
chmod +r "$APP_DIR/metrics_utils.py"
chmod +r "$APP_DIR/CW-AgentConfig.json"

# Create manual startup script
log "Creating manual startup script..."
tee "$APP_DIR/start-app.sh" > /dev/null <<EOF
#!/bin/bash
cd $APP_DIR

# Set environment variables for Application Signals with CloudWatch Agent
export OTEL_METRICS_EXPORTER=none
export OTEL_PYTHON_LOG_CORRELATION=true
export OTEL_LOGS_EXPORTER=none
export OTEL_AWS_APPLICATION_SIGNALS_ENABLED=true
export OTEL_PYTHON_DISTRO=aws_distro
export OTEL_PYTHON_CONFIGURATOR=aws_configurator
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_AWS_APPLICATION_SIGNALS_EXPORTER_ENDPOINT=http://localhost:4316/v1/metrics
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4316/v1/traces
export OTEL_RESOURCE_ATTRIBUTES="aws.log.group.names=strands-agent-logs,service.name=strands-agent,deployment.environment=ec2:default"

# Start the application
opentelemetry-instrument python app.py
EOF

chmod +x "$APP_DIR/start-app.sh"



log "Setup completed! Application code copied and CloudWatch Agent configured."
log "Application Signals traces and metrics will be collected by CloudWatch Agent"
log "Use the following commands to manage the application:"
log "  - Start application manually: cd $APP_DIR && ./start-app.sh"
log "  - View CloudWatch Agent logs: sudo journalctl -u amazon-cloudwatch-agent -f"

echo "Setup completed successfully! Check $LOG_FILE for detailed logs."
echo "To run the application manually, use: cd $APP_DIR && ./start-app.sh"
echo "Application Signals data will be available in CloudWatch console under Application Signals section."
