FROM quay.io/fedora/python-313:20250101@sha256:dc3b9cf6de0ce9dca8b7eda0b353f7cfa15887e0bfe2015b2100f7d1aa368293 AS builder

# builder should use root to install/create all files
USER root

# hadolint ignore=DL3033,DL3041,DL4006,SC2039,SC3040
RUN set -exo pipefail \
    && mkdir -p /mnt/rootfs \
    # install runtime dependencies
    && dnf install -y \
        --installroot=/mnt/rootfs \
        --use-host-config \
        --setopt install_weak_deps=false \
        --nodocs \
        --disablerepo=* \
        --enablerepo=fedora,updates \
        krb5-libs \
        mod_ssl \
        openldap \
        python3 \
        httpd-core \
        python3-mod_wsgi \
    && dnf --installroot=/mnt/rootfs clean all \
    && ln -s mod_wsgi-express-3 /mnt/rootfs/usr/bin/mod_wsgi-express \
    # https://python-poetry.org/docs/master/#installing-with-the-official-installer
    && curl -sSL --proto "=https" https://install.python-poetry.org | python3 - \
    && python3 -m venv /venv

ENV \
    PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Copy only specific files to avoid accidentally including any generated files
# or secrets.
COPY resultsdb ./resultsdb
COPY conf ./conf
COPY \
    pyproject.toml \
    poetry.lock \
    README.md \
    alembic.ini \
    entrypoint.sh \
    ./

# hadolint ignore=SC1091
RUN set -ex \
    && export PATH=/root/.local/bin:"$PATH" \
    && . /venv/bin/activate \
    && poetry build --format=wheel \
    && version=$(poetry version --short) \
    && pip install --no-cache-dir dist/resultsdb-"$version"-py3*.whl \
    && deactivate \
    && mv /venv /mnt/rootfs \
    && mkdir -p /mnt/rootfs/app \
    && cp -v entrypoint.sh /mnt/rootfs/app

# fix apache config for container use
RUN sed -i 's#^WSGISocketPrefix .*#WSGISocketPrefix /tmp/wsgi#' conf/resultsdb.conf \
    # install configuration
    && install -d /mnt/rootfs/usr/share/resultsdb/conf \
    && install -p -m 0644 conf/resultsdb.conf /mnt/rootfs/usr/share/resultsdb/conf/ \
    && install -p -m 0644 conf/resultsdb.wsgi /mnt/rootfs/usr/share/resultsdb/ \
    && install -d /mnt/rootfs/etc/resultsdb \
    && install -p -m 0644 conf/resultsdb.conf /mnt/rootfs/etc/httpd/conf.d/ \
    # install alembic configuration and migrations
    && install -p -m 0644 alembic.ini /mnt/rootfs/usr/share/resultsdb/alembic.ini \
    && cp -a resultsdb/alembic /mnt/rootfs/usr/share/resultsdb/alembic \
    && chmod -R 0755 /mnt/rootfs/usr/share/resultsdb/alembic

# This is just to satisfy linters
USER 1001

# --- Final image
FROM scratch
ARG GITHUB_SHA
ARG EXPIRES_AFTER
LABEL \
    name="ResultsDB application" \
    vendor="ResultsDB developers" \
    license="GPLv2+" \
    description="ResultsDB is a results store engine for, but not limited to, Fedora QA tools." \
    usage="https://pagure.io/taskotron/resultsdb/blob/develop/f/openshift/README.md" \
    url="https://github.com/release-engineering/resultsdb" \
    vcs-type="git" \
    vcs-ref=$GITHUB_SHA \
    io.k8s.display-name="ResultsDB" \
    quay.expires-after=$EXPIRES_AFTER

ENV \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1 \
    WEB_CONCURRENCY=8

COPY --from=builder /mnt/rootfs/ /
COPY --from=builder \
    /etc/yum.repos.d/fedora.repo \
    /etc/yum.repos.d/fedora-updates.repo \
    /etc/yum.repos.d/
WORKDIR /app

USER 1001
EXPOSE 5001

# Validate virtual environment
RUN /app/entrypoint.sh python -c 'import resultsdb' \
    && mod_wsgi-express module-config \
    && /app/entrypoint.sh resultsdb --help

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["mod_wsgi-express", "start-server", "/usr/share/resultsdb/resultsdb.wsgi", \
    "--user", "apache", "--group", "apache", \
    "--port", "5001", "--threads", "5", \
    "--include-file", "/etc/httpd/conf.d/resultsdb.conf", \
    "--log-level", "info", \
    "--log-to-terminal", \
    "--access-log", \
    "--startup-log" \
]
USER 1001:0
