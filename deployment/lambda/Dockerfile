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
