FROM rust:1.85-slim AS build
WORKDIR /src
COPY Cargo.toml /src/
COPY src /src/src
RUN cargo build --release

FROM debian:bookworm-slim
WORKDIR /app
COPY --from=build /src/target/release/rust-hyper-h2 /app/server
EXPOSE 8000
ENTRYPOINT ["/app/server"]
