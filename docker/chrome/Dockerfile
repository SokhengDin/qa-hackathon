FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g chrome-devtools-mcp@latest

ENV CHROME_BIN=/usr/bin/chromium

EXPOSE 9222

CMD ["chromium", "--headless", "--disable-gpu", "--no-sandbox", \
     "--remote-debugging-address=0.0.0.0", "--remote-debugging-port=9222"]
