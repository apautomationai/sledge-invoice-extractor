# Invoice Extraction Service

A microservice for processing PDF invoices using OpenAI GPT-4 Vision API. Handles invoice splitting, data extraction, and S3 uploads.

## Features

- **PDF Processing**: Handles single and multi-page invoices
- **Invoice Splitting**: Automatically detects and splits multiple invoices from a single PDF
- **Data Extraction**: Extracts structured invoice data using GPT-4 Vision
- **Multiple Deployment Options**: Supports AWS Lambda, EC2, and CLI usage
- **Robust Error Handling**: PDF corruption detection and repair
- **Comprehensive Logging**: Configurable logging with file rotation

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   SQS Queue     │───▶│  Lambda/EC2      │───▶│   S3 Storage    │
│ (attachment_id) │    │  Handler         │    │ (PDFs + JSON)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   OpenAI API     │
                       │ (GPT-4 Vision)   │
                       └──────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │  Database API    │
                       │ (Invoice Records)│
                       └──────────────────┘
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT-4 Vision |
| `API_URL` | Yes | Base URL for attachment API |
| `S3_BUCKET_NAME` | Yes | S3 bucket for file uploads |
| `SQS_QUEUE_URL` | No | SQS queue URL (for server handler) |
| `DEBUG_LOG` | No | Enable file logging (default: false) |

## Usage

### CLI

Process a single attachment:
```bash
invoice-extract 123
```

Process with custom output directory:
```bash
invoice-extract 123 --output-dir ./my-output
```

### SQS Message Format

Send messages to the SQS queue in this format:
```json
{
  "attachment_id": 123
}
```

### Supported Invoice Types

- **Single invoice, single page**: Standard invoice on one page
- **Single invoice, multiple pages**: Invoice spanning multiple pages
- **Multiple invoices, one page each**: Several invoices, one per page
- **Multiple invoices, multiple pages each**: Complex multi-invoice documents

### Extracted Data

The service extracts the following invoice data:

```json
{
  "invoice_number": "INV-12345",
  "customer_name": "Customer Company Inc.",
  "vendor_name": "Vendor Corp",
  "invoice_date": "2024-01-15",
  "due_date": "2024-02-15",
  "total_amount": 1250.00,
  "currency": "USD",
  "description": "Monthly services",
  "line_items": [
    {
      "item_name": "Consulting Services",
      "quantity": 40,
      "unit_price": 25.00,
      "total_price": 1000.00
    }
  ]
}
```

## Deployment

### AWS Lambda

Deploy using SAM:
```bash
cd services/invoice-extraction
sam build
sam deploy --guided
```

### EC2

Deploy as systemd service:
```bash
# Copy service file
sudo cp deployment/systemd/invoice-extraction.service /etc/systemd/system/

# Enable and start
sudo systemctl enable invoice-extraction
sudo systemctl start invoice-extraction
```

See [DEPLOYMENT.md](../../docs/DEPLOYMENT.md) for detailed deployment instructions.

## Development

### Local Setup

1. Install dependencies:
```bash
cd services/invoice-extraction
uv sync
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run locally:
```bash
uv run invoice-extract <attachment_id>
```

See [DEVELOPMENT.md](../../docs/DEVELOPMENT.md) for detailed development setup.

## Error Handling

The service includes comprehensive error handling:

- **PDF Corruption**: Automatically detects and attempts to repair corrupted PDFs
- **API Failures**: Graceful handling of OpenAI API errors with fallback behavior
- **Network Issues**: Retry logic for S3 uploads and API calls
- **Invalid Data**: Validation and error reporting for malformed input

## Logging

Configure logging behavior with the `DEBUG_LOG` environment variable:

- `DEBUG_LOG=false` (default): Log only errors to stderr
- `DEBUG_LOG=true`: Log all messages to file with rotation (10MB, 5 backups)

Log files are stored in `logs/invoice-extraction.log` when file logging is enabled.

## Performance

### Lambda Configuration

- **Memory**: 2048 MB
- **Timeout**: 900 seconds (15 minutes)
- **Concurrency**: 10 reserved concurrent executions

### Processing Times

Typical processing times:
- Single page invoice: 30-60 seconds
- Multi-page invoice: 60-120 seconds
- Large documents (10+ pages): 2-5 minutes

## Monitoring

### CloudWatch Metrics (Lambda)

- Duration, Errors, Invocations, Throttles
- Set up alarms for error rates and duration

### Systemd Journal (EC2)

```bash
# View logs
sudo journalctl -u invoice-extraction -f

# Check status
sudo systemctl status invoice-extraction
```

## Troubleshooting

### Common Issues

1. **PDF processing errors**: Ensure poppler-utils is installed
2. **API errors**: Verify OpenAI API key and API_URL
3. **Permission errors**: Check AWS credentials and S3 bucket policies

### Debug Mode

Enable debug logging for detailed troubleshooting:
```bash
# .env
DEBUG_LOG=true
```

This creates detailed logs including PDF processing steps, API calls, and error details.
