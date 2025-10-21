# Define custom function directory
ARG FUNCTION_DIR="/function"

FROM python:3.13-slim AS base
FROM base AS builder

# Include global arg in this stage of the build
ARG FUNCTION_DIR


# Make sure the function directory exists and set it as the working directory
RUN mkdir -p ${FUNCTION_DIR}
WORKDIR ${FUNCTION_DIR}

# Install the function's dependencies
RUN apt update -y 
RUN apt install -y poppler-utils
RUN apt clean all

# Create non-root user for security
# RUN addgroup --system --gid 1001 appgroup
# RUN adduser --system --uid 1001 --ingroup appgroup appuser

# USER appuser

# install uv
RUN apt install -y --no-install-recommends curl ca-certificates
# Download the latest installer
ADD https://astral.sh/uv/install.sh /uv-installer.sh
# Run the installer then remove it
RUN sh /uv-installer.sh && rm /uv-installer.sh
# Ensure the installed binary is on the `PATH`
ENV PATH="/root/.local/bin/:$PATH"

# install aws lambda runtime interface client
RUN uv pip install --system --no-cache-dir awslambdaric

# install the function's dependencies
COPY pyproject.toml ${FUNCTION_DIR}
RUN uv pip install --system --no-cache-dir -e ${FUNCTION_DIR}

# COPY . ${FUNCTION_DIR}

# # Install the function's dependencies
# RUN uv pip install \
#     --target ${FUNCTION_DIR} \
#         awslambdaric




# Copy in the built dependencies
COPY . ${FUNCTION_DIR}

# Set runtime interface client as default command for the container runtime
ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]
# Pass the name of the function handler as an argument to the runtime
CMD [ "lambda_handler.handler" ]