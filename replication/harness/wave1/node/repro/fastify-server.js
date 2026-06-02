const fastify = require('fastify')({ logger: false });

fastify.get('/health', async (request, reply) => {
  return { ok: true };
});

// Use raw stream so we count true wire bytes (and avoid body parsing of arbitrary bytes)
fastify.addContentTypeParser('application/octet-stream', (request, payload, done) => {
  let n = 0;
  payload.on('data', (chunk) => { n += chunk.length; });
  payload.on('end', () => { done(null, { len: n }); });
  payload.on('error', (err) => { done(err); });
});

fastify.post('/upload', async (request, reply) => {
  return request.body;
});

fastify.listen({ port: 8000, host: '0.0.0.0' }, (err) => {
  if (err) { console.error(err); process.exit(1); }
  console.log('fastify listening on 8000');
});
