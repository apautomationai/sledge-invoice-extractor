# Deployment Guide

This guide covers deploying the invoice extraction service to AWS Lambda and EC2.

## AWS Lambda Deployment

### Prerequisites

- AWS CLI configured
- SAM CLI installed
- Docker installed
- S3 bucket for deployment artifacts

### Deploy with SAM

1. **Navigate to the service directory:**
   ```bash
   cd services/invoice-extraction
   ```

2. **Build the application:**
   ```bash
   sam build
   ```

3. **Deploy with guided setup (first time):**
   ```bash
   sam deploy --guided
   ```

   Provide the following parameters:
   - Stack Name: `invoice-extraction-stack`
   - AWS Region: `us-east-1` (or your preferred region)
   - Parameter SQSQueueUrl: (leave empty, will be created)
   - Parameter OpenAIApiKey: Your OpenAI API key
   - Parameter ApiUrl: Your API endpoint URL
   - Parameter S3BucketName: Your S3 bucket name
   - Confirm changes before deploy: `Y`
   - Allow SAM CLI IAM role creation: `Y`
   - Save parameters to configuration file: `Y`
   - SAM configuration file: `samconfig.toml`

4. **Deploy updates:**
   ```bash
   sam deploy
   ```

### Lambda Configuration

The Lambda function is configured with:
- **Runtime**: Python 3.13 (Container)
- **Memory**: 2048 MB
- **Timeout**: 900 seconds (15 minutes)
- **Concurrency**: 10 reserved concurrent executions

### SQS Integration

The deployment creates:
- **Main Queue**: `invoice-extraction-queue`
- **Dead Letter Queue**: `invoice-extraction-dlq`
- **Event Source Mapping**: Automatically triggers Lambda on new messages

### Message Format

Send messages to the SQS queue in this format:
```json
{
  "attachment_id": 123
}
```

## EC2 Deployment

### Prerequisites

- EC2 instance with Ubuntu 20.04+ or Amazon Linux 2
- Python 3.13+
- AWS credentials configured
- SSH access to the instance

### Installation Steps

1. **SSH into your EC2 instance:**
   ```bash
   ssh -i your-key.pem ubuntu@your-ec2-ip
   ```

2. **Install system dependencies:**
   ```bash
   # Update system
   sudo apt update && sudo apt upgrade -y
   
   # Install Python 3.13
   sudo apt install -y software-properties-common
   sudo add-apt-repository ppa:deadsnakes/ppa
   sudo apt update
   sudo apt install -y python3.13 python3.13-venv python3.13-dev
   
   # Install poppler-utils
   sudo apt install -y poppler-utils
   
   # Install git
   sudo apt install -y git
   ```

3. **Create application user:**
   ```bash
   sudo useradd -r -s /bin/false invoice-processor
   ```

4. **Clone and setup application:**
   ```bash
   # Clone repository
   sudo git clone https://github.com/your-org/payables.git /opt/payables
   cd /opt/payables/services/invoice-extraction
   
   # Install Python dependencies
   sudo python3.13 -m pip install .
   
   # Set ownership
   sudo chown -R invoice-processor:invoice-processor /opt/payables
   ```

5. **Configure environment:**
   ```bash
   # Create environment directory
   sudo mkdir -p /etc/invoice-extraction
   
   # Create environment file
   sudo tee /etc/invoice-extraction/.env > /dev/null <<EOF
   OPENAI_API_KEY=sk-your-openai-api-key
   API_URL=https://your-api-endpoint.com
   S3_BUCKET_NAME=your-s3-bucket
   SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789/invoice-queue
   DEBUG_LOG=false
   EOF
   
   # Set permissions
   sudo chown invoice-processor:invoice-processor /etc/invoice-extraction/.env
   sudo chmod 600 /etc/invoice-extraction/.env
   ```

6. **Install and start systemd service:**
   ```bash
   # Copy service file
   sudo cp deployment/systemd/invoice-extraction.service /etc/systemd/system/
   
   # Reload systemd
   sudo systemctl daemon-reload
   
   # Enable and start service
   sudo systemctl enable invoice-extraction
   sudo systemctl start invoice-extraction
   ```

### Service Management

**Check status:**
```bash
sudo systemctl status invoice-extraction
```

**View logs:**
```bash
# Recent logs
sudo journalctl -u invoice-extraction -f

# All logs
sudo journalctl -u invoice-extraction

# Logs with timestamps
sudo journalctl -u invoice-extraction --since "1 hour ago"
```

**Control service:**
```bash
# Start
sudo systemctl start invoice-extraction

# Stop
sudo systemctl stop invoice-extraction

# Restart
sudo systemctl restart invoice-extraction

# Reload configuration
sudo systemctl reload invoice-extraction
```

### Enable Debug Logging

To enable detailed file logging:

1. **Update environment file:**
   ```bash
   sudo nano /etc/invoice-extraction/.env
   # Change DEBUG_LOG=false to DEBUG_LOG=true
   ```

2. **Restart service:**
   ```bash
   sudo systemctl restart invoice-extraction
   ```

3. **Check logs:**
   ```bash
   # File logs (when DEBUG_LOG=true)
   sudo tail -f /opt/payables/services/invoice-extraction/logs/invoice-extraction.log
   
   # Systemd logs
   sudo journalctl -u invoice-extraction -f
   ```

### Updating the Application

1. **Pull latest changes:**
   ```bash
   cd /opt/payables
   sudo git pull origin main
   ```

2. **Reinstall dependencies:**
   ```bash
   cd services/invoice-extraction
   sudo python3.13 -m pip install .
   ```

3. **Restart service:**
   ```bash
   sudo systemctl restart invoice-extraction
   ```

## Monitoring

### CloudWatch (Lambda)

- **Logs**: `/aws/lambda/invoice-extraction-function`
- **Metrics**: Duration, Errors, Invocations, Throttles
- **Alarms**: Set up alarms for errors and duration

### Systemd Journal (EC2)

- **Logs**: `journalctl -u invoice-extraction`
- **Log rotation**: Managed by systemd
- **Monitoring**: Use tools like `htop`, `iotop` for resource monitoring

## Troubleshooting

### Lambda Issues

1. **Function timeout:**
   - Increase timeout in SAM template
   - Check PDF processing time
   - Optimize image conversion settings

2. **Memory errors:**
   - Increase memory allocation
   - Check for memory leaks
   - Optimize image processing

3. **Permission errors:**
   - Verify IAM role permissions
   - Check S3 bucket policies
   - Ensure SQS queue permissions

### EC2 Issues

1. **Service won't start:**
   ```bash
   # Check service status
   sudo systemctl status invoice-extraction
   
   # Check logs
   sudo journalctl -u invoice-extraction
   ```

2. **Permission errors:**
   ```bash
   # Fix ownership
   sudo chown -R invoice-processor:invoice-processor /opt/payables
   ```

3. **Python import errors:**
   ```bash
   # Reinstall dependencies
   cd /opt/payables/services/invoice-extraction
   sudo python3.13 -m pip install .
   ```

4. **PDF processing errors:**
   ```bash
   # Verify poppler installation
   pdftoppm -h
   
   # Reinstall if needed
   sudo apt install --reinstall poppler-utils
   ```
