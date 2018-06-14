# This will produce an image to be used in Openshift
# Build should be triggered from repo root like:
# docker build -f openshift/Dockerfile \
#              --tag <IMAGE_TAG> \
#              --build-arg resultsdb_rpm=<RESULTSDB_RPM> ./

FROM fedora:28
LABEL \
    name="ResultsDB application" \
    vendor="ResultsDB developers" \
    license="GPLv2+" \
    description="ResultsDB is a results store engine for, but not limited to, Fedora QA tools." \
    usage="https://pagure.io/taskotron/resultsdb/blob/develop/f/openshift/README.md" \
    build-date=""

# The caller should build a resultsdb RPM package used and then pass it in this arg.
# Accept both a URL or a local path relative to the build context.
ARG resultsdb_rpm
ADD $resultsdb_rpm /tmp

RUN dnf -y update \
    && dnf -y install --setopt=tsflags=nodocs \
        python-psycopg2 \
        httpd \
        mod_wsgi \
        /tmp/$(basename $resultsdb_rpm) \
    && dnf clean all \
    && rm -f /tmp/$(basename $resultsdb_rpm)

EXPOSE 5001/tcp
VOLUME ["/etc/resultsdb", "/etc/httpd/conf.d"]
ENTRYPOINT ["mod_wsgi-express", "start-server", "/usr/share/resultsdb/resultsdb.wsgi"]
CMD [\
    "--user", "apache", "--group", "apache", \
    "--port", "5001", "--threads", "5", \
    "--include-file", "/etc/httpd/conf.d/resultsdb.conf", \
    "--log-level", "info", \
    "--log-to-terminal", \
    "--access-log", \
    "--startup-log" \
]
