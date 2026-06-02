use actix_web::{get, post, web, App, HttpResponse, HttpServer, Responder};

#[get("/health")]
async fn health() -> impl Responder {
    HttpResponse::Ok()
        .content_type("application/json")
        .body(r#"{"ok":true}"#)
}

#[post("/upload")]
async fn upload(body: web::Bytes) -> impl Responder {
    HttpResponse::Ok()
        .content_type("application/json")
        .body(format!(r#"{{"len":{}}}"#, body.len()))
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    eprintln!("actix listening on 0.0.0.0:8000");
    HttpServer::new(|| {
        App::new()
            .app_data(web::PayloadConfig::new(usize::MAX))
            .service(health)
            .service(upload)
    })
    .workers(1)
    .bind(("0.0.0.0", 8000))?
    .run()
    .await
}
