use std::convert::Infallible;
use std::net::SocketAddr;

use bytes::Bytes;
use http_body_util::{BodyExt, Full};
use hyper::body::Incoming;
use hyper::service::service_fn;
use hyper::{Method, Request, Response, StatusCode};
use hyper_util::rt::{TokioExecutor, TokioIo};
use hyper_util::server::conn::auto::Builder as AutoBuilder;
use tokio::net::TcpListener;

async fn handle(req: Request<Incoming>) -> Result<Response<Full<Bytes>>, Infallible> {
    let path = req.uri().path().to_string();
    let method = req.method().clone();
    if path == "/health" && method == Method::GET {
        let body = Bytes::from_static(b"{\"ok\":true}");
        return Ok(Response::builder()
            .status(StatusCode::OK)
            .header("content-type", "application/json")
            .body(Full::new(body)).unwrap());
    }
    if path == "/upload" && method == Method::POST {
        // Drain body, count bytes.
        let mut total: u64 = 0;
        let mut body = req.into_body();
        while let Some(frame) = body.frame().await {
            match frame {
                Ok(f) => {
                    if let Some(data) = f.data_ref() {
                        total += data.len() as u64;
                    }
                }
                Err(_) => break,
            }
        }
        let s = format!("{{\"len\":{}}}", total);
        let len = s.len();
        return Ok(Response::builder()
            .status(StatusCode::OK)
            .header("content-type", "application/json")
            .header("content-length", len.to_string())
            .body(Full::new(Bytes::from(s))).unwrap());
    }
    Ok(Response::builder()
        .status(StatusCode::NOT_FOUND)
        .body(Full::new(Bytes::new())).unwrap())
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr: SocketAddr = ([0, 0, 0, 0], 8000).into();
    let listener = TcpListener::bind(addr).await?;
    println!("hyper h2 listening on {}", addr);
    loop {
        let (stream, _) = listener.accept().await?;
        let io = TokioIo::new(stream);
        tokio::spawn(async move {
            let mut builder = AutoBuilder::new(TokioExecutor::new());
            // Force HTTP/2 only path; we'll let auto-builder negotiate.
            builder.http2().max_concurrent_streams(1000u32);
            let _ = builder
                .serve_connection(io, service_fn(handle))
                .await;
        });
    }
}
