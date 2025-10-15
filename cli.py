"""
Command-line interface for invoice extraction service.

This module provides a CLI for processing PDF invoices from attachment IDs.
"""

import os
import sys
import argparse
import tempfile
from pathlib import Path

from invoice_extraction.core.processor import InvoiceSplitter
from invoice_extraction.utils.logger import setup_logger


def main():
    """Main CLI entry point for invoice extraction."""
    parser = argparse.ArgumentParser(
        description="Split invoices from PDF using OpenAI GPT-4 Vision and Attachment API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  invoice-extract 6
  invoice-extract 6 --output-dir ./split_invoices
  
Environment Variables Required:
  OPENAI_API_KEY - OpenAI API key for GPT-4 Vision
  API_URL - Base URL for attachment API (e.g., https://api.example.com)
  S3_BUCKET_NAME - S3 bucket name for uploads
  AWS credentials should be configured via AWS CLI
        """
    )
    parser.add_argument(
        "attachment_id",
        type=int,
        help="Attachment ID to process"
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory for split invoices (default: ./output)",
        default="output"
    )
    
    args = parser.parse_args()
    
    # Set up logger
    logger = setup_logger("invoice-extraction")
    
    temp_pdf_path = None
    
    try:
        # Initialize the splitter
        logger.info(f"Initializing invoice splitter for attachment ID: {args.attachment_id}")
        splitter = InvoiceSplitter(logger=logger)
        
        # Fetch attachment metadata
        logger.info(f"Fetching attachment metadata for ID: {args.attachment_id}")
        attachment_data = splitter.fetch_attachment_metadata(args.attachment_id)
        
        file_url = attachment_data.get("fileUrl")
        filename = attachment_data.get("filename", f"attachment_{args.attachment_id}.pdf")
        
        if not file_url:
            raise ValueError("File URL not found in attachment metadata")
        
        logger.info(f"Attachment: {filename}")
        logger.info(f"File URL: {file_url}")
        
        # Download PDF to temporary location
        temp_pdf_path = tempfile.mktemp(suffix=".pdf", prefix=f"attachment_{args.attachment_id}_")
        logger.info(f"\nDownloading PDF from S3...")
        splitter.download_pdf_from_url(file_url, temp_pdf_path)
        
        # Process the PDF
        logger.info(f"\nProcessing PDF...")
        output_files = splitter.process_pdf(temp_pdf_path, args.attachment_id, args.output_dir)
        
        if output_files:
            logger.info("\nOutput files:")
            for file in output_files:
                logger.info(f"  - {file}")
            logger.info(f"\n✓ Successfully processed attachment {args.attachment_id}")
            sys.exit(0)
        else:
            logger.error("\nNo invoices were extracted (file may be corrupted)")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Clean up temporary PDF file
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            try:
                os.remove(temp_pdf_path)
                logger.info(f"\nCleaned up temporary file: {temp_pdf_path}")
            except Exception as e:
                logger.warning(f"\nWarning: Failed to clean up temporary file: {e}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
