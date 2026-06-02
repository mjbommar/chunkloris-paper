// tokio-tungstenite echo-count server.
//
// We don't use hyper for the upgrade: we accept directly on a TcpListener,
// peek the first request line to dispatch /health vs /ws, and hand the
// /ws path to tungstenite's accept_async.
use futures_util::{SinkExt, StreamExt};
use std::net::SocketAddr;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};
use tokio_tungstenite::accept_async;
use tokio_tungstenite::tungstenite::protocol::Message;

async fn handle_health(mut s: TcpStream) {
    let body = b"{\"ok\":true}";
    let resp = format!(
        "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        body.len()
    );
    let _ = s.write_all(resp.as_bytes()).await;
    let _ = s.write_all(body).await;
}

async fn handle_ws(stream: TcpStream, n_expected: usize) {
    let ws_stream = match accept_async(stream).await {
        Ok(s) => s,
        Err(_) => return,
    };
    let (mut write, mut read) = ws_stream.split();
    let mut received: usize = 0;
    while let Some(msg) = read.next().await {
        match msg {
            Ok(Message::Text(_)) | Ok(Message::Binary(_)) => {
                received += 1;
                if received >= n_expected { break; }
            }
            Ok(Message::Ping(_)) | Ok(Message::Pong(_)) | Ok(Message::Frame(_)) => {}
            Ok(Message::Close(_)) => break,
            Err(_) => break,
        }
    }
    let body = format!("{{\"frames\":{}}}", received);
    let _ = write.send(Message::Text(body.into())).await;
    let _ = write.close().await;
}

async fn dispatch(mut s: TcpStream) {
    // Peek the request line to decide.
    let mut buf = [0u8; 4096];
    let n = match s.peek(&mut buf).await {
        Ok(n) if n > 0 => n,
        _ => return,
    };
    // Look at first line.
    let first = match std::str::from_utf8(&buf[..n.min(256)]) { Ok(s) => s, Err(_) => return };
    if first.starts_with("GET /health") {
        // consume the request
        let mut tmp = [0u8; 4096];
        let _ = s.read(&mut tmp).await;
        handle_health(s).await;
        return;
    }
    // Parse the n=X query param if present in /ws?n=NUMBER.
    let mut n_expected: usize = 50000;
    if let Some(line_end) = first.find("\r\n") {
        let req_line = &first[..line_end];
        // GET /ws?n=NN HTTP/1.1
        if let Some(qm) = req_line.find('?') {
            let after = &req_line[qm + 1..];
            if let Some(sp) = after.find(' ') {
                let q = &after[..sp];
                for kv in q.split('&') {
                    if let Some((k, v)) = kv.split_once('=') {
                        if k == "n" {
                            if let Ok(x) = v.parse::<usize>() { n_expected = x; }
                        }
                    }
                }
            }
        }
    }
    handle_ws(s, n_expected).await;
}

#[tokio::main(flavor = "multi_thread", worker_threads = 2)]
async fn main() {
    let addr: SocketAddr = "0.0.0.0:8000".parse().unwrap();
    let listener = TcpListener::bind(addr).await.unwrap();
    eprintln!("rust ws server on :8000");
    loop {
        let (stream, _) = match listener.accept().await { Ok(x) => x, Err(_) => continue };
        tokio::spawn(dispatch(stream));
    }
}
