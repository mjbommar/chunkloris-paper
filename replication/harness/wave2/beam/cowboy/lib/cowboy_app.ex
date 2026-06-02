defmodule CowboyApp do
  def start do
    dispatch = :cowboy_router.compile([
      {:_,
        [
          {"/health", CowboyApp.HealthHandler, []},
          {"/upload", CowboyApp.UploadHandler, []},
          {"/profile_upload", CowboyApp.ProfileHandler, []}
        ]}
    ])

    {:ok, _} =
      :cowboy.start_clear(
        :http_listener,
        %{num_acceptors: 1, socket_opts: [port: 8000, ip: {0, 0, 0, 0}]},
        %{env: %{dispatch: dispatch}}
      )

    IO.puts("cowboy listening on 0.0.0.0:8000")
  end
end

defmodule CowboyApp.HealthHandler do
  def init(req, state) do
    req = :cowboy_req.reply(200, %{"content-type" => "application/json"}, ~s({"ok":true}), req)
    {:ok, req, state}
  end
end

defmodule CowboyApp.UploadHandler do
  def init(req, state) do
    {req, total} = drain(req, 0)
    body = ~s({"len":#{total}})
    req = :cowboy_req.reply(200, %{"content-type" => "application/json"}, body, req)
    {:ok, req, state}
  end

  defp drain(req, acc) do
    case :cowboy_req.read_body(req, %{length: 64_000, period: 5_000}) do
      {:ok, data, req} -> {req, acc + byte_size(data)}
      {:more, data, req} -> drain(req, acc + byte_size(data))
    end
  end
end

defmodule CowboyApp.ProfileHandler do
  def init(req, state) do
    {:ok, _} = :eprof.start()
    # Profile every existing process so we catch the cowboy_http connection process too.
    :eprof.start_profiling(Process.list())
    {req, total} = drain(req, 0)
    :eprof.stop_profiling()
    :eprof.log(~c"/tmp/eprof_cowboy.txt")
    :eprof.analyze(:total, [{:sort, :time}])
    :eprof.stop()
    body = ~s({"len":#{total}})
    req = :cowboy_req.reply(200, %{"content-type" => "application/json"}, body, req)
    {:ok, req, state}
  end

  defp drain(req, acc) do
    case :cowboy_req.read_body(req, %{length: 64_000, period: 5_000}) do
      {:ok, data, req} -> {req, acc + byte_size(data)}
      {:more, data, req} -> drain(req, acc + byte_size(data))
    end
  end
end
