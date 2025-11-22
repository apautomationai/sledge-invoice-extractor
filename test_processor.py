"""
Test script for invoice processor using local PDF files.

This script tests the invoice extraction processor with a random PDF from the data folder.
It mocks API calls and S3 uploads to allow local testing without external dependencies.
"""

import os
import sys
import random
from pathlib import Path
from unittest.mock import patch
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from invoice_extraction.core.processor import InvoiceSplitter
from invoice_extraction.utils.logger import setup_logger


def mock_fetch_attachment_metadata(attachment_id: int) -> Dict:
    """Mock function to return attachment metadata."""
    return {
        "id": attachment_id,
        "filename": f"test_attachment_{attachment_id}.pdf",
        "fileUrl": f"https://example.com/files/{attachment_id}.pdf",
        "status": "pending"
    }


def mock_update_attachment_status(attachment_id: int, status: str):
    """Mock function to update attachment status."""
    print(f"  [MOCK] Updated attachment {attachment_id} status to: {status}")


def mock_upload_to_s3(file_path: str, s3_key: str, mime_type: str = 'binary/octet-stream') -> str:
    """Mock function to upload file to S3."""
    print(f"  [MOCK] Uploaded to S3: {s3_key} (from {Path(file_path).name})")
    return s3_key


def mock_create_invoice_record(invoice_data: Dict, attachment_id: int, s3_pdf_key: str, s3_json_key: str):
    """Mock function to create a single invoice record."""
    inv_num = invoice_data.get("invoice_number", "N/A")
    print(f"  [MOCK] Created invoice record: {inv_num}")


def mock_create_invoice_records_batch(invoices: list):
    """Mock function to create invoice records in batch."""
    print(f"  [MOCK] Batch API call: Creating {len(invoices)} invoice record(s)")
    for idx, invoice in enumerate(invoices, 1):
        inv_num = invoice["invoice_data"].get("invoice_number", "N/A")
        print(f"    [MOCK] Invoice {idx}: {inv_num}")


def get_random_pdf() -> Path:
    """Get a random PDF file from the data folder."""
    data_dir = Path("data")
    if not data_dir.exists():
        raise FileNotFoundError("Data folder not found. Please ensure 'data' folder exists with PDF files.")
    
    pdf_files = list(data_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError("No PDF files found in data folder.")
    
    selected_pdf = random.choice(pdf_files)
    print(f"Selected PDF: {selected_pdf.name}")
    return selected_pdf



def main():
    """Main test function."""
    print("=" * 70)
    print("Invoice Processor Test Script")
    print("=" * 70)
    print()
    
    # Check for required environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable not set.")
        print("Please set it before running the test:")
        print("export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)
    
    # Set dummy environment variables for API and S3 (will be mocked anyway)
    os.environ.setdefault("API_URL", "https://api.example.com")
    os.environ.setdefault("S3_BUCKET_NAME", "test-bucket")
    
    # Get random PDF
    try:
        # pdf_path = get_random_pdf()
        pdf_path = Path('D:\\work\\sledge\\test\\data\\03-single-multi-1-1-2-test.pdf')
        # pdf_path = Path('D:\\work\\sledge\\test\\data\\05-multi-multi-1.pdf')
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    
    # Generate a random attachment ID for testing
    attachment_id = random.randint(1000, 9999)
    
    print(f"Attachment ID (test): {attachment_id}")
    print(f"PDF Path: {pdf_path.absolute()}")
    print()
    
    # Set up logger
    logger = setup_logger("test-processor", enable_file_logging=False)
    
    # Create output directory
    output_dir = Path("test_output") / str(attachment_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir.absolute()}")
    print()
    
    try:
        # Initialize processor
        print("Initializing processor...")
        splitter = InvoiceSplitter(logger=logger)
        
        # Mock the API and S3 methods
        with patch.object(splitter, 'fetch_attachment_metadata', side_effect=mock_fetch_attachment_metadata), \
             patch.object(splitter, 'update_attachment_status', side_effect=mock_update_attachment_status), \
             patch.object(splitter, 'upload_to_s3', side_effect=mock_upload_to_s3), \
             patch.object(splitter, 'create_invoice_record', side_effect=mock_create_invoice_record), \
             patch.object(splitter, 'create_invoice_records_batch', side_effect=mock_create_invoice_records_batch):
            
            print("Processing PDF (API and S3 calls are mocked)...")
            print("-" * 70)
            
            # Process the PDF
            output_files = splitter.process_pdf(
                str(pdf_path),
                attachment_id,
                str(output_dir.parent)  # Pass parent so it creates attachment_id subfolder
            )
            
            print("-" * 70)
            print()
            
            if output_files:
                print(f"✓ Successfully processed {len(output_files)} invoice(s)")
                print()
                print("Output files:")
                for file in output_files:
                    file_path = Path(file)
                    if file_path.exists():
                        size_kb = file_path.stat().st_size / 1024
                        print(f"  ✓ {file_path.name} ({size_kb:.1f} KB)")
                    else:
                        print(f"  ✗ {file_path.name} (not found)")
                
                # Check for JSON files
                json_files = list(output_dir.glob("*.json"))
                if json_files:
                    print()
                    print("JSON data files:")
                    for json_file in json_files:
                        size_kb = json_file.stat().st_size / 1024
                        print(f"  ✓ {json_file.name} ({size_kb:.1f} KB)")
                
                print()
                print("=" * 70)
                print("Test completed successfully!")
                print("=" * 70)
                sys.exit(0)
            else:
                print("✗ No invoices were extracted")
                print("  This could mean:")
                print("  - The PDF is corrupted")
                print("  - The PDF doesn't contain invoices")
                print("  - There was an error during processing")
                sys.exit(1)
                
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

