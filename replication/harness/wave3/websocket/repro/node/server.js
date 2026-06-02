// Tiny WS echo-count server using the 'ws' library (the de facto
// Node.js WebSocket impl, also used by socket.io).
const http = require('http');
const { WebSocketServer } = require('ws');

const server = http.createServer((req, res) => {
    if (req.url === '/health') {
        res.writeHead(200, {'Content-Type': 'application/json'});
        res.end('{"ok":true}');
        return;
    }
    res.writeHead(404); res.end();
});

const wss = new WebSocketServer({ server, perMessageDeflate: false });
wss.on('connection', (ws, req) => {
    const url = new URL(req.url, 'http://localhost');
    const nExpected = parseInt(url.searchParams.get('n') || '50000', 10);
    let received = 0;
    ws.on('message', (data, isBinary) => {
        received += 1;
        if (received === nExpected) {
            ws.send(JSON.stringify({frames: received}));
            ws.close();
        }
    });
    ws.on('error', () => {});
});

server.listen(8000, '0.0.0.0', () => {
    console.error('node ws server on :8000');
});
