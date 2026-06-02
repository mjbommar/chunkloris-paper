FROM golang:1.23-bookworm AS build
WORKDIR /src
COPY go.mod main.go /src/
RUN go mod tidy && go build -o /out/server .

FROM debian:bookworm-slim
WORKDIR /app
COPY --from=build /out/server /app/server
EXPOSE 8000
ENTRYPOINT ["/app/server"]
