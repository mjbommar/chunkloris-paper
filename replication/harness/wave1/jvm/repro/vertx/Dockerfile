FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
RUN mvn -B -q dependency:go-offline || true
COPY src ./src
RUN mvn -B -q -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/* \
 && curl -sSL -o /tmp/ap.tgz https://github.com/async-profiler/async-profiler/releases/download/v3.0/async-profiler-3.0-linux-x64.tar.gz \
 && tar -xzf /tmp/ap.tgz -C /opt/ \
 && mv /opt/async-profiler-3.0-linux-x64 /opt/async-profiler \
 && rm /tmp/ap.tgz
COPY --from=build /src/target/app.jar /app/app.jar
ENV JAVA_OPTS="-XX:+UnlockDiagnosticVMOptions -XX:+DebugNonSafepoints"
EXPOSE 8000
ENTRYPOINT ["sh","-c","exec java $JAVA_OPTS -jar /app/app.jar"]
