# Local preview only. GitHub Pages builds the site itself and never sees this.
# Installs the same `github-pages` gem GitHub runs, so preview matches production.
FROM ruby:3.2-slim

RUN apt-get update -y \
 && apt-get install -y --no-install-recommends build-essential git \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# Bundle lives OUTSIDE /srv/jekyll on purpose: that path is bind-mounted to the
# host at runtime, which would otherwise hide the Gemfile.lock created here.
WORKDIR /gems
COPY Gemfile /gems/Gemfile
RUN bundle install --no-cache
ENV BUNDLE_GEMFILE=/gems/Gemfile

WORKDIR /srv/jekyll
EXPOSE 8080 35729

# --force_polling: file-change events don't cross the Docker VM boundary on macOS.
CMD ["bundle", "exec", "jekyll", "serve", \
     "--host", "0.0.0.0", "--port", "8080", \
     "--livereload", "--livereload-port", "35729", \
     "--force_polling"]
