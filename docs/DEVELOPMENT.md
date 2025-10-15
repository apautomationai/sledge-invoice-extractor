# Development Guide

This guide covers setting up the invoice extraction service for local development.

## Prerequisites

- Python 3.13 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- poppler-utils (for PDF processing)
- AWS CLI configured (for S3 and SQS access)

### Installing poppler-utils

**Windows:**
```bash
# Using Chocolatey
choco install poppler

# Or download from https://poppler.freedesktop.org/
```

**macOS:**
```bash
brew install poppler
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install poppler-utils
```

## Local Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd payables
   ```

2. **Navigate to the invoice extraction service:**
   ```bash
   cd services/invoice-extraction
   ```

3. **Copy environment file:**
   ```bash
   cp .env.example .env
   ```

4. **Configure environment variables in `.env`:**
   ```bash
   # Required
   OPENAI_API_KEY=sk-your-openai-api-key
   API_URL=https://your-api-endpoint.com
   S3_BUCKET_NAME=your-s3-bucket
   
   # Optional
   DEBUG_LOG=true  # Enable verbose logging for development
   ```

5. **Install dependencies:**
   ```bash
   uv sync
   ```

## Running the Service

### CLI Usage

Process a single attachment:
```bash
uv run invoice-extract 123
```

Process with custom output directory:
```bash
uv run invoice-extract 123 --output-dir ./my-output
```

### Running Tests

```bash
uv run pytest
```

### Running with Debug Logging

Set `DEBUG_LOG=true` in your `.env` file to enable detailed file logging:
```bash
# .env
DEBUG_LOG=true
```

This will create a `logs/invoice-extraction.log` file with detailed processing information.

## Development Workflow

1. **Make changes to the code**
2. **Test locally:**
   ```bash
   uv run invoice-extract <test-attachment-id>
   ```
3. **Run tests:**
   ```bash
   uv run pytest
   ```
4. **Check logs:**
   - If `DEBUG_LOG=true`: Check `logs/invoice-extraction.log`
   - Otherwise: Check console output

## Code Structure

```
services/invoice-extraction/
├── invoice_extraction/
│   ├── core/           # Business logic (InvoiceSplitter)
│   ├── handlers/       # Lambda and server handlers
│   ├── utils/          # Utilities (logging, etc.)
│   └── cli.py          # Command-line interface
├── deployment/         # Deployment configurations
├── tests/             # Test files
└── pyproject.toml     # Dependencies and configuration
```

## Adding New Features

1. **Core functionality**: Add to `invoice_extraction/core/`
2. **Utilities**: Add to `invoice_extraction/utils/`
3. **CLI commands**: Modify `invoice_extraction/cli.py`
4. **Tests**: Add to `tests/` directory

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT-4 Vision |
| `API_URL` | Yes | Base URL for attachment API |
| `S3_BUCKET_NAME` | Yes | S3 bucket for file uploads |
| `SQS_QUEUE_URL` | No | SQS queue URL (for server handler) |
| `DEBUG_LOG` | No | Enable file logging (default: false) |

## Troubleshooting

### Common Issues

1. **PDF processing errors:**
   - Ensure poppler-utils is installed
   - Check PDF file is not corrupted
   - Verify file permissions

2. **API errors:**
   - Verify `OPENAI_API_KEY` is valid
   - Check `API_URL` is accessible
   - Ensure AWS credentials are configured

3. **Import errors:**
   - Run `uv sync` to install dependencies
   - Check Python version (3.13+ required)

### Debug Mode

Enable debug logging for detailed troubleshooting:
```bash
# .env
DEBUG_LOG=true
```

This creates detailed logs in `logs/invoice-extraction.log` including:
- PDF processing steps
- API calls and responses
- Error details and stack traces
