FROM nginx:1.27-alpine
# Patch OS-level Alpine packages (openssl, brotli, etc.) at build time
# rather than trusting the base image tag to already be current.
RUN apk update && apk upgrade --no-cache
COPY index.html /usr/share/nginx/html/index.html
EXPOSE 80
