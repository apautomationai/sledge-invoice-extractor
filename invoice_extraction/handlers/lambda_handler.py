"""
AWS Lambda handler for invoice extraction service.

This module handles SQS events and processes PDF invoices in a serverless environment.
"""

import json
import tempfile
import os
from typing import Dict, List, Any

from ..core.processor import InvoiceSplitter
from ..utils.logger import setup_logger


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for processing SQS messages containing attachment IDs.
    
    Args:
        event: SQS event containing records with attachment IDs
        context: Lambda context object
        
    Returns:
        Dict containing processing results and status
    """
    # Set up logger (file logging disabled for Lambda)
    logger = setup_logger("invoice-extraction", enable_file_logging=False)
    
    logger.info(f"Received event with {len(event.get('Records', []))} records")
    
    processed_attachments = []
    failed_attachments = []
    
    try:
        # Process each SQS record
        for record in event.get('Records', []):
            try:
                # Parse the message body
                message_body = json.loads(record['body'])
                attachment_id = message_body.get('attachment_id')
                
                if not attachment_id:
                    logger.error("No attachment_id found in message body")
                    failed_attachments.append({
                        'message_id': record.get('messageId'),
                        'error': 'No attachment_id in message body'
                    })
                    continue
                
                logger.info(f"Processing attachment ID: {attachment_id}")
                
                # Initialize processor
                processor = InvoiceSplitter(logger=logger)
                
                # Fetch attachment metadata
                attachment_data = processor.fetch_attachment_metadata(attachment_id)
                file_url = attachment_data.get("fileUrl")
                filename = attachment_data.get("filename", f"attachment_{attachment_id}.pdf")
                
                if not file_url:
                    raise ValueError("File URL not found in attachment metadata")
                
                logger.info(f"Processing: {filename}")
                
                # Download PDF to Lambda's /tmp directory
                temp_pdf_path = os.path.join('/tmp', f"attachment_{attachment_id}.pdf")
                processor.download_pdf_from_url(file_url, temp_pdf_path)
                
                # Process the PDF (output to /tmp as well)
                output_files = processor.process_pdf(temp_pdf_path, attachment_id, '/tmp/output')
                
                # Clean up temp files
                try:
                    os.remove(temp_pdf_path)
                    logger.info(f"Cleaned up temporary file: {temp_pdf_path}")
                except Exception as e:
                    logger.warning(f"Warning: Failed to clean up temporary file: {e}")
                
                if output_files:
                    processed_attachments.append({
                        'attachment_id': attachment_id,
                        'filename': filename,
                        'output_files': len(output_files)
                    })
                    logger.info(f"✓ Successfully processed attachment {attachment_id}")
                else:
                    failed_attachments.append({
                        'attachment_id': attachment_id,
                        'error': 'No invoices were extracted (file may be corrupted)'
                    })
                    logger.error(f"✗ No invoices extracted for attachment {attachment_id}")
                    
            except Exception as e:
                logger.error(f"Error processing record: {str(e)}", exc_info=True)
                failed_attachments.append({
                    'message_id': record.get('messageId'),
                    'attachment_id': message_body.get('attachment_id') if 'message_body' in locals() else None,
                    'error': str(e)
                })
        
        # Return processing results
        result = {
            'statusCode': 200,
            'processed_count': len(processed_attachments),
            'failed_count': len(failed_attachments),
            'processed_attachments': processed_attachments,
            'failed_attachments': failed_attachments
        }
        
        if failed_attachments:
            logger.warning(f"Processing completed with {len(failed_attachments)} failures")
        else:
            logger.info("All attachments processed successfully")
            
        return result
        
    except Exception as e:
        logger.error(f"Unexpected error in Lambda handler: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'error': str(e),
            'processed_count': len(processed_attachments),
            'failed_count': len(failed_attachments) + 1,
            'processed_attachments': processed_attachments,
            'failed_attachments': failed_attachments
        }
