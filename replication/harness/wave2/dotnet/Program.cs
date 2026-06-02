using System.Text.Json.Serialization;

var builder = WebApplication.CreateSlimBuilder(args);
builder.Logging.ClearProviders();
builder.Services.ConfigureHttpJsonOptions(o => o.SerializerOptions.TypeInfoResolverChain.Insert(0, AppJsonContext.Default));

builder.WebHost.ConfigureKestrel(opts =>
{
    opts.ListenAnyIP(8000);
    // Disable any body-size limit to make sure we measure the parser, not a guard.
    opts.Limits.MaxRequestBodySize = null;
});

var app = builder.Build();

app.MapGet("/health", () => Results.Json(new HealthResp(true), AppJsonContext.Default.HealthResp));

app.MapPost("/upload", async (HttpRequest req) =>
{
    long len = 0;
    var buf = new byte[64 * 1024];
    var s = req.Body;
    while (true)
    {
        int n = await s.ReadAsync(buf.AsMemory());
        if (n == 0) break;
        len += n;
    }
    return Results.Json(new LenResp(len), AppJsonContext.Default.LenResp);
});

app.Run();

public record HealthResp(bool ok);
public record LenResp(long len);

[JsonSerializable(typeof(HealthResp))]
[JsonSerializable(typeof(LenResp))]
internal partial class AppJsonContext : JsonSerializerContext { }
