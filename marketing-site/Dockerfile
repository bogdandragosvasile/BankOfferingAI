FROM nginx:1.27-alpine
COPY src/index.html /usr/share/nginx/html/index.html
COPY src/demo.html /usr/share/nginx/html/demo.html
COPY src/info.html /usr/share/nginx/html/info.html
COPY src/ai-deep-dive.html /usr/share/nginx/html/ai-deep-dive.html
COPY src/_shared.html /usr/share/nginx/html/_shared.html
COPY src/_theme-toggle.html /usr/share/nginx/html/_theme-toggle.html
RUN echo 'server { \
    listen 80; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { try_files $uri $uri/ =404; } \
    gzip on; \
    gzip_types text/html text/css application/javascript; \
}' > /etc/nginx/conf.d/default.conf
