FROM ubuntu:24.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates lsb-release wget \
    && wget https://apache.jfrog.io/artifactory/arrow/ubuntu/apache-arrow-apt-source-latest-noble.deb \
    && apt-get install -y -V ./apache-arrow-apt-source-latest-noble.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential cmake g++-13 \
    libarrow-dev libarrow-acero-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY worker/CMakeLists.txt worker/
COPY worker/include/ worker/include/
COPY worker/src/ worker/src/
COPY worker/strategies/ worker/strategies/

RUN cmake -S worker -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build -j"$(nproc)"

FROM ubuntu:24.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates lsb-release wget \
    && wget https://apache.jfrog.io/artifactory/arrow/ubuntu/apache-arrow-apt-source-latest-noble.deb \
    && apt-get install -y -V ./apache-arrow-apt-source-latest-noble.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    g++-13 libarrow-dev libarrow-acero-dev \
    && rm -rf /var/lib/apt/lists/* \
    && (userdel -r ubuntu || true) \
    && useradd -m -u 1000 sandbox

COPY --from=builder /build/build/swarm_worker /usr/local/bin/swarm_worker
COPY --from=builder /build/build/swarm_benchmark /usr/local/bin/swarm_benchmark
COPY worker/include/ /app/include/
COPY worker/scripts/compile_strategy.sh /app/scripts/compile_strategy.sh
RUN chmod +x /app/scripts/compile_strategy.sh

USER sandbox
WORKDIR /sandbox
ENTRYPOINT ["/usr/local/bin/swarm_worker"]
