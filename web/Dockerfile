FROM nginx:1.27-alpine
ARG BUILD_SHA=dev
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY public /usr/share/nginx/html
# Keep source SEO/application markup unchanged while layering the reversible
# platform visual system into every top-level HTML document in the image.
RUN sed -i 's#</head>#<link rel="stylesheet" href="/stitch.css?v=20260912a"></head>#' /usr/share/nginx/html/*.html \
    && printf '%s\n' "$BUILD_SHA" > /usr/share/nginx/html/build.txt
