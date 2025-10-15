# Adding New Microservices

This guide explains how to add new microservices to the payables monorepo.

## Service Structure

Each microservice should follow this standard structure:

```
services/<service-name>/
├── <service_name>/           # Python package (underscores)
│   ├── __init__.py
│   ├── core/                 # Business logic
│   │   ├── __init__.py
│   │   └── processor.py      # Main service logic
│   ├── handlers/             # Lambda/Server handlers (if applicable)
│   │   ├── __init__.py
│   │   ├── lambda_handler.py # AWS Lambda handler
│   │   └── server_handler.py # EC2 server handler
│   ├── cli.py               # CLI interface (if applicable)
│   └── utils/               # Service-specific utilities
│       ├── __init__.py
│       └── logger.py        # Logging configuration
├── deployment/
│   ├── lambda/              # Lambda deployment files (if applicable)
│   │   ├── Dockerfile
│   │   └── template.yaml    # SAM template
│   └── systemd/             # Systemd service files (if applicable)
│       └── <service-name>.service
├── tests/
│   └── __init__.py
├── pyproject.toml           # Service dependencies
├── README.md                # Service-specific documentation
└── .env.example             # Environment variables template
```

## Naming Conventions

- **Directory names**: Use kebab-case (e.g., `invoice-extraction`, `payment-processor`)
- **Python packages**: Use snake_case (e.g., `invoice_extraction`, `payment_processor`)
- **Service names**: Use descriptive names that indicate the service's purpose

## Step-by-Step Guide

### 1. Create Service Directory Structure

```bash
# Create main service directory
mkdir -p services/<service-name>/{<service_name>,deployment/{lambda,systemd},tests}

# Create Python package structure
mkdir -p services/<service-name>/<service_name>/{core,handlers,utils}

# Create __init__.py files
touch services/<service-name>/<service_name>/__init__.py
touch services/<service-name>/<service_name>/core/__init__.py
touch services/<service-name>/<service_name>/handlers/__init__.py
touch services/<service-name>/<service_name>/utils/__init__.py
touch services/<service-name>/tests/__init__.py
```

### 2. Create Core Service Logic

Create `services/<service-name>/<service_name>/core/processor.py`:

```python
"""
Core business logic for <service-name>.
"""

import os
from typing import Dict, Any, Optional

from ..utils.logger import setup_logger


class ServiceProcessor:
    """Main service processor class."""
    
    def __init__(self, logger: Optional[Any] = None):
        """Initialize the service processor."""
        self.logger = logger or setup_logger("<service-name>")
        
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process the input data."""
        self.logger.info("Processing data...")
        # Your service logic here
        return {"status": "success"}
```

### 3. Create CLI Interface (Optional)

Create `services/<service-name>/<service_name>/cli.py`:

```python
"""
Command-line interface for <service-name>.
"""

import argparse
from .core.processor import ServiceProcessor
from .utils.logger import setup_logger


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="<Service description>")
    parser.add_argument("input", help="Input parameter")
    
    args = parser.parse_args()
    
    logger = setup_logger("<service-name>")
    processor = ServiceProcessor(logger=logger)
    
    try:
        result = processor.process({"input": args.input})
        logger.info(f"Success: {result}")
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    main()
```

### 4. Create Handlers (If Applicable)

#### Lambda Handler

Create `services/<service-name>/<service_name>/handlers/lambda_handler.py`:

```python
"""
AWS Lambda handler for <service-name>.
"""

import json
from typing import Dict, Any

from ..core.processor import ServiceProcessor
from ..utils.logger import setup_logger


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler."""
    logger = setup_logger("<service-name>", enable_file_logging=False)
    
    try:
        processor = ServiceProcessor(logger=logger)
        
        # Process each record
        for record in event.get('Records', []):
            message_body = json.loads(record['body'])
            result = processor.process(message_body)
            
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Success'})
        }
    except Exception as e:
        logger.error(f"Error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

#### Server Handler

Create `services/<service-name>/<service_name>/handlers/server_handler.py`:

```python
"""
EC2 server handler for <service-name>.
"""

import json
import signal
import sys
from typing import Dict, Any

import boto3
from ..core.processor import ServiceProcessor
from ..utils.logger import setup_logger


class SQSWorker:
    """Long-polling SQS worker."""
    
    def __init__(self):
        self.logger = setup_logger("<service-name>")
        self.sqs_client = boto3.client('sqs')
        self.queue_url = os.getenv('SQS_QUEUE_URL')
        self.running = False
        
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def run(self):
        """Main worker loop."""
        self.logger.info("Starting SQS worker...")
        self.running = True
        
        while self.running:
            try:
                response = self.sqs_client.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20
                )
                
                for message in response.get('Messages', []):
                    if not self.running:
                        break
                    
                    self._process_message(message)
                    
            except Exception as e:
                self.logger.error(f"Error: {e}")
    
    def _process_message(self, message):
        """Process a single message."""
        try:
            message_body = json.loads(message['Body'])
            processor = ServiceProcessor(logger=self.logger)
            processor.process(message_body)
            
            # Delete message on success
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=message['ReceiptHandle']
            )
        except Exception as e:
            self.logger.error(f"Failed to process message: {e}")


def run_sqs_worker():
    """Entry point for running the SQS worker."""
    try:
        worker = SQSWorker()
        worker.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_sqs_worker()
```

### 5. Create Service Configuration

Create `services/<service-name>/pyproject.toml`:

```toml
[project]
name = "<service-name>"
version = "0.1.0"
description = "<Service description>"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "boto3>=1.40.48",
    "python-dotenv>=1.1.1",
    "requests>=2.32.5",
    # Add service-specific dependencies
]

[project.scripts]
<service-command> = "<service_name>.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
    "pytest>=7.0.0",
    "black>=23.0.0",
    "isort>=5.12.0",
    "mypy>=1.0.0",
]
```

Create `services/<service-name>/.env.example`:

```bash
# Service-specific configuration
SERVICE_API_KEY=your-api-key
SERVICE_URL=https://api.example.com

# AWS Configuration (if applicable)
S3_BUCKET_NAME=your-bucket
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789/queue

# Logging
DEBUG_LOG=false
```

### 6. Create Deployment Files (If Applicable)

#### Lambda Deployment

Create `services/<service-name>/deployment/lambda/Dockerfile`:

```dockerfile
FROM public.ecr.aws/lambda/python:3.13

# Install system dependencies if needed
# RUN yum install -y package-name

# Copy application code
COPY <service_name> ${LAMBDA_TASK_ROOT}/<service_name>
COPY pyproject.toml ${LAMBDA_TASK_ROOT}/

# Install Python dependencies
RUN pip install --no-cache-dir .

# Set handler
CMD ["<service_name>.handlers.lambda_handler.handler"]
```

Create `services/<service-name>/deployment/lambda/template.yaml`:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: <Service Name> Lambda Function

Parameters:
  ServiceApiKey:
    Type: String
    Description: Service API Key
    NoEcho: true
  
  ServiceUrl:
    Type: String
    Description: Service URL
    Default: ""

Globals:
  Function:
    Timeout: 300
    MemorySize: 512
    Environment:
      Variables:
        SERVICE_API_KEY: !Ref ServiceApiKey
        SERVICE_URL: !Ref ServiceUrl
        DEBUG_LOG: "false"

Resources:
  ServiceFunction:
    Type: AWS::Serverless::Function
    Properties:
      PackageType: Image
      ImageConfig:
        Command: ["<service_name>.handlers.lambda_handler.handler"]
      Events:
        SQSEvent:
          Type: SQS
          Properties:
            Queue: !GetAtt ServiceQueue.Arn
            BatchSize: 1
      Policies:
        - SQSReceiveMessagePolicy:
            QueueName: !Ref ServiceQueue
        - Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - logs:CreateLogGroup
                - logs:CreateLogStream
                - logs:PutLogEvents
              Resource: '*'

  ServiceQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: <service-name>-queue
      VisibilityTimeoutSeconds: 360
      MessageRetentionPeriod: 1209600
      ReceiveMessageWaitTimeSeconds: 20

Outputs:
  ServiceFunction:
    Description: "Service Lambda Function ARN"
    Value: !GetAtt ServiceFunction.Arn
  
  ServiceQueueUrl:
    Description: "SQS Queue URL"
    Value: !Ref ServiceQueue
```

#### Systemd Service

Create `services/<service-name>/deployment/systemd/<service-name>.service`:

```ini
[Unit]
Description=<Service Name> Worker
After=network.target

[Service]
Type=simple
User=<service-user>
WorkingDirectory=/opt/payables/services/<service-name>
EnvironmentFile=/etc/<service-name>/.env
ExecStart=/usr/bin/python3 -m <service_name>.handlers.server_handler
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 7. Create Service Documentation

Create `services/<service-name>/README.md`:

```markdown
# <Service Name>

<Brief description of the service and its purpose.>

## Features

- Feature 1
- Feature 2
- Feature 3

## Architecture

```
[Text-based architecture diagram]
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SERVICE_API_KEY` | Yes | API key for the service |
| `SERVICE_URL` | Yes | Service endpoint URL |
| `DEBUG_LOG` | No | Enable debug logging |

## Usage

### CLI

```bash
<service-command> <input>
```

### SQS Message Format

```json
{
  "field1": "value1",
  "field2": "value2"
}
```

## Deployment

See [DEPLOYMENT.md](../../docs/DEPLOYMENT.md) for deployment instructions.

## Development

See [DEVELOPMENT.md](../../docs/DEVELOPMENT.md) for development setup.
```

### 8. Update Root Documentation

Add your service to the root `README.md`:

```markdown
## Services

### invoice-extraction
Processes PDF invoices using OpenAI GPT-4 Vision API.

### <service-name>
<Brief description of your service>
```

## Best Practices

1. **Keep services focused**: Each service should have a single, well-defined responsibility
2. **Use shared utilities**: Put common code in the `shared/` directory
3. **Follow naming conventions**: Use consistent naming across all files
4. **Write tests**: Include comprehensive tests for your service
5. **Document everything**: Provide clear documentation for users and developers
6. **Handle errors gracefully**: Implement proper error handling and logging
7. **Use environment variables**: Don't hardcode configuration values
8. **Follow security best practices**: Use proper authentication and authorization

## Shared Code

If you have code that could be reused across services, add it to the `shared/` directory:

```
shared/
├── __init__.py
├── aws/              # AWS utilities
├── database/         # Database utilities
├── auth/            # Authentication utilities
└── utils/           # General utilities
```

Then import it in your service:

```python
from shared.aws.s3_client import S3Client
from shared.utils.validators import validate_email
```

## Testing

Create tests in the `tests/` directory:

```python
# tests/test_processor.py
import pytest
from <service_name>.core.processor import ServiceProcessor


def test_process_success():
    processor = ServiceProcessor()
    result = processor.process({"input": "test"})
    assert result["status"] == "success"
```

Run tests:

```bash
cd services/<service-name>
uv run pytest
```
