FROM golang:1.23-bookworm AS build
WORKDIR /src
COPY go.mod /src/go.mod
COPY server.go /src/server.go
RUN go mod tidy && CGO_ENABLED=0 go build -trimpath -ldflags '-s -w' -o /out/server ./...

FROM gcr.io/distroless/static-debian12
COPY --from=build /out/server /server
EXPOSE 8000
ENTRYPOINT ["/server"]
