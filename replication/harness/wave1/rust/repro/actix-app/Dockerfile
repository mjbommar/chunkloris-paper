FROM rust:1.89-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends pkg-config && rm -rf /var/lib/apt/lists/*
COPY Cargo.toml /build/
RUN mkdir -p src && echo "fn main(){}" > src/main.rs && cargo build --release && rm -rf src
COPY src /build/src
RUN touch src/main.rs && cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    linux-perf procps ca-certificates \
  && rm -rf /var/lib/apt/lists/* \
  && ln -sf /usr/bin/perf_* /usr/local/bin/perf 2>/dev/null || true
COPY --from=builder /build/target/release/actix-srv /usr/local/bin/actix-srv
EXPOSE 8000
CMD ["/usr/local/bin/actix-srv"]
