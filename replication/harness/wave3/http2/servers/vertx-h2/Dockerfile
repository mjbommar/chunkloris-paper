FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml /src/
COPY src /src/src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/target/vertx-h2-1.0-jar-with-dependencies.jar /app/app.jar
EXPOSE 8000
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
