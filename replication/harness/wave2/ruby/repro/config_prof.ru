# Rack app with HTTP-triggered stackprof.
# GET /prof/start, GET /prof/stop, GET /prof/dump.
require 'stackprof'
require 'json'

PROF_OUT = '/tmp/stackprof.dump'
PROF_STATE = { running: false }
PROF_MUTEX = Mutex.new

app = lambda do |env|
  m = env['REQUEST_METHOD']
  p = env['PATH_INFO']
  if m == 'GET' && p == '/health'
    return [200, {'content-type' => 'application/json'}, ['{"ok":true}']]
  end
  if m == 'GET' && p == '/prof/start'
    PROF_MUTEX.synchronize do
      unless PROF_STATE[:running]
        StackProf.start(mode: :cpu, interval: 1000, raw: false)
        PROF_STATE[:running] = true
      end
    end
    return [200, {'content-type' => 'text/plain'}, ["started pid=#{Process.pid}"]]
  end
  if m == 'GET' && p == '/prof/stop'
    PROF_MUTEX.synchronize do
      if PROF_STATE[:running]
        StackProf.stop
        File.binwrite(PROF_OUT, Marshal.dump(StackProf.results))
        PROF_STATE[:running] = false
      end
    end
    return [200, {'content-type' => 'text/plain'}, ["stopped pid=#{Process.pid}"]]
  end
  if m == 'POST' && p == '/upload'
    input = env['rack.input']
    n = 0
    if input
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
