const express = require('express');
const app = express();

app.get('/health', (req, res) => {
  res.json({ ok: true });
});

app.post('/upload', (req, res) => {
  let n = 0;
  req.on('data', (chunk) => { n += chunk.length; });
  req.on('end', () => { res.json({ len: n }); });
});

app.listen(8000, '0.0.0.0', () => {
  console.log('express listening on 8000');
});
