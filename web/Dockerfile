FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY public /usr/share/nginx/html
# Keep the source HTML/SEO structure untouched while layering the reversible
# platform visual system into every rendered HTML document at image build time.
RUN find /usr/share/nginx/html -maxdepth 1 -type f -name '*.html' -exec sed -i 's#</head>#<link rel="stylesheet" href="/stitch.css?v=20260912a"></head>#' {} +
