// Pure Node http.Server baseline: no framework
const http = require('http');

const server = http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end('{"ok":true}');
    return;
  }
  if (req.url === '/upload' && req.method === 'POST') {
    let n = 0;
    req.on('data', (chunk) => { n += chunk.length; });
    req.on('end', () => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ len: n }));
    });
    return;
  }
  res.writeHead(404); res.end();
});

server.listen(8000, '0.0.0.0', () => console.log('http listening on 8000'));
