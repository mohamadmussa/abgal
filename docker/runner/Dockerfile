# The container backend's runner image. It carries only what the GitHub
# Actions runner needs to run, not the runner itself: abgal bind mounts the
# tarball it already fetched through runner-versions.conf onto /runner, so
# the same version policy governs both backends instead of whatever this
# image happened to ship with.
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        jq \
        zstd \
        sudo \
        libicu70 \
        liblttng-ust1 \
        libkrb5-3 \
        libssl3 \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /runner
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
