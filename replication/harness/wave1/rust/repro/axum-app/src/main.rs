use axum::{
    body::Bytes,
    extract::Request,
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Router,
};
use http_body_util::BodyExt;

async fn health() -> impl IntoResponse {
    (StatusCode::OK, [("content-type", "application/json")], r#"{"ok":true}"#)
}

async fn upload(req: Request) -> impl IntoResponse {
    // Drain the full body
    let collected = req.into_body().collect().await;
    match collected {
        Ok(c) => {
            let bytes: Bytes = c.to_bytes();
            let body = format!(r#"{{"len":{}}}"#, bytes.len());
            (StatusCode::OK, [("content-type", "application/json")], body).into_response()
        }
        Err(e) => (StatusCode::BAD_REQUEST, format!("err: {e}")).into_response(),
    }
}

#[tokio::main(flavor = "current_thread")]
async fn main() {
    let app = Router::new()
        .route("/health", get(health))
        .route("/upload", post(upload));
    let listener = tokio::net::TcpListener::bind("0.0.0.0:8000").await.unwrap();
    eprintln!("axum listening on 0.0.0.0:8000");
    axum::serve(listener, app).await.unwrap();
}
