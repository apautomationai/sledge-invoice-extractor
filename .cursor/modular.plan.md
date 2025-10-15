# Modularize Invoice Processor - Microservices Monorepo

## Project Structure (Monorepo for Multiple Microservices)

```
payables/
├── services/
│   └── invoice-extraction/
│       ├── invoice_extraction/
│       │   ├── __init__.py
│       │   ├── core/
│       │   │   ├── __init__.py
│       │   │   └── processor.py          # InvoiceSplitter class
│       │   ├── handlers/
│       │   │   ├── __init__.py
│       │   │   ├── lambda_handler.py     # AWS Lambda SQS handler
│       │   │   └── server_handler.py     # EC2 long-polling SQS handler
│       │   ├── cli.py                     # CLI interface
│       │   └── utils/
│       │       ├── __init__.py
│       │       └── logger.py              # Logging configuration
│       ├── deployment/
│       │   ├── lambda/
│       │   │   ├── Dockerfile
│       │   │   └── template.yaml          # SAM template
│       │   └── systemd/
│       │       └── invoice-extraction.service
│       ├── tests/
│       │   └── __init__.py
│       ├── pyproject.toml
│       ├── README.md
│       └── .env.example
├── shared/                                 # Shared libraries across services
│   └── __init__.py
├── docs/
│   ├── DEVELOPMENT.md                      # Local dev setup guide
│   ├── DEPLOYMENT.md                       # Deployment guides (Lambda, EC2)
│   └── ADDING_SERVICES.md                  # Guide for adding new microservices
└── README.md                               # Monorepo overview
```

## Implementation Steps

### 1. Create Monorepo Structure

- Create `services/invoice-extraction/` directory
- Create `shared/` for common utilities (future use)
- Create `docs/` for documentation
- Update root `README.md` with monorepo overview

### 2. Create Logger Utility (`services/invoice-extraction/invoice_extraction/utils/logger.py`)

- `setup_logger(service_name: str, enable_file_logging: bool = None)` function
- Check `DEBUG_LOG` environment variable (default: "false")
- When enabled: log to `logs/{service_name}.log` with rotation (10MB, 5 backups)
- When disabled: log ERROR level to stderr only
- Support structured logging with timestamps and log levels

### 3. Create Core Processor (`services/invoice-extraction/invoice_extraction/core/processor.py`)

- Extract `InvoiceSplitter` class from main.py
- Keep all processing methods intact
- Replace print statements with logger calls
- Add comprehensive docstrings with type hints
- Make output_dir optional with sensible defaults

### 4. Create CLI Interface (`services/invoice-extraction/invoice_extraction/cli.py`)

- Import `InvoiceSplitter` from `core.processor`
- Import logger from `utils.logger`
- Implement `main()` with argparse: `<attachment_id> [--output-dir DIR]`
- Add entry point in pyproject.toml: `invoice-extract`
- Handle errors gracefully with proper exit codes

### 5. Create Lambda Handler (`services/invoice-extraction/invoice_extraction/handlers/lambda_handler.py`)

- Function signature: `handler(event, context)`
- Parse SQS Records: `json.loads(record['body'])` → `{"attachment_id": 123}`
- Process to `/tmp/` directory (Lambda ephemeral storage)
- Batch processing support (handle multiple SQS records)
- Return success/failure status with processed attachment IDs
- Error handling with proper Lambda response format

### 6. Create Server Handler (`services/invoice-extraction/invoice_extraction/handlers/server_handler.py`)

- Main function: `run_sqs_worker()`
- Read `SQS_QUEUE_URL` from environment
- Long-polling loop: `receive_message(WaitTimeSeconds=20, MaxNumberOfMessages=1)`
- Parse message body, process with `InvoiceSplitter`
- Delete message on success, log and skip on error (DLQ will handle retries)
- Signal handling: graceful shutdown on SIGTERM/SIGINT
- Entry point: `if __name__ == "__main__": run_sqs_worker()`

### 7. Lambda Deployment Files

**`services/invoice-extraction/deployment/lambda/Dockerfile`:**

```dockerfile
FROM public.ecr.aws/lambda/python:3.13
# Install system dependencies (poppler for pdf2image)
RUN yum install -y poppler-utils
# Copy application code
COPY invoice_extraction ${LAMBDA_TASK_ROOT}/invoice_extraction
COPY pyproject.toml ${LAMBDA_TASK_ROOT}/
# Install Python dependencies
RUN pip install --no-cache-dir .
# Set handler
CMD ["invoice_extraction.handlers.lambda_handler.handler"]
```

**`services/invoice-extraction/deployment/lambda/template.yaml`:**

- SAM template with Lambda function resource
- SQS event source mapping
- Environment variables section (with placeholders)
- IAM role with policies: SQS (receive/delete), S3 (put), CloudWatch Logs
- Function config: Timeout 900s, Memory 2048MB, ReservedConcurrentExecutions

### 8. Systemd Service File (`services/invoice-extraction/deployment/systemd/invoice-extraction.service`)

```ini
[Unit]
Description=Invoice Extraction SQS Worker
After=network.target

[Service]
Type=simple
User=invoice-processor
WorkingDirectory=/opt/payables/services/invoice-extraction
EnvironmentFile=/etc/invoice-extraction/.env
ExecStart=/usr/bin/python3 -m invoice_extraction.handlers.server_handler
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 9. Service Configuration Files

**`services/invoice-extraction/pyproject.toml`:**

- Name: "invoice-extraction"
- Version: "0.1.0"
- Requires-python: ">=3.13"
- Dependencies: existing + add optional `watchtower` for CloudWatch
- Tool.uv: `dev-dependencies` for testing
- Scripts: `invoice-extract = "invoice_extraction.cli:main"`

**`services/invoice-extraction/.env.example`:**

```
# OpenAI Configuration
OPENAI_API_KEY=sk-...

# API Configuration
API_URL=https://api.example.com

# AWS Configuration
S3_BUCKET_NAME=my-bucket
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789/invoice-queue

# Logging (set to "true" to enable file logging)
DEBUG_LOG=false
```

### 10. Documentation Files

**`docs/DEVELOPMENT.md`:**

- Prerequisites: Python 3.13+, uv, poppler-utils
- Clone repository
- Navigate to `services/invoice-extraction/`
- Copy `.env.example` to `.env` and configure
- Install dependencies: `uv sync`
- Run CLI locally: `uv run invoice-extract <attachment_id>`
- Run tests: `uv run pytest`
- Debugging: Set `DEBUG_LOG=true` for verbose logging

**`docs/DEPLOYMENT.md`:**

*Lambda Deployment:*

- Prerequisites: AWS CLI, SAM CLI, Docker
- Build: `sam build` in `services/invoice-extraction/`
- Deploy: `sam deploy --guided`
- Configure environment variables in SAM
- Set up SQS trigger and DLQ

*EC2 Deployment:*

- SSH to EC2 instance
- Install Python 3.13, poppler-utils, git
- Clone repo to `/opt/payables/`
- Create user: `sudo useradd -r -s /bin/false invoice-processor`
- Install dependencies: `cd /opt/payables/services/invoice-extraction && pip install .`
- Copy `.env` to `/etc/invoice-extraction/.env`
- Copy systemd service: `sudo cp deployment/systemd/invoice-extraction.service /etc/systemd/system/`
- Enable and start: `sudo systemctl enable --now invoice-extraction`
- Check status: `sudo systemctl status invoice-extraction`
- View logs: `sudo journalctl -u invoice-extraction -f`

**`docs/ADDING_SERVICES.md`:**

- Create new directory: `services/<service-name>/`
- Required structure:
  ```
  services/<service-name>/
  ├── <service_name>/           # Python package (underscores)
  │   ├── __init__.py
  │   ├── core/                 # Business logic
  │   ├── handlers/             # Lambda/Server handlers (if applicable)
  │   ├── cli.py               # CLI interface (if applicable)
  │   └── utils/               # Service-specific utilities
  ├── deployment/
  │   ├── lambda/              # Lambda deployment files (if applicable)
  │   └── systemd/             # Systemd service files (if applicable)
  ├── tests/
  ├── pyproject.toml           # Service dependencies
  ├── README.md                # Service-specific documentation
  └── .env.example
  ```

- Update root README.md with service description
- Share common code via `shared/` directory
- Follow naming conventions: kebab-case for directories, snake_case for Python packages

**`services/invoice-extraction/README.md`:**

- Service overview and purpose
- Architecture diagram (text-based)
- Environment variables reference
- API/SQS message format
- Link to main docs for deployment

**Root `README.md`:**

- Monorepo overview
- List of services with descriptions
- Links to documentation
- Getting started (point to DEVELOPMENT.md)
- Repository structure explanation

## Files to Create/Modify

### Create:

- `services/invoice-extraction/invoice_extraction/__init__.py`
- `services/invoice-extraction/invoice_extraction/core/__init__.py`
- `services/invoice-extraction/invoice_extraction/core/processor.py`
- `services/invoice-extraction/invoice_extraction/handlers/__init__.py`
- `services/invoice-extraction/invoice_extraction/handlers/lambda_handler.py`
- `services/invoice-extraction/invoice_extraction/handlers/server_handler.py`
- `services/invoice-extraction/invoice_extraction/utils/__init__.py`
- `services/invoice-extraction/invoice_extraction/utils/logger.py`
- `services/invoice-extraction/invoice_extraction/cli.py`
- `services/invoice-extraction/deployment/lambda/Dockerfile`
- `services/invoice-extraction/deployment/lambda/template.yaml`
- `services/invoice-extraction/deployment/systemd/invoice-extraction.service`
- `services/invoice-extraction/tests/__init__.py`
- `services/invoice-extraction/pyproject.toml`
- `services/invoice-extraction/README.md`
- `services/invoice-extraction/.env.example`
- `shared/__init__.py`
- `docs/DEVELOPMENT.md`
- `docs/DEPLOYMENT.md`
- `docs/ADDING_SERVICES.md`
- Root `README.md`

### Keep:

- `test/main.py` (for reference during migration)

## Key Technical Decisions

- **Monorepo Structure**: Each service is self-contained with its own dependencies and deployment configs
- **Logger**: Conditional file logging via `DEBUG_LOG` env var, rotated at 10MB
- **SQS Format**: `{"attachment_id": <int>}` in message body
- **EC2 Handler**: Long-polling daemon (20s wait) for cost efficiency
- **Lambda**: Container image for system dependencies (poppler)
- **Service Isolation**: Each service has independent pyproject.toml and deployment configs
- **Shared Code**: Use `shared/` directory for cross-service utilities