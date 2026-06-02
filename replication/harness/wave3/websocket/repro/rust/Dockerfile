FROM rust:1.83-bookworm AS build
WORKDIR /src
COPY Cargo.toml /src/Cargo.toml
COPY src /src/src
RUN cargo build --release --locked || cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/target/release/ws-server /usr/local/bin/ws-server
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/ws-server"]
