defmodule BanditApp.MixProject do
  use Mix.Project

  def project do
    [
      app: :bandit_app,
      version: "0.1.0",
      elixir: "~> 1.17",
      deps: deps()
    ]
  end

  def application do
    [
      extra_applications: [:logger, :tools],
      mod: {BanditApp.Application, []}
    ]
  end

  defp deps do
    [
      {:bandit, "~> 1.6"},
      {:plug, "~> 1.16"}
    ]
  end
end
