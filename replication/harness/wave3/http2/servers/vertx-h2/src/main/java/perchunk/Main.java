package perchunk;

import io.vertx.core.Vertx;
import io.vertx.core.http.HttpServer;
import io.vertx.core.http.HttpServerOptions;
import io.vertx.core.http.HttpVersion;

public class Main {
  public static void main(String[] args) {
    Vertx vertx = Vertx.vertx();
    HttpServerOptions opts = new HttpServerOptions()
        .setHost("0.0.0.0")
        .setPort(8000)
        // h2c: HTTP/2 cleartext, no ALPN
        .setUseAlpn(false)
        .addEnabledSecureTransportProtocol("TLSv1.3")
        .setInitialSettings(new io.vertx.core.http.Http2Settings()
            .setMaxConcurrentStreams(1000))
        // accept HTTP/1 upgrade and prior-knowledge h2c
        .setHttp2ClearTextEnabled(true);

    HttpServer server = vertx.createHttpServer(opts);
    server.requestHandler(req -> {
      String path = req.path();
      if ("/health".equals(path) && req.method().name().equals("GET")) {
        req.response()
            .putHeader("content-type", "application/json")
            .end("{\"ok\":true}");
        return;
      }
      if ("/upload".equals(path) && req.method().name().equals("POST")) {
        long[] total = new long[]{0L};
        req.handler(buf -> total[0] += buf.length());
        req.endHandler(v -> {
          String body = "{\"len\":" + total[0] + "}";
          req.response()
              .putHeader("content-type", "application/json")
              .putHeader("content-length", Integer.toString(body.length()))
              .end(body);
        });
        req.exceptionHandler(t -> {
          if (!req.response().ended()) req.response().setStatusCode(500).end();
        });
        return;
      }
      req.response().setStatusCode(404).end();
    });
    server.listen(res -> {
      if (res.succeeded()) {
        System.out.println("vertx h2c listening on 0.0.0.0:8000");
      } else {
        System.err.println("listen failed: " + res.cause());
        System.exit(1);
      }
    });
  }
}
