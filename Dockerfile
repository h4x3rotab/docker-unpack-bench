FROM ubuntu:22.04

# Install all heavy dependencies during build time
RUN apt-get update && apt-get install -y \
    containerd \
    runc \
    ca-certificates \
    docker.io \
    python3 \
    python3-pip \
    time \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Pre-generate containerd config
RUN mkdir -p /etc/containerd && \
    containerd config default > /etc/containerd/config.toml

# Set working directory
WORKDIR /workspace

# Copy scripts
COPY scripts/ /workspace/scripts/
RUN chmod +x /workspace/scripts/*.sh /workspace/scripts/*.py

# Default command
CMD ["/workspace/scripts/entrypoint.sh"]