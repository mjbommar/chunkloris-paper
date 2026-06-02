FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src
COPY WsServer.csproj /src/WsServer.csproj
COPY Program.cs /src/Program.cs
RUN dotnet publish -c Release -o /out --nologo

FROM mcr.microsoft.com/dotnet/aspnet:9.0
WORKDIR /app
COPY --from=build /out /app
EXPOSE 8000
ENV ASPNETCORE_URLS=http://0.0.0.0:8000
ENV DOTNET_EnableDiagnostics=0
ENTRYPOINT ["dotnet","/app/WsServer.dll"]
