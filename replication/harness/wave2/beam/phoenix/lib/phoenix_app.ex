defmodule PhoenixApp.Endpoint do
  use Phoenix.Endpoint, otp_app: :phoenix_app

  plug PhoenixApp.Router
end

defmodule PhoenixApp.Application do
  use Application

  def start(_type, _args) do
    Application.put_env(:phoenix_app, PhoenixApp.Endpoint,
      adapter: Phoenix.Endpoint.Cowboy2Adapter,
      http: [
        ip: {0, 0, 0, 0},
        port: 8000
      ],
      server: true,
      url: [host: "localhost"],
      render_errors: [formats: [json: PhoenixApp.ErrorJSON], layout: false],
      pubsub_server: nil,
      secret_key_base: String.duplicate("a", 64)
    )

    children = [
      PhoenixApp.Endpoint
    ]

    opts = [strategy: :one_for_one, name: PhoenixApp.Supervisor]
    Supervisor.start_link(children, opts)
  end
end

defmodule PhoenixApp do
  def start do
    {:ok, _} = Application.ensure_all_started(:phoenix_app)
    IO.puts("phoenix(cowboy2) listening on 0.0.0.0:8000")
    Process.sleep(:infinity)
  end
end
