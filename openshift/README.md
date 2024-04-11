Building the container image
============================

Building the container image requires the ResultsDB rpm to be provided as a
build argument:

```bash
$ podman build -f Dockerfile --tag <IMAGE_TAG> .
```

`IMAGE_TAG` is the tag to be applied on the image built.

Using the container image
=========================

The container image has port `5001/tcp` marked as exposed, but the port to be
used by ResultsDB can be changed in the configuration with the `RUN_PORT`
configuration option.

There are two volumes expected to be mounted, holding configuration for
ResultsDB and httpd:

1. The volume mounted at `/etc/resultsdb` should have `settings.py` and `.htpasswd`.
   The former holds ResultsDB configuration. For an example, see `settings.py` in
   `resultsdb-test-template.yaml`, or `conf/settings.py.example`
   for a full list of configuration options.
   `.htpasswd` holds user data for basic auth, and it's generated using `htpasswd`.

2. The volume mounted at `/etc/httpd/conf.d` should have `resultsdb.conf`,
   holding httpd configuration to be used by `mod_wsgi-express`. For an
   example, see `resultsdb.conf` in `resultsdb-test-template.yaml`.


Deploying to OpenShift
======================

`resultsdb-test-template.yaml` defines the
[template](https://docs.openshift.org/latest/dev_guide/templates.html) to
deploy ResultsDB and a PostgreSQL database to OpenShift.

For the full list of template parameters see:

```bash
$ oc process -f openshift/resultsdb-test-template.yaml --parameters
```

For creating the environment run:

```bash
$ oc process -f openshift/resultsdb-test-template.yaml \
             -p TEST_ID=<TEST_ID> \
             -p RESULTSDB_IMAGE=<RESULTSDB_IMAGE> | oc apply -f -
```

Use the `-p` option of `oc process` to override default values of the template
parameters.
