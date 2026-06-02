using Microsoft.AspNetCore.Server.Kestrel.Core;

var builder = WebApplication.CreateSlimBuilder(args);

builder.WebHost.ConfigureKestrel(opts =>
{
    opts.Limits.MaxRequestBodySize = null;
    opts.ListenAnyIP(8000, listen =>
    {
        // Force HTTP/2 over plaintext (h2c). No prior-knowledge fallback.
        listen.Protocols = HttpProtocols.Http2;
    });
});

var app = builder.Build();

app.MapGet("/health", () => Results.Json(new { ok = true }));

app.MapPost("/upload", async (HttpRequest req) =>
{
    var buf = new byte[64 * 1024];
    long total = 0;
    while (true)
    {
        var n = await req.Body.ReadAsync(buf);
        if (n == 0) break;
        total += n;
    }
    return Results.Json(new { len = total });
});

app.Run();
