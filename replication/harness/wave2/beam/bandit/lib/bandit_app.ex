defmodule BanditApp.Router do
  @behaviour Plug

  @impl true
  def init(opts), do: opts

  @impl true
  def call(%Plug.Conn{request_path: "/health"} = conn, _opts) do
    conn
    |> Plug.Conn.put_resp_content_type("application/json")
    |> Plug.Conn.send_resp(200, ~s({"ok":true}))
  end

  def call(%Plug.Conn{request_path: "/upload"} = conn, _opts) do
    {total, conn} = drain(conn, 0)

    conn
    |> Plug.Conn.put_resp_content_type("application/json")
    |> Plug.Conn.send_resp(200, ~s({"len":#{total}}))
  end

  # Profiling variant: wrap the drain in :eprof, dump top hot functions to /tmp.
  def call(%Plug.Conn{request_path: "/profile_upload"} = conn, _opts) do
    {:ok, _} = :eprof.start()
    :eprof.start_profiling([self()])
    {total, conn} = drain(conn, 0)
    :eprof.stop_profiling()
    :eprof.log(~c"/tmp/eprof_bandit.txt")
    :eprof.analyze(:total, [{:sort, :time}])
    :eprof.stop()

    conn
    |> Plug.Conn.put_resp_content_type("application/json")
    |> Plug.Conn.send_resp(200, ~s({"len":#{total}}))
  end

  def call(conn, _opts) do
    Plug.Conn.send_resp(conn, 404, "")
  end

  defp drain(conn, acc) do
    case Plug.Conn.read_body(conn, length: 64_000, read_length: 64_000, read_timeout: 5_000) do
      {:ok, data, conn} -> {acc + byte_size(data), conn}
      {:more, data, conn} -> drain(conn, acc + byte_size(data))
    end
  end
end

defmodule BanditApp.Application do
  use Application

  def start(_type, _args) do
    children = [
      {Bandit,
       plug: BanditApp.Router,
       scheme: :http,
       port: 8000,
       ip: {0, 0, 0, 0},
       thousand_island_options: [num_acceptors: 1]}
    ]

    IO.puts("bandit listening on 0.0.0.0:8000")
    Supervisor.start_link(children, strategy: :one_for_one, name: BanditApp.Supervisor)
  end
end

defmodule BanditApp do
  def start do
    {:ok, _} = Application.ensure_all_started(:bandit_app)
    Process.sleep(:infinity)
  end
end
