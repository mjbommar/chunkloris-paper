defmodule PhoenixApp.PageController do
  use Phoenix.Controller, formats: [:json]

  def health(conn, _params) do
    conn
    |> put_resp_content_type("application/json")
    |> send_resp(200, ~s({"ok":true}))
  end

  def upload(conn, _params) do
    {total, conn} = drain(conn, 0)

    conn
    |> put_resp_content_type("application/json")
    |> send_resp(200, ~s({"len":#{total}}))
  end

  defp drain(conn, acc) do
    case Plug.Conn.read_body(conn, length: 64_000, read_length: 64_000, read_timeout: 5_000) do
      {:ok, data, conn} -> {acc + byte_size(data), conn}
      {:more, data, conn} -> drain(conn, acc + byte_size(data))
    end
  end
end

defmodule PhoenixApp.Router do
  use Phoenix.Router

  pipeline :raw do
  end

  scope "/" do
    pipe_through :raw

    get "/health", PhoenixApp.PageController, :health
    post "/upload", PhoenixApp.PageController, :upload
  end
end

defmodule PhoenixApp.ErrorJSON do
  def render(_template, _assigns), do: %{error: true}
end
