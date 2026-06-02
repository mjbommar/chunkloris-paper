FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src
COPY KestrelH2.csproj Program.cs /src/
RUN dotnet publish -c Release -o /out

FROM mcr.microsoft.com/dotnet/aspnet:9.0
WORKDIR /app
COPY --from=build /out /app
EXPOSE 8000
ENV ASPNETCORE_URLS=http://0.0.0.0:8000
ENV DOTNET_USE_POLLING_FILE_WATCHER=1
ENTRYPOINT ["dotnet", "/app/KestrelH2.dll"]
