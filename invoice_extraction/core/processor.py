"""
Core invoice processing functionality using OpenAI GPT-4 Vision API.

This module contains the InvoiceSplitter class that handles PDF invoice processing,
including corruption detection, repair, invoice splitting, and data extraction.
"""

import os
import json
import base64
import shutil
import tempfile
from pathlib import Path
from io import BytesIO
from typing import List, Dict, Optional, Tuple, Any

import requests
import boto3
from botocore.exceptions import ClientError
from openai import OpenAI
from pdf2image import convert_from_path
from pypdf import PdfReader, PdfWriter
from PIL import Image


class InvoiceSplitter:
    """
    Invoice processing service using OpenAI GPT-4 Vision API.
    
    Handles various invoice scenarios:
    - Single invoice, single page
    - Single invoice, multiple pages  
    - Multiple invoices, one page each
    - Multiple invoices, multiple pages each
    """
    
    def __init__(self, api_key: Optional[str] = None, logger: Optional[Any] = None):
        """
        Initialize the invoice splitter with OpenAI API key and AWS/API configurations.
        
        Args:
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
            logger: Logger instance for logging output
        """
        self.logger = logger
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")
        self.client = OpenAI(api_key=self.api_key)
        
        # API configuration
        self.api_url = os.getenv("API_URL")
        if not self.api_url:
            raise ValueError("API_URL environment variable not found.")
        
        # S3 configuration
        self.s3_bucket_name = os.getenv("S3_BUCKET_NAME")
        if not self.s3_bucket_name:
            raise ValueError("S3_BUCKET_NAME environment variable not found.")
        
        # Initialize S3 client with default AWS CLI credentials
        self.s3_client = boto3.client('s3')
        
    def _log(self, message: str, level: str = "info"):
        """Log message using the configured logger or print as fallback."""
        if self.logger:
            if level == "error":
                self.logger.error(message)
            elif level == "warning":
                self.logger.warning(message)
            elif level == "debug":
                self.logger.debug(message)
            else:
                self.logger.info(message)
        else:
            print(message)
    
    def check_pdf_corruption(self, pdf_path: str) -> Tuple[bool, Optional[str]]:
        """
        Check if PDF is corrupted and attempt to repair it.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            reader = PdfReader(pdf_path)
            # Try to access pages
            num_pages = len(reader.pages)
            if num_pages == 0:
                return False, "PDF has no pages"
            # Try to access first page content
            _ = reader.pages[0]
            return True, None
        except Exception as e:
            return False, str(e)
    
    def repair_pdf(self, pdf_path: str) -> Tuple[bool, Optional[str]]:
        """
        Attempt to repair a corrupted PDF.
        
        Args:
            pdf_path: Path to the corrupted PDF file
            
        Returns:
            Tuple of (success, repaired_path or error_message)
        """
        try:
            # Try to read with strict=False for more lenient parsing
            reader = PdfReader(pdf_path, strict=False)
            
            # Create a new PDF writer
            writer = PdfWriter()
            
            # Try to copy pages
            for page in reader.pages:
                writer.add_page(page)
            
            # Save repaired PDF
            repaired_path = pdf_path.replace(".pdf", "_repaired.pdf")
            with open(repaired_path, "wb") as output_file:
                writer.write(output_file)
            
            # Verify the repaired PDF
            is_valid, error = self.check_pdf_corruption(repaired_path)
            if is_valid:
                return True, repaired_path
            else:
                os.remove(repaired_path)
                return False, f"Repair failed: {error}"
        except Exception as e:
            return False, f"Repair error: {str(e)}"
    
    def fetch_attachment_metadata(self, attachment_id: int) -> Dict:
        """
        Fetch attachment metadata from the API.
        
        Args:
            attachment_id: ID of the attachment
            
        Returns:
            Dictionary containing attachment metadata
        """
        try:
            url = f"{self.api_url}/api/v1/processor/attachments/{attachment_id}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if not data.get("success"):
                raise ValueError(f"API returned success=false: {data}")
            
            return data.get("data")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch attachment metadata: {str(e)}")
    
    def update_attachment_status(self, attachment_id: int, status: str):
        """
        Update attachment status via API.
        
        Args:
            attachment_id: ID of the attachment
            status: Status value ("processing", "success", or "failed")
        """
        try:
            url = f"{self.api_url}/api/v1/processor/attachments/{attachment_id}"
            payload = {"status": status}
            response = requests.patch(url, json=payload, timeout=30)
            response.raise_for_status()
            
            self._log(f"Updated attachment {attachment_id} status to: {status}")
        except requests.exceptions.RequestException as e:
            # Log warning but don't raise - status update failure shouldn't stop processing
            self._log(f"Warning: Failed to update attachment status: {str(e)}", "warning")
    
    def download_pdf_from_url(self, file_url: str, output_path: str):
        """
        Download PDF from URL to local file.
        
        Args:
            file_url: URL of the PDF file
            output_path: Local path to save the PDF
        """
        try:
            response = requests.get(file_url, timeout=60, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self._log(f"Downloaded PDF to: {output_path}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to download PDF: {str(e)}")
    
    def upload_to_s3(self, file_path: str, s3_key: str, mime_type: str='binary/octet-stream') -> str:
        """
        Upload file to S3.
        
        Args:
            file_path: Local path to file
            s3_key: S3 key for the uploaded file
            mime_type: MIME type of the uploaded file
        Returns:
            S3 key of the uploaded file
        """
        try:
            with open(file_path, 'rb') as f:
                self.s3_client.upload_fileobj(f, self.s3_bucket_name, s3_key, ExtraArgs={'ContentType': mime_type})
            
            self._log(f"    Uploaded to S3: {s3_key}")
            return s3_key
        except ClientError as e:
            raise Exception(f"Failed to upload to S3: {str(e)}")
    
    def create_invoice_record(self, invoice_data: Dict, attachment_id: int, 
                            s3_pdf_key: str, s3_json_key: str):
        """
        Create invoice record in database via API.
        
        Args:
            invoice_data: Extracted invoice data
            attachment_id: ID of the source attachment
            s3_pdf_key: S3 key of the uploaded PDF
            s3_json_key: S3 key of the uploaded JSON
        """
        # Prepare payload with all invoice data plus additional fields
        payload = {
            **invoice_data,
            "attachment_id": attachment_id,
            "s3_pdf_key": s3_pdf_key,
            "s3_json_key": s3_json_key
        }
        try:
            
            # create invoice record in database
            response = requests.post(f"{self.api_url}/api/v1/processor/invoices", json=payload, timeout=30)
            response.raise_for_status()
            
            self._log(f"    Created invoice record in database")
        except requests.exceptions.RequestException as e:
            # Log error but don't raise - continue processing other invoices
            self._log(f"    Warning: Failed to create invoice record: {str(e)}", "warning")
    
    def create_invoice_records_batch(self, invoices: List[Dict]):
        """
        Create multiple invoice records in a single batch API call.
        
        Args:
            invoices: List of invoice dictionaries, each containing:
                - invoice_data: Dict with invoice fields
                - attachment_id: int
                - s3_pdf_key: str
                - s3_json_key: str
        """
        if not invoices:
            return
        
        try:
            # Prepare batch payload
            payload = {
                "invoices": [
                    {
                        **invoice["invoice_data"],
                        "attachment_id": invoice["attachment_id"],
                        "s3_pdf_key": invoice["s3_pdf_key"],
                        "s3_json_key": invoice["s3_json_key"]
                    }
                    for invoice in invoices
                ]
            }
            
            # Try batch endpoint first
            try:
                response = requests.post(
                    # f"{self.api_url}/api/v1/processor/invoices/batch",
                    f"https://webhook.site/1629bfe9-6548-4055-8078-857d4b2265f1",
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()
                self._log(f"    Created {len(invoices)} invoice records in batch")
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    # Batch endpoint doesn't exist, fall back to individual calls
                    self._log(f"    Batch endpoint not available, creating {len(invoices)} invoices individually...")
                    for invoice in invoices:
                        try:
                            self.create_invoice_record(
                                invoice["invoice_data"],
                                invoice["attachment_id"],
                                invoice["s3_pdf_key"],
                                invoice["s3_json_key"]
                            )
                        except Exception as individual_error:
                            self._log(f"    Warning: Failed to create invoice record: {individual_error}", "warning")
                else:
                    raise
                    
        except requests.exceptions.RequestException as e:
            self._log(f"    Warning: Failed to create invoice records: {str(e)}", "warning")
            # Fallback to individual calls
            self._log(f"    Attempting individual invoice creation...")
            for invoice in invoices:
                try:
                    self.create_invoice_record(
                        invoice["invoice_data"],
                        invoice["attachment_id"],
                        invoice["s3_pdf_key"],
                        invoice["s3_json_key"]
                    )
                except Exception as individual_error:
                    self._log(f"    Warning: Failed to create invoice record: {individual_error}", "warning")
    
    def image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buffered = BytesIO()
        # Convert to RGB if necessary
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(buffered, format="JPEG", quality=85)
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return img_str
    
    def analyze_and_extract_invoice(self, images: List[Image.Image], page_nums: List[int], total_pages: int) -> Dict:
        """
        Combined analysis and extraction: determines if this is a complete invoice
        and extracts all structured data in a single AI call.
        
        Args:
            images: List of PIL Images for the potential invoice pages
            page_nums: List of page numbers (1-indexed) for these images
            total_pages: Total number of pages in the document
            
        Returns:
            Dictionary with:
            - is_complete_invoice: bool (whether this group forms a complete invoice)
            - is_invoice_start: bool (whether first page starts a new invoice)
            - has_continuation: bool (whether invoice continues to next pages)
            - All invoice data fields (invoice_number, customer_name, vendor_name, etc.)
            - line_items: array
            - confidence: float
            - reasoning: string
        """
        # Convert all images to base64
        base64_images = [self.image_to_base64(img) for img in images]
        
        page_info = f"Pages {page_nums[0]}-{page_nums[-1]} of {total_pages}" if len(page_nums) > 1 else f"Page {page_nums[0]} of {total_pages}"
        
        prompt = f"""Analyze these document pages ({page_info}) and perform TWO tasks:

TASK 1: Determine invoice boundaries
- Does the FIRST page START a new invoice? (Look for invoice headers, invoice numbers, "INVOICE" title, billing/shipping addresses at top)
- Do these pages form a COMPLETE invoice? (All pages belong to the same invoice, no continuation to next pages)
- Is there a CONTINUATION to another page? (Look for "continued on next page", partial tables at end)

TASK 2: Extract invoice data (if this is an invoice)
Extract all relevant information from these pages:

1. invoice_number: The invoice number/identifier
2. customer_name: The customer/buyer name (the "Bill To" or recipient)
3. vendor_name: The vendor/seller name (the "From" or issuer)
4. vendor_address: The vendor/seller address
5. vendor_phone: The vendor/seller phone number
6. vendor_email: The vendor/seller email address
7. invoice_date: Invoice date in YYYY-MM-DD format
8. due_date: Payment due date in YYYY-MM-DD format (if available)
9. total_amount: Total invoice amount as a number
10. currency: Currency code (USD, EUR, etc.)
11. total_tax: Total tax amount as a number
12. description: Brief description or summary of the invoice
13. line_items: Array of items with item_name, quantity, unit_price, total_price

Important:
- If a field is not found, use null
- For line_items, extract ALL items across all pages
- Ensure amounts are numbers, not strings
- Use YYYY-MM-DD format for dates

Respond ONLY with valid JSON in this exact format:
{{
    "is_complete_invoice": true/false,
    "is_invoice_start": true/false,
    "has_continuation": true/false,
    "invoice_number": "string or null",
    "customer_name": "string or null",
    "vendor_name": "string or null",
    "vendor_address": "string or null",
    "vendor_phone": "string or null",
    "vendor_email": "string or null",
    "invoice_date": "YYYY-MM-DD or null",
    "due_date": "YYYY-MM-DD or null",
    "total_amount": number or null,
    "currency": "string or null",
    "total_tax": number or null,
    "description": "string or null",
    "line_items": [
        {{
            "item_name": "string",
            "quantity": number or null,
            "unit_price": number or null,
            "total_price": number or null
        }}
    ],
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""

        try:
            # Build message content with all images
            content = [{"type": "text", "text": prompt}]
            
            # Add all page images
            for img_b64 in base64_images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}",
                        "detail": "high"
                    }
                })
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                max_tokens=2500,
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(result_text)
            return result
            
        except Exception as e:
            self._log(f"    Warning: Vision API error: {str(e)}", "warning")
            # Fallback: assume it's a complete invoice
            return {
                "is_complete_invoice": True,
                "is_invoice_start": True,
                "has_continuation": False,
                "invoice_number": None,
                "customer_name": None,
                "vendor_name": None,
                "vendor_address": None,
                "vendor_phone": None,
                "vendor_email": None,
                "invoice_date": None,
                "due_date": None,
                "total_amount": None,
                "currency": None,
                "total_tax": None,
                "description": None,
                "line_items": [],
                "confidence": 0.0,
                "reasoning": f"API error: {str(e)}"
            }
    
    def analyze_page_with_vision(self, image: Image.Image, page_num: int, total_pages: int) -> Dict:
        """
        Analyze a page image using GPT-4 Vision to detect invoice information.
        
        Args:
            image: PIL Image object of the page
            page_num: Current page number (1-indexed)
            total_pages: Total number of pages in the document
        
        Returns:
            Dict with keys: is_invoice_start, is_continuation, invoice_number, confidence
        """
        base64_image = self.image_to_base64(image)
        
        prompt = f"""Analyze this document page (page {page_num} of {total_pages}) and determine:

1. Does this page START a new invoice? (Look for invoice headers, invoice numbers, "INVOICE" title, billing/shipping addresses at top)
2. Is this page a CONTINUATION of a previous invoice? (Look for "continued from previous page", partial tables, no invoice header)
3. What is the invoice number/identifier if visible? (e.g., "INV-12345", "Invoice #67890")

Consider these patterns:
- New invoice pages typically have: Invoice header/title, invoice number prominently displayed, billing "From" and "To" addresses, invoice date
- Continuation pages typically have: Itemized lists continuing, page numbers like "Page 2 of 3", no invoice header/number, table rows continuing
- Some invoices may have multiple invoices on one page (rare but possible)

Respond ONLY with valid JSON in this exact format:
{{
    "is_invoice_start": true/false,
    "is_continuation": true/false,
    "invoice_number": "string or null",
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(result_text)
            return result
            
        except Exception as e:
            self._log(f"  Warning: Vision API error on page {page_num}: {str(e)}", "warning")
            # Fallback: assume each page is a new invoice if we can't analyze
            return {
                "is_invoice_start": True,
                "is_continuation": False,
                "invoice_number": None,
                "confidence": 0.0,
                "reasoning": f"API error: {str(e)}"
            }
    
    def group_pages_into_invoices(self, analyses: List[Dict]) -> List[List[int]]:
        """
        Group page numbers into invoice groups based on AI analysis.
        
        Args:
            analyses: List of analysis results for each page
            
        Returns:
            List of invoice groups, where each group is a list of page numbers (0-indexed)
        """
        if not analyses:
            return []
        
        invoice_groups = []
        current_group = [0]  # Start with first page
        
        for i in range(1, len(analyses)):
            analysis = analyses[i]
            
            # If this page starts a new invoice, close current group and start new one
            if analysis.get("is_invoice_start", False):
                invoice_groups.append(current_group)
                current_group = [i]
            # If it's a continuation or uncertain, add to current group
            else:
                current_group.append(i)
        
        # Don't forget the last group
        if current_group:
            invoice_groups.append(current_group)
        
        return invoice_groups
    
    def extract_invoice_data(self, images: List[Image.Image]) -> Dict:
        """
        Extract structured invoice data from invoice page images using GPT-4 Vision.
        
        Args:
            images: List of PIL Images for all pages of the invoice
            
        Returns:
            Dictionary with structured invoice data
        """
        # Convert all images to base64 for multi-page invoices
        base64_images = [self.image_to_base64(img) for img in images]
        
        # Create the prompt for data extraction
        prompt = """Analyze this invoice document and extract all relevant information.

For multi-page invoices, combine information from all pages.

Extract and return the following information in JSON format:

1. invoice_number: The invoice number/identifier
2. customer_name: The customer/buyer name (the "Bill To" or recipient)
3. vendor_name: The vendor/seller name (the "From" or issuer)
4. vendor_address: The vendor/seller address (the "From" or issuer address)
5. vendor_phone: The vendor/seller phone number (the "From" or issuer phone number)
6. vendor_email: The vendor/seller email address (the "From" or issuer email address)
7. invoice_date: Invoice date in YYYY-MM-DD format
8. due_date: Payment due date in YYYY-MM-DD format (if available)
9. total_amount: Total invoice amount as a number
10. currency: Currency code (USD, EUR, etc.)
11. total_tax: Total tax amount as a number
12. description: Brief description or summary of the invoice
13. line_items: Array of items with:
   - item_name: Name/description of the item/service
   - quantity: Quantity ordered
   - unit_price: Price per unit (null if not available)
   - total_price: Total price for this line item

Important:
- If a field is not found, use null
- For line_items, extract ALL items across all pages
- Ensure amounts are numbers, not strings
- Use YYYY-MM-DD format for dates

Respond ONLY with valid JSON in this exact format:
{
    "invoice_number": "string or null",
    "customer_name": "string or null",
    "vendor_name": "string or null",
    "vendor_address": "string or null",
    "vendor_phone": "string or null",
    "vendor_email": "string or null",
    "invoice_date": "YYYY-MM-DD or null",
    "due_date": "YYYY-MM-DD or null",
    "total_amount": number or null,
    "currency": "string or null",
    "total_tax": number or null,
    "description": "string or null",
    "line_items": [
        {
            "item_name": "string",
            "quantity": number or null,
            "unit_price": number or null,
            "total_price": number or null
        }
    ]
}"""

        try:
            # Build message content with all images
            content = [{"type": "text", "text": prompt}]
            
            # Add all page images
            for img_b64 in base64_images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}",
                        "detail": "high"
                    }
                })
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                max_tokens=2000,
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            invoice_data = json.loads(result_text)
            return invoice_data
            
        except Exception as e:
            self._log(f"    Warning: Error extracting invoice data: {str(e)}", "warning")
            # Return empty structure if extraction fails
            return {
                "invoice_number": None,
                "customer_name": None,
                "vendor_name": None,
                "vendor_address": None,
                "vendor_phone": None,
                "vendor_email": None,
                "invoice_date": None,
                "due_date": None,
                "total_amount": None,
                "currency": None,
                "total_tax": None,
                "description": None,
                "line_items": [],
                "extraction_error": str(e)
            }
    
    def find_existing_invoice_file(self, output_dir: Path, invoice_number: str) -> Optional[Tuple[Path, Path]]:
        """
        Find existing JSON and PDF files for a given invoice number.
        
        Args:
            output_dir: Directory to search for files
            invoice_number: Invoice number to search for
            
        Returns:
            Tuple of (json_path, pdf_path) if found, None otherwise
        """
        # Sanitize invoice number for filename matching
        safe_invoice_num = "".join(c for c in invoice_number if c.isalnum() or c in "-_")
        
        # Search for JSON files that might contain this invoice number
        for json_file in output_dir.glob("*_invoice_*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get("invoice_number") == invoice_number:
                        # Found a match, return both JSON and PDF paths
                        pdf_file = json_file.with_suffix('.pdf')
                        if pdf_file.exists():
                            return (json_file, pdf_file)
            except (json.JSONDecodeError, Exception) as e:
                self._log(f"    Warning: Could not read {json_file.name}: {e}", "warning")
                continue
        
        return None
    
    def merge_invoice_data(self, existing_data: Dict, new_data: Dict) -> Dict:
        """
        Merge new invoice data into existing invoice data.
        
        Args:
            existing_data: Existing invoice data dictionary
            new_data: New invoice data to merge
            
        Returns:
            Merged invoice data dictionary
        """
        merged = existing_data.copy()
        
        # Always append line items
        if new_data.get("line_items"):
            if not merged.get("line_items"):
                merged["line_items"] = []
            merged["line_items"].extend(new_data["line_items"])
        
        # Update other fields only if existing field is null/None/empty and new has value
        for field in ["customer_name", "vendor_name", "vendor_address", "vendor_phone", "vendor_email", "invoice_date", "due_date", 
                      "total_amount", "currency", "total_tax", "description", "invoice_number"]:
            existing_value = merged.get(field)
            new_value = new_data.get(field)
            
            # Check if existing is null/None/empty
            if not existing_value and new_value:
                merged[field] = new_value
        
        return merged
    
    def merge_pdf_files(self, existing_pdf: str, new_pages_source: str, new_page_indices: List[int]):
        """
        Merge new pages into an existing PDF file.
        
        Args:
            existing_pdf: Path to existing PDF file to append to
            new_pages_source: Path to source PDF containing new pages
            new_page_indices: List of 0-indexed page numbers to append
        """
        try:
            # Read existing PDF
            existing_reader = PdfReader(existing_pdf, strict=False)
            
            # Read source PDF with new pages
            source_reader = PdfReader(new_pages_source, strict=False)
            
            # Create writer and add all existing pages first
            writer = PdfWriter()
            for page in existing_reader.pages:
                writer.add_page(page)
            
            # Add new pages
            for page_idx in new_page_indices:
                if page_idx < len(source_reader.pages):
                    writer.add_page(source_reader.pages[page_idx])
            
            # Write back to the existing file
            with open(existing_pdf, "wb") as output_file:
                writer.write(output_file)
            
            self._log(f"    Merged {len(new_page_indices)} new pages into existing PDF")
            
        except Exception as e:
            self._log(f"    Error merging PDF files: {e}", "error")
            raise
    
    def extract_pages_to_pdf(self, input_pdf: str, page_indices: List[int], output_path: str):
        """
        Extract specific pages from input PDF and save to new PDF.
        
        Args:
            input_pdf: Path to input PDF
            page_indices: List of 0-indexed page numbers to extract
            output_path: Path for output PDF
        """
        self._log(f"    DEBUG: Extracting pages {page_indices} from {Path(input_pdf).name}", "debug")
        reader = PdfReader(input_pdf, strict=False)
        writer = PdfWriter()
        
        pages_added = 0
        for page_idx in page_indices:
            if page_idx < len(reader.pages):
                writer.add_page(reader.pages[page_idx])
                pages_added += 1
        
        self._log(f"    DEBUG: Added {pages_added} pages to output PDF", "debug")
        
        with open(output_path, "wb") as output_file:
            writer.write(output_file)
        
        # Verify the output
        verify_reader = PdfReader(output_path, strict=False)
        self._log(f"    DEBUG: Output PDF has {len(verify_reader.pages)} pages", "debug")
    
    def process_pdf(self, pdf_path: str, attachment_id: int, output_dir: Optional[str] = None) -> List[str]:
        """
        Main processing function to split invoices from a PDF.
        
        Args:
            pdf_path: Path to input PDF file
            attachment_id: ID of the attachment being processed
            output_dir: Directory for output files (default: ./output)
            
        Returns:
            List of output file paths
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Set output directory with attachment_id subdirectory
        if output_dir:
            output_dir = Path(output_dir) / str(attachment_id)
        else:
            output_dir = Path("output") / str(attachment_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create errors directory
        errors_dir = output_dir / "errors"
        errors_dir.mkdir(exist_ok=True)
        
        self._log(f"Processing: {pdf_path.name}")
        self._log(f"Output directory: {output_dir}")
        
        # Update status to processing
        self.update_attachment_status(attachment_id, "processing")
        
        try:
            # Check for corruption
            is_valid, error = self.check_pdf_corruption(str(pdf_path))
            
            if not is_valid:
                self._log(f"⚠️  PDF appears corrupted: {error}", "warning")
                self._log("Attempting to repair...")
                
                success, result = self.repair_pdf(str(pdf_path))
                
                if success:
                    self._log(f"✓ PDF repaired successfully: {result}")
                    pdf_path = Path(result)
                else:
                    self._log(f"✗ Repair failed: {result}", "error")
                    error_file = errors_dir / pdf_path.name
                    shutil.copy2(pdf_path, error_file)
                    self._log(f"Copied to errors folder: {error_file}")
                    self.update_attachment_status(attachment_id, "failed")
                    return []
            
            # Convert PDF to images
            self._log("Converting PDF pages to images...")
            try:
                images = convert_from_path(str(pdf_path), dpi=200)
            except Exception as e:
                self._log(f"Error converting PDF to images: {e}", "error")
                error_file = errors_dir / pdf_path.name
                shutil.copy2(pdf_path, error_file)
                self._log(f"Copied to errors folder: {error_file}")
                self.update_attachment_status(attachment_id, "failed")
                return []
            
            total_pages = len(images)
            self._log(f"Total pages: {total_pages}")
            
            # Process pages with sliding window approach to find invoice boundaries
            self._log("\nAnalyzing and extracting invoices with GPT-4 Vision...")
            
            # Store all extracted invoice data in memory
            invoice_data_list = []  # List of dicts: {invoice_data, page_indices, pdf_path, json_path, s3_keys}
            session_invoices = {}  # invoice_number -> index in invoice_data_list
            
            # Use sliding window to find invoice boundaries
            i = 0
            while i < total_pages:
                # Try groups of increasing size starting from current page
                found_invoice = False
                best_group = None
                best_result = None
                
                # Try groups from 1 page up to remaining pages (max 10 pages per invoice)
                for group_size in range(1, min(11, total_pages - i + 1)):
                    page_group = list(range(i, i + group_size))
                    page_nums = [p + 1 for p in page_group]  # 1-indexed for display
                    group_images = [images[p] for p in page_group]
                    
                    self._log(f"  Analyzing pages {page_nums[0]}-{page_nums[-1]}...")
                    result = self.analyze_and_extract_invoice(group_images, page_nums, total_pages)
                    
                    # If this group forms a complete invoice, use it
                    if result.get("is_complete_invoice", False):
                        best_group = page_group
                        best_result = result
                        found_invoice = True
                        break
                    # If this is an invoice start with no continuation, treat as complete
                    elif result.get("is_invoice_start", False) and not result.get("has_continuation", False):
                        best_group = page_group
                        best_result = result
                        found_invoice = True
                        break
                    # Track the best invoice start we've seen (for max size fallback)
                    elif result.get("is_invoice_start", False):
                        if best_group is None or len(page_group) > len(best_group):
                            best_group = page_group
                            best_result = result
                
                # If we've tried all sizes and found an invoice start but not complete, use the largest group
                if not found_invoice and best_result and best_result.get("is_invoice_start", False):
                    found_invoice = True
                
                if found_invoice and best_result:
                    # Extract invoice data from result
                    invoice_data = {
                        "invoice_number": best_result.get("invoice_number"),
                        "customer_name": best_result.get("customer_name"),
                        "vendor_name": best_result.get("vendor_name"),
                        "vendor_address": best_result.get("vendor_address"),
                        "vendor_phone": best_result.get("vendor_phone"),
                        "vendor_email": best_result.get("vendor_email"),
                        "invoice_date": best_result.get("invoice_date"),
                        "due_date": best_result.get("due_date"),
                        "total_amount": best_result.get("total_amount"),
                        "currency": best_result.get("currency"),
                        "total_tax": best_result.get("total_tax"),
                        "description": best_result.get("description"),
                        "line_items": best_result.get("line_items", []),
                        "attachment_id": attachment_id
                    }
                    
                    invoice_num = invoice_data.get("invoice_number")
                    
                    # Check for duplicate in session
                    if invoice_num and invoice_num in session_invoices:
                        # Merge with existing
                        existing_idx = session_invoices[invoice_num]
                        existing = invoice_data_list[existing_idx]
                        
                        self._log(f"    Merging with existing invoice: {invoice_num}")
                        merged_data = self.merge_invoice_data(existing["invoice_data"], invoice_data)
                        existing["invoice_data"] = merged_data
                        existing["page_indices"].extend(best_group)
                    else:
                        # New invoice - store in memory
                        invoice_data_list.append({
                            "invoice_data": invoice_data,
                            "page_indices": best_group.copy(),
                            "pdf_path": None,  # Will be set later
                            "json_path": None,  # Will be set later
                            "s3_pdf_key": None,  # Will be set later
                            "s3_json_key": None  # Will be set later
                        })
                        
                        if invoice_num:
                            session_invoices[invoice_num] = len(invoice_data_list) - 1
                    
                    # Move to next page after this invoice
                    i += len(best_group)
                    
                    status = "COMPLETE" if best_result.get("is_complete_invoice") else "PARTIAL"
                    inv_num = invoice_num or "N/A"
                    self._log(f"  {status} INVOICE | Invoice#: {inv_num} | Pages: {page_nums} | Confidence: {best_result.get('confidence', 0):.2f}")
                else:
                    # No invoice found, move to next page
                    i += 1
            
            self._log(f"\nFound {len(invoice_data_list)} invoice(s)")
            
            # Now process all invoices: create PDFs, JSONs, upload to S3
            output_files = []
            base_name = pdf_path.stem
            batch_invoices = []  # For batch API call
            
            for idx, invoice_info in enumerate(invoice_data_list, start=1):
                invoice_data = invoice_info["invoice_data"]
                page_indices = invoice_info["page_indices"]
                invoice_num = invoice_data.get("invoice_number")
                
                # Determine filename
                if invoice_num:
                    safe_invoice_num = "".join(c for c in invoice_num if c.isalnum() or c in "-_")
                    output_filename = f"{base_name}_invoice_{safe_invoice_num}.pdf"
                else:
                    output_filename = f"{base_name}_invoice_{idx}.pdf"
                
                output_path = output_dir / output_filename
                json_output_path = output_dir / output_filename.replace(".pdf", ".json")
                
                self._log(f"\n  Invoice {idx}: Pages {[p+1 for p in page_indices]} -> {output_filename}")
                
                # Extract pages to PDF
                self.extract_pages_to_pdf(str(pdf_path), page_indices, str(output_path))
                output_files.append(str(output_path))
                
                # Save JSON data
                with open(json_output_path, 'w', encoding='utf-8') as json_file:
                    json.dump(invoice_data, json_file, indent=2, ensure_ascii=False)
                
                self._log(f"    Saved PDF: {output_filename}")
                self._log(f"    Saved JSON: {json_output_path.name}")
                
                # Upload to S3
                try:
                    pdf_s3_key = f"invoices/{attachment_id}/{output_filename}"
                    json_s3_key = f"invoices/{attachment_id}/{json_output_path.name}"
                    
                    self.upload_to_s3(str(output_path), pdf_s3_key, mime_type="application/pdf")
                    self.upload_to_s3(str(json_output_path), json_s3_key, mime_type="application/json")
                    
                    # Store for batch API call
                    batch_invoices.append({
                        "invoice_data": invoice_data,
                        "attachment_id": attachment_id,
                        "s3_pdf_key": pdf_s3_key,
                        "s3_json_key": json_s3_key
                    })
                    
                except Exception as e:
                    self._log(f"    Warning: S3 upload failed: {e}", "warning")
                
                # Display extracted info summary
                if invoice_data.get("invoice_number"):
                    self._log(f"    Invoice #: {invoice_data['invoice_number']}")
                if invoice_data.get("vendor_name"):
                    self._log(f"    Vendor: {invoice_data['vendor_name']}")
                if invoice_data.get("total_amount"):
                    currency = invoice_data.get("currency", "")
                    self._log(f"    Total: {currency} {invoice_data['total_amount']}")
                if invoice_data.get("line_items"):
                    self._log(f"    Line items: {len(invoice_data['line_items'])}")
            
            # Make single batch API call for all invoices
            if batch_invoices:
                self._log(f"\nCreating {len(batch_invoices)} invoice records in batch...")
                self.create_invoice_records_batch(batch_invoices)
            
            self._log(f"\n✓ Successfully split into {len(output_files)} invoice(s)")
            self._log(f"✓ Generated {len(output_files)} JSON data files")
            
            # Update status to success
            self.update_attachment_status(attachment_id, "success")
            
            return output_files
            
        except Exception as e:
            self._log(f"Unexpected error during processing: {str(e)}", "error")
            self.update_attachment_status(attachment_id, "failed")
            raise
