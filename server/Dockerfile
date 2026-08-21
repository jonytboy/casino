# No dependencies to install: the server uses node:http, node:sqlite and
# node:crypto only. node:sqlite needs Node 22.5 or newer.
FROM node:22-alpine

WORKDIR /app
COPY package.json ./
COPY index.js ./
COPY src ./src
COPY games ./games

# The database is the only mutable state. Mount a volume here or the balances
# disappear with the container.
RUN mkdir -p /data
ENV DB_PATH=/data/casino.db
ENV PORT=8080
VOLUME ["/data"]
EXPOSE 8080

RUN addgroup -S app && adduser -S app -G app && chown -R app:app /app /data
USER app

HEALTHCHECK --interval=30s --timeout=3s \
  CMD wget -qO- http://127.0.0.1:8080/api/health || exit 1

CMD ["node", "index.js"]
