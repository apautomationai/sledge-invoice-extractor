"""
EC2 server handler for invoice extraction service.

This module implements a long-polling SQS worker that runs continuously on EC2 instances.
"""

import os
import json
import signal
import sys
import tempfile
import time
from typing import Dict, Any
from dotenv import load_dotenv

import boto3
from botocore.exceptions import ClientError

from invoice_extraction.core.processor import InvoiceSplitter
from invoice_extraction.utils.logger import setup_logger

load_dotenv()


class SQSWorker:
    """Long-polling SQS worker for invoice extraction."""
    
    def __init__(self):
        """Initialize the SQS worker."""
        self.logger = setup_logger("invoice-extraction")
        self.sqs_client = boto3.client('sqs')
        self.queue_url = os.getenv('SQS_QUEUE_URL')
        self.running = False
        
        if not self.queue_url:
            raise ValueError("SQS_QUEUE_URL environment variable not found")
        
        self.logger.info(f"Initialized SQS worker for queue: {self.queue_url}")
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
    
    def process_message(self, message: Dict[str, Any]) -> bool:
        """
        Process a single SQS message.
        
        Args:
            message: SQS message dictionary
            
        Returns:
            True if message was processed successfully, False otherwise
        """
        message_id = message.get('MessageId')
        receipt_handle = message.get('ReceiptHandle')
        
        try:
            # Parse message body
            message_body = json.loads(message['Body'])
            attachment_id = message_body.get('attachment_id')
            
            if not attachment_id:
                self.logger.error(f"Message {message_id}: No attachment_id found")
                return False
            
            self.logger.info(f"Processing attachment ID: {attachment_id}")
            
            # Initialize processor
            processor = InvoiceSplitter(logger=self.logger)
            
            # Fetch attachment metadata
            attachment_data = processor.fetch_attachment_metadata(attachment_id)
            file_url = attachment_data.get("fileUrl")
            filename = attachment_data.get("filename", f"attachment_{attachment_id}.pdf")
            
            if not file_url:
                raise ValueError("File URL not found in attachment metadata")
            
            self.logger.info(f"Processing: {filename}")
            
            # Download PDF to temporary location
            temp_pdf_path = tempfile.mktemp(suffix=".pdf", prefix=f"attachment_{attachment_id}_")
            processor.download_pdf_from_url(file_url, temp_pdf_path)
            
            try:
                # Process the PDF
                output_files = processor.process_pdf(temp_pdf_path, attachment_id)
                
                if output_files:
                    self.logger.info(f"✓ Successfully processed attachment {attachment_id}")
                    self.logger.info(f"Generated {len(output_files)} output files")
                    return True
                else:
                    self.logger.error(f"✗ No invoices extracted for attachment {attachment_id}")
                    return False
                    
            finally:
                # Clean up temporary file
                try:
                    os.remove(temp_pdf_path)
                    self.logger.debug(f"Cleaned up temporary file: {temp_pdf_path}")
                except Exception as e:
                    self.logger.warning(f"Warning: Failed to clean up temporary file: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error processing message {message_id}: {str(e)}", exc_info=True)
            return False
    
    def delete_message(self, message: Dict[str, Any]):
        """Delete a processed message from the SQS queue."""
        try:
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=message['ReceiptHandle']
            )
            self.logger.debug(f"Deleted message {message.get('MessageId')}")
        except ClientError as e:
            self.logger.error(f"Failed to delete message: {e}")
    
    def run(self):
        """Main worker loop with long-polling."""
        self.logger.info("Starting SQS worker...")
        self.running = True
        
        while self.running:
            try:
                # Long-poll for messages (20 second wait time)
                response = self.sqs_client.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20,
                    AttributeNames=['All'],
                    MessageAttributeNames=['All']
                )
                
                messages = response.get('Messages', [])
                
                if not messages:
                    # No messages received, continue polling
                    continue
                
                for message in messages:
                    if not self.running:
                        break
                    
                    message_id = message.get('MessageId')
                    self.logger.info(f"Received message: {message_id}")
                    
                    # Process the message
                    success = self.process_message(message)
                    
                    if success:
                        # Delete the message from the queue
                        self.delete_message(message)
                        self.logger.info(f"Successfully processed and deleted message: {message_id}")
                    else:
                        # Leave message in queue for retry (DLQ will handle failures)
                        self.logger.warning(f"Failed to process message: {message_id}")
                
            except ClientError as e:
                self.logger.error(f"SQS client error: {e}")
                time.sleep(5)  # Wait before retrying
            except Exception as e:
                self.logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)
                time.sleep(5)  # Wait before retrying
        
        self.logger.info("SQS worker stopped")


def run_sqs_worker():
    """Entry point for running the SQS worker."""
    try:
        worker = SQSWorker()
        worker.run()
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt, shutting down...")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_sqs_worker()
