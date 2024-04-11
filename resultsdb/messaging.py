# Copyright 2016, Red Hat, Inc
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Authors:
#   Ralph Bean <rbean@redhat.com>

import abc
import json
import logging
from threading import Lock

import pkg_resources
import stomp
from fedora_messaging.api import Message, publish
from fedora_messaging.exceptions import (
    ConnectionException,
    PublishForbidden,
    PublishReturned,
    PublishTimeout,
)
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import (
    TraceContextTextMapPropagator,
)
from tenacity import retry, stop_after_attempt, wait_exponential

from resultsdb.models import db
from resultsdb.models.results import Result, ResultData
from resultsdb.serializers.api_v2 import Serializer

log = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

SERIALIZE = Serializer().serialize

STOMP_RETRY_STOP = stop_after_attempt(3)
STOMP_RETRY_WAIT = wait_exponential(multiplier=2, min=5, max=15)


def get_prev_result(result):
    """
    Find previous result with the same testcase, item, type, and arch.
    Return None if no result is found.

    Note that this logic is Taskotron-specific: it does not consider the
    possibility that a result may be distinguished by other keys in the data
    (for example 'scenario' which is used in OpenQA results). But this is only
    used for publishing Taskotron compatibility messages, thus we keep this
    logic as is.
    """
    q = db.session.query(Result).filter(Result.id != result.id)
    q = q.filter_by(testcase_name=result.testcase_name)

    for result_data in result.data:
        if result_data.key in ["item", "type", "arch"]:
            alias = db.aliased(ResultData)
            q = q.join(alias).filter(
                db.and_(alias.key == result_data.key, alias.value == result_data.value)
            )

    q = q.order_by(db.desc(Result.submit_time))
    return q.first()


def publish_taskotron_message(result):
    """
    Publish a fedmsg on the taskotron topic with Taskotron-compatible structure.

    These messages are deprecated, consumers should consume from the resultsdb
    topic instead.
    """
    prev_result = get_prev_result(result)
    if prev_result is not None and prev_result.outcome == result.outcome:
        # If the previous result had the same outcome, skip publishing
        # a message for this new result.
        # This was intended as a workaround to avoid spammy messages from the
        # dist.depcheck task, which tends to produce a very large number of
        # identical results for any given build, because of the way that it is
        # designed.
        log.debug(
            "Skipping Taskotron message for result %d, outcome has not changed",
            result.id,
        )
        return

    task = {
        datum.key: datum.value
        for datum in result.data
        if datum.key
        in (
            "item",
            "type",
        )
    }
    task["name"] = result.testcase.name
    body = {
        "task": task,
        "result": {
            "id": result.id,
            "submit_time": result.submit_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "prev_outcome": prev_result.outcome if prev_result else None,
            "outcome": result.outcome,
            "log_url": result.ref_url,
        },
    }

    try:
        msg = Message(topic="taskotron.result.new", body=body)
        publish(msg)
        log.debug("Message published")
    except PublishReturned as e:
        log.error(f"Fedora Messaging broker rejected message {msg.id}: {e}")
    except PublishTimeout:
        log.error(f"Timeout publishing message {msg.id}")
    except PublishForbidden as e:
        log.error(f"Permission error publishing message {msg.id}: {e}")
    except ConnectionException as e:
        log.error(f"Error sending message {msg.id}: {e.reason}")


def create_message(result):
    # Re-use the same structure as in the HTTP API v2.
    return SERIALIZE(result)


class MessagingPlugin:
    """Abstract base class that messaging plugins must extend.

    One abstract method is declared which must be implemented:
        - publish(message)

    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @abc.abstractmethod
    def publish(self, message):
        pass


class DummyPlugin(MessagingPlugin):
    """A dummy plugin used for testing.  Just logs the messages."""

    # A class attribute where we store all messages published.
    # Used by the test suite.  This would cause a memory leak if used in prod.
    history: list[dict[str, object]] = []

    def publish(self, message):
        # Add telemetry information. This includes an extra key
        # traceparent.
        TraceContextTextMapPropagator().inject(message)
        self.history.append(message)
        log.info(f"{self!r}->{message!r}")


class FedmsgPlugin(MessagingPlugin):
    """A fedmsg plugin, used to publish to the fedmsg bus."""

    def publish(self, message):
        try:
            msg = Message(topic=f"{self.modname}.result.new", body=message)
            publish(msg)
            log.debug("Message published")
        except PublishReturned as e:
            log.error(f"Fedora Messaging broker rejected message {msg.id}: {e}")
        except PublishTimeout:
            log.error(f"Timeout publishing message {msg.id}")
        except PublishForbidden as e:
            log.error(f"Permission error publishing message {msg.id}: {e}")
        except ConnectionException as e:
            log.error(f"Error sending message {msg.id}: {e.reason}")


class StompPlugin(MessagingPlugin):
    def __init__(self, **kwargs):
        args = kwargs.copy()
        conn_args = args["connection"].copy()
        if "use_ssl" in conn_args:
            use_ssl = conn_args["use_ssl"]
            del conn_args["use_ssl"]
        else:
            use_ssl = False

        ssl_args = {"for_hosts": conn_args.get("host_and_ports", [])}
        for attr in ("key_file", "cert_file", "ca_certs"):
            conn_attr = f"ssl_{attr}"
            if conn_attr in conn_args:
                ssl_args[attr] = conn_args[conn_attr]
                del conn_args[conn_attr]

        if "ssl_version" in conn_args:
            ssl_args["ssl_version"] = conn_args["ssl_version"]
            del conn_args["ssl_version"]

        args["connection"] = conn_args
        args["use_ssl"] = use_ssl
        args["ssl_args"] = ssl_args

        super().__init__(**args)

        # Validate that some required config is present
        required = ["connection", "destination"]
        for attr in required:
            if getattr(self, attr, None) is None:
                raise ValueError(f"Missing {attr!r} option for STOMP messaging plugin")

        self.conn_lock = Lock()
        self.conn = stomp.connect.StompConnection11(**self.connection)
        if self.use_ssl:
            self.conn.set_ssl(**self.ssl_args)

    @tracer.start_as_current_span("StompPlugin.publish")
    def publish(self, msg):
        # Add telemetry information. This includes an extra key
        # traceparent.
        TraceContextTextMapPropagator().inject(msg)

        msg = json.dumps(msg)
        kwargs = {"body": msg, "headers": {}, "destination": self.destination}
        self._publish_with_retry(**kwargs)

    @retry(stop=STOMP_RETRY_STOP, wait=STOMP_RETRY_WAIT, reraise=True)
    def _publish_with_retry(self, **kwargs):
        with self.conn_lock:
            if not self.conn.is_connected():
                log.info("Connecting to message bus")

                # Inactive connection is be closed/disconnected automatically
                # after a short time.
                with tracer.start_as_current_span("StompPlugin.publish.connect"):
                    self.conn.connect(wait=True)
            with tracer.start_as_current_span("StompPlugin.publish.send"):
                self.conn.send(**kwargs)
            log.debug("Published message through stomp: %s", kwargs["body"])


def load_messaging_plugin(name, plugin_args):
    """Instantiate and return the appropriate messaging plugin."""
    points = pkg_resources.iter_entry_points("resultsdb.messaging.plugins")
    classes = {"dummy": DummyPlugin}
    classes.update({point.name: point.load() for point in points})

    log.debug("Found the following installed messaging plugin %r" % classes)
    if name not in classes:
        raise KeyError(f"{name!r} not found in {classes.keys()!r}")

    cls = classes[name]

    # Sanity check
    if not issubclass(cls, MessagingPlugin):
        raise TypeError(f"{name} {cls!r} does not extend MessagingPlugin.")

    log.debug(f"Instantiating plugin {cls!r} named {name}")
    return cls(**plugin_args)
