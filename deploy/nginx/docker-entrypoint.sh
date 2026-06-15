#!/bin/sh
set -e

if [ -f /etc/nginx/certs/fullchain.pem ] && [ -f /etc/nginx/certs/privkey.pem ]; then
    echo "SSL certs found — using HTTPS config (port 8443)"
    cp /etc/nginx/templates/nginx.https.conf /etc/nginx/nginx.conf
else
    echo "No SSL certs — using HTTP config (port 80)"
    cp /etc/nginx/templates/nginx.http.conf /etc/nginx/nginx.conf
fi

exec nginx -g 'daemon off;'
