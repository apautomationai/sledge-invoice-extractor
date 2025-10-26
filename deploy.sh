#!/bin/bash

# AWS Lambda Container Deployment Script for PRODUCTION
# This script deploys the latest container image from ECR to a Lambda function
# IMPORTANT: This deployment must be manually approved/triggered by system administrator

set -e

echo "=========================================="
echo "Starting PRODUCTION Deployment"
echo "Environment: PRODUCTION"
echo "Lambda Function: $LAMBDA_FUNCTION_NAME"
echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_DEFAULT_REGION"
echo "ECR Repository: $ECR_REPOSITORY"
echo "=========================================="

# Build the ECR image URI using 'latest' tag
REPOSITORY_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/$ECR_REPOSITORY"
IMAGE_URI="$REPOSITORY_URI:latest"

echo "Image URI: $IMAGE_URI"
echo ""
echo "WARNING: Deploying to PRODUCTION Lambda function!"
echo "This deployment affects PRODUCTION. Proceeding in 5 seconds..."
sleep 5

# Update Lambda function with the latest container image
echo "Updating Lambda function with new container image..."
aws lambda update-function-code \
  --function-name "$LAMBDA_FUNCTION_NAME" \
  --image-uri "$IMAGE_URI"

# Wait for Lambda function update to complete
echo "Waiting for Lambda function update to complete..."
aws lambda wait function-updated \
  --function-name "$LAMBDA_FUNCTION_NAME"

# Verify deployment
echo "Verifying deployment..."
CODE_SHA=$(aws lambda get-function \
  --function-name "$LAMBDA_FUNCTION_NAME" \
  --query 'Configuration.CodeSha256' \
  --output text)

echo "Code Sha256: $CODE_SHA"
echo "=========================================="
echo "PRODUCTION Deployment completed successfully!"
echo "Completed at: $(date)"
echo "=========================================="

