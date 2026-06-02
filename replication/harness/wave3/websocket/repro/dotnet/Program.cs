using System.Net.WebSockets;
using System.Text;
using System.Text.Json;

var builder = WebApplication.CreateSlimBuilder(args);
builder.Logging.ClearProviders();
builder.WebHost.ConfigureKestrel(o => o.ListenAnyIP(8000));

var app = builder.Build();
app.UseWebSockets();

app.MapGet("/health", () => Results.Json(new { ok = true }));

app.Map("/ws", async (HttpContext ctx) =>
{
    if (!ctx.WebSockets.IsWebSocketRequest)
    {
        ctx.Response.StatusCode = 400;
        return;
    }
    int nExpected = 50000;
    if (ctx.Request.Query.TryGetValue("n", out var v) && int.TryParse(v, out var nn)) nExpected = nn;

    using var ws = await ctx.WebSockets.AcceptWebSocketAsync();
    var buf = new byte[8192];
    int received = 0;
    while (received < nExpected)
    {
        var r = await ws.ReceiveAsync(new ArraySegment<byte>(buf), CancellationToken.None);
        if (r.MessageType == WebSocketMessageType.Close) break;
        if (r.EndOfMessage) received++;
        // If EndOfMessage is false the client fragmented; we still count
        // one application-level frame per assembled message (this matches
        // every other server in the survey's text-frame semantics).
    }
    var summary = Encoding.UTF8.GetBytes($"{{\"frames\":{received}}}");
    await ws.SendAsync(new ArraySegment<byte>(summary), WebSocketMessageType.Text, true, CancellationToken.None);
    try { await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "done", CancellationToken.None); }
    catch { }
});

app.Run();
