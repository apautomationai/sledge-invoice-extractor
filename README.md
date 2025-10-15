# Payables - Microservices Monorepo

A microservices-based platform for processing financial documents and managing payables workflows.

## Overview

This monorepo contains multiple microservices designed to handle different aspects of financial document processing. Each service is self-contained with its own dependencies, deployment configurations, and documentation.

## Repository Structure

```
payables/
├── services/                    # Microservices directory
│   └── invoice-extraction/      # Invoice processing service
├── shared/                      # Shared libraries across services
├── docs/                        # Documentation
│   ├── DEVELOPMENT.md          # Development setup guide
│   ├── DEPLOYMENT.md           # Deployment guides
│   └── ADDING_SERVICES.md      # Guide for adding new services
└── README.md                   # This file
```

## Services

### invoice-extraction

**Purpose**: Processes PDF invoices using OpenAI GPT-4 Vision API

**Features**:
- Automatically splits multi-invoice PDFs
- Extracts structured invoice data
- Handles various invoice formats (single/multi-page, single/multi-invoice)
- Uploads processed files to S3
- Creates database records via API

**Deployment Options**:
- AWS Lambda (serverless)
- EC2 (long-running service)
- CLI (local processing)

**Quick Start**:
```bash
cd services/invoice-extraction
uv sync
cp .env.example .env  # Configure your API keys
uv run invoice-extract <attachment_id>
```

## Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- AWS CLI configured (for cloud deployments)

### Development Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd payables
   ```

2. **Choose a service to work with:**
   ```bash
   cd services/invoice-extraction  # or any other service
   ```

3. **Follow the service-specific setup:**
   - See `services/<service-name>/README.md` for service details
   - See [DEVELOPMENT.md](docs/DEVELOPMENT.md) for general development guide

### Adding New Services

See [ADDING_SERVICES.md](docs/ADDING_SERVICES.md) for a comprehensive guide on adding new microservices to this monorepo.

## Documentation

- **[DEVELOPMENT.md](docs/DEVELOPMENT.md)**: Local development setup and workflow
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)**: Deployment guides for AWS Lambda and EC2
- **[ADDING_SERVICES.md](docs/ADDING_SERVICES.md)**: Guide for adding new microservices

## Architecture Principles

### Service Isolation

Each microservice is self-contained with:
- Independent dependencies (`pyproject.toml`)
- Separate deployment configurations
- Own logging and monitoring
- Isolated environment variables

### Shared Code

Common utilities are placed in the `shared/` directory:
- AWS utilities (S3, SQS, Lambda helpers)
- Database utilities
- Authentication utilities
- General-purpose utilities

### Deployment Flexibility

Services support multiple deployment patterns:
- **Serverless**: AWS Lambda with SQS triggers
- **Long-running**: EC2 with systemd services
- **CLI**: Local processing and testing
- **Hybrid**: Mix of deployment patterns as needed

### Naming Conventions

- **Directories**: kebab-case (`invoice-extraction`, `payment-processor`)
- **Python packages**: snake_case (`invoice_extraction`, `payment_processor`)
- **Environment variables**: UPPER_SNAKE_CASE (`API_URL`, `S3_BUCKET_NAME`)

## Common Workflows

### Local Development

1. Navigate to a service directory
2. Install dependencies with `uv sync`
3. Configure environment variables
4. Run tests and local processing
5. Deploy when ready

### Adding Features

1. Create feature branch
2. Implement changes in the appropriate service
3. Add tests
4. Update documentation
5. Deploy and test in staging
6. Merge to main

### Monitoring and Maintenance

- **Lambda services**: Monitor via CloudWatch
- **EC2 services**: Monitor via systemd journal
- **Logs**: Configure with `DEBUG_LOG` environment variable
- **Health checks**: Implement service-specific health endpoints

## Contributing

1. Follow the service structure defined in [ADDING_SERVICES.md](docs/ADDING_SERVICES.md)
2. Maintain backward compatibility
3. Update documentation for any API changes
4. Add tests for new functionality
5. Use consistent error handling and logging patterns

## Support

- **Service-specific issues**: Check the service's README.md
- **Development issues**: See [DEVELOPMENT.md](docs/DEVELOPMENT.md)
- **Deployment issues**: See [DEPLOYMENT.md](docs/DEPLOYMENT.md)
- **Adding services**: See [ADDING_SERVICES.md](docs/ADDING_SERVICES.md)