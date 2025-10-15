# Quick Start Guide

## 1. Set Your OpenAI API Key

### Windows PowerShell (Recommended)
```powershell
$env:OPENAI_API_KEY="sk-your-api-key-here"
```

### Windows CMD
```cmd
set OPENAI_API_KEY=sk-your-api-key-here
```

### Verify it's set
```powershell
echo $env:OPENAI_API_KEY
```

## 2. Install Dependencies

If you haven't already:
```bash
uv sync
```

Or:
```bash
pip install openai pdf2image pillow pypdf
```

## 3. Run a Test

### Process a single PDF
```bash
python main.py 01-single-single.pdf --output-dir output
```

### Process all test PDFs
```bash
python test_all.py
```

Or on Windows, double-click:
```
test_all.bat
```

## 4. Check Results

Look in the `output/` folder:
- Split invoice PDFs will be named: `{original}_invoice_{number}.pdf`
- Corrupted files (if any) will be in: `output/errors/`

## Example Output

```
output/
├── 01-single-single_invoice_1.pdf
├── 01-single-single_invoice_1.json        # ← Structured invoice data
├── 03-single-multi-1_invoice_INV12345.pdf
├── 03-single-multi-1_invoice_INV12345.json
├── 04-multi-single_invoice_1.pdf
├── 04-multi-single_invoice_1.json
├── 04-multi-single_invoice_2.pdf
├── 04-multi-single_invoice_2.json
└── errors/
    └── 02-corrupted.pdf  (if couldn't be repaired)
```

Each JSON file contains:
- Invoice number, dates, amounts
- Customer and vendor names
- Line items with quantities and prices

## What the Script Does

1. ✓ Checks PDF for corruption (attempts repair if needed)
2. ✓ Converts pages to images
3. ✓ Sends each page to GPT-4 Vision for analysis
4. ✓ Groups pages into separate invoices
5. ✓ Extracts and saves each invoice as a new PDF
6. ✓ Extracts structured data and saves as JSON for each invoice

## Cost Estimate

GPT-4 Vision API usage:
- **Page analysis**: ~$0.01-0.02 per page (determines invoice boundaries)
- **Data extraction**: ~$0.02-0.04 per invoice (extracts structured data from all pages)

For the 5 test PDFs (assuming ~10 pages, ~15 invoices total): **~$0.30-0.80**

Note: Multi-page invoices send all pages together for data extraction to ensure complete line item capture.

## Troubleshooting

### "OPENAI_API_KEY not found"
→ Set the environment variable (see step 1 above)

### "Poppler not found"
→ Install poppler:
- Windows: Download from [here](https://github.com/oschwartz10612/poppler-windows/releases/) and add to PATH
- Run: `choco install poppler` (if you have Chocolatey)

### Import errors
→ Run `uv sync` or `pip install -r requirements.txt`

## Next Steps

- Process your own invoice PDFs:
  ```bash
  python main.py path/to/your/invoice.pdf --output-dir ./split
  ```

- Integrate into your workflow:
  ```python
  from main import InvoiceSplitter
  
  splitter = InvoiceSplitter()
  output_files = splitter.process_pdf("invoice.pdf", "output")
  ```

