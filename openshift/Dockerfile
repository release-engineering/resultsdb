# This will produce an image to be used in Openshift
# Build should be triggered from repo root like:
# docker build -f openshift/Dockerfile \
#              --tag <IMAGE_TAG>

FROM registry.fedoraproject.org/f29/httpd:latest
LABEL \
    name="ResultsDB application" \
    vendor="ResultsDB developers" \
    license="GPLv2+" \
    description="ResultsDB is a results store engine for, but not limited to, Fedora QA tools." \
    usage="https://pagure.io/taskotron/resultsdb/blob/develop/f/openshift/README.md" \
    build-date=""

USER root
COPY ./resultsdb.spec /opt/app-root/src/resultsdb/resultsdb.spec

# install dependencies defined in RPM spec file
RUN dnf -y install findutils rpm-build python3-pip python3-mod_wsgi python3-psycopg2 \
    && rpm --query --requires --specfile ./resultsdb/resultsdb.spec | xargs -d '\n' dnf -y install

COPY . /opt/app-root/src/resultsdb/
# install using --no-deps option to ensure nothing comes from PyPi
RUN pip3 install --no-deps ./resultsdb

# config files
RUN install -d /usr/share/resultsdb/conf \
    && install -p -m 0644 ./resultsdb/conf/resultsdb.conf /usr/share/resultsdb/conf/ \
    && install -p -m 0644 ./resultsdb/conf/resultsdb.wsgi /usr/share/resultsdb/ \
    && install -d /etc/resultsdb \
    && install -p -m 0644 ./resultsdb/conf/settings.py.example /etc/resultsdb/settings.py \
    && install -p -m 0644 ./resultsdb/conf/resultsdb.conf /etc/httpd/conf.d/

# clean up
RUN rm -rf /opt/app-root/src/resultsdb \
    && dnf -y autoremove findutils rpm-build \
    && dnf clean all

# EXPOSE 5001/tcp
EXPOSE 5001
CMD ["mod_wsgi-express-3", "start-server", "/usr/share/resultsdb/resultsdb.wsgi", \
    "--user", "apache", "--group", "apache", \
    "--port", "5001", "--threads", "5", \
    "--include-file", "/etc/httpd/conf.d/resultsdb.conf", \
    "--log-level", "info", \
    "--log-to-terminal", \
    "--access-log", \
    "--startup-log" \
]
USER 1001:0
