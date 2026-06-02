// Node.js native http2 server, h2c (plaintext). createServer = h2c.
const http2 = require('node:http2');

const server = http2.createServer({
  // No body-size limits.
  maxSessionMemory: 1024,    // MiB; allow huge accumulated state
});

server.on('stream', (stream, headers) => {
  const method = headers[':method'];
  const path = headers[':path'];
  if (path === '/health' && method === 'GET') {
    stream.respond({':status': 200, 'content-type': 'application/json'});
    stream.end('{"ok":true}');
    return;
  }
  if (path === '/upload' && method === 'POST') {
    let total = 0;
    stream.on('data', (chunk) => { total += chunk.length; });
    stream.on('end', () => {
      const body = JSON.stringify({len: total});
      stream.respond({
        ':status': 200,
        'content-type': 'application/json',
        'content-length': Buffer.byteLength(body),
      });
      stream.end(body);
    });
    stream.on('error', (err) => {
      try { stream.close(); } catch (e) {}
    });
    return;
  }
  stream.respond({':status': 404});
  stream.end();
});

server.on('sessionError', (err) => { console.error('sessionError', err.code); });
server.on('error', (err) => { console.error('serverError', err); });

server.listen(8000, '0.0.0.0', () => {
  console.log('node http2 (h2c) listening on 0.0.0.0:8000');
});
