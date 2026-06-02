# Minimal Rack app: drain body, return {"len": N}.
# No middleware, no logging.

app = lambda do |env|
  if env['REQUEST_METHOD'] == 'GET' && env['PATH_INFO'] == '/health'
    return [200, {'content-type' => 'application/json'}, ['{"ok":true}']]
  end
  if env['REQUEST_METHOD'] == 'POST' && env['PATH_INFO'] == '/upload'
    input = env['rack.input']
    n = 0
    if input
      # Drain in 64KB reads. Most Ruby servers buffer the whole body
      # before invoking the handler (rack.input is a fully-rewindable
      # IO-like by the time we get here on Puma/Unicorn). Falcon may
      # stream.
      buf = String.new
      while (chunk = input.read(65536, buf))
        n += chunk.bytesize
      end
    end
    return [200, {'content-type' => 'application/json'}, [%Q({"len":#{n}})]]
  end
  [404, {'content-type' => 'text/plain'}, ['not found']]
end

run app
