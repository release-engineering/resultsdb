# This will produce an image to be used in Openshift
# Build should be triggered from repo root like:
# docker build -f openshift/Dockerfile --build-arg resultsdb_rpm=resultsdb-2.0.2-1.fc25.noarch.rpm .

FROM centos:7
LABEL \
    name="ResultsDB application" \
    vendor="ResultsDB developers" \
    license="GPLv2+" \
    build-date=""

RUN yum -y install epel-release && yum -y clean all
# The caller should build a resultsdb RPM package using and then pass it in this arg.
ARG resultsdb_rpm
COPY $resultsdb_rpm /tmp

RUN yum -y install --setopt=tsflags=nodocs \
        python-psycopg2 \
        /tmp/$(basename $resultsdb_rpm) \
    && yum clean all \
    && rm -f /tmp/$(basename $resultsdb_rpm)

COPY runapp.py /usr/bin/run_resultsdb
COPY openshift/run_app.sh /usr/bin/run_app

RUN chmod 770 /usr/bin/run_resultsdb /usr/bin/run_app

USER 1001
EXPOSE 5001
ENTRYPOINT run_app
