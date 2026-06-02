package survey;

import io.vertx.core.Vertx;
import io.vertx.core.http.HttpServerOptions;
import io.vertx.ext.web.Router;

public class App {
    public static void main(String[] args) {
        Vertx vertx = Vertx.vertx();
        Router router = Router.router(vertx);

        router.get("/health").handler(ctx ->
            ctx.response()
                .putHeader("content-type", "application/json")
                .end("{\"ok\":true}"));

        router.post("/upload").handler(ctx -> {
            // Count bytes as they stream in (no aggregation buffer growth).
            long[] total = {0};
            ctx.request().handler(buf -> total[0] += buf.length());
            ctx.request().endHandler(v ->
                ctx.response()
                    .putHeader("content-type", "application/json")
                    .end("{\"len\":" + total[0] + "}"));
            ctx.request().exceptionHandler(t ->
                ctx.response().setStatusCode(500).end("err"));
        });

        HttpServerOptions opts = new HttpServerOptions()
            .setHost("0.0.0.0")
            .setPort(8000);

        vertx.createHttpServer(opts)
            .requestHandler(router)
            .listen(res -> {
                if (res.succeeded()) {
                    System.out.println("vertx listening on 0.0.0.0:8000");
                } else {
                    res.cause().printStackTrace();
                    System.exit(1);
                }
            });
    }
}
