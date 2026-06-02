FROM hexpm/elixir:1.17.3-erlang-27.1.2-debian-bookworm-20241016-slim

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN mix local.hex --force && mix local.rebar --force

COPY mix.exs /app/mix.exs
RUN mix deps.get && mix deps.compile

COPY lib /app/lib

ENV MIX_ENV=prod
RUN mix compile

EXPOSE 8000
CMD ["sh", "-c", "elixir --erl '+S 1:1' --no-halt -S mix run -e 'CowboyApp.start()'"]
