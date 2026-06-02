defmodule CowboyApp.MixProject do
  use Mix.Project

  def project do
    [
      app: :cowboy_app,
      version: "0.1.0",
      elixir: "~> 1.17",
      deps: deps()
    ]
  end

  def application do
    [extra_applications: [:logger, :tools]]
  end

  defp deps do
    [
      {:cowboy, "~> 2.12"}
    ]
  end
end
