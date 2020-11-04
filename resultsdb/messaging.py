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

import pkg_resources

from resultsdb import db, app
from resultsdb.models.results import Result, ResultData
from resultsdb.serializers.api_v2 import Serializer

import logging
log = logging.getLogger(__name__)

try:
    from fedora_messaging.api import Message, publish
    from fedora_messaging.exceptions import PublishReturned, ConnectionException
except ImportError:
    if app.config.get('MESSAGE_BUS_PUBLISH_TASKOTRON') or app.config.get('MESSAGE_BUS_PLUGIN') == 'fedmsg':
        log.error('fedora-messaging must be installed if "MESSAGE_BUS_PUBLISH_TASKOTRON" is '
                  'enabled or "MESSAGE_BUS_PLUGIN" is set to "fedmsg"')
        raise


SERIALIZE = Serializer().serialize


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
        if result_data.key in ['item', 'type', 'arch']:
            alias = db.aliased(ResultData)
            q = q.join(alias).filter(
                db.and_(alias.key == result_data.key, alias.value == result_data.value))

    q = q.order_by(db.desc(Result.submit_time))
    return q.first()


def publish_taskotron_message(result, include_job_url=False):
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
        log.debug("Skipping Taskotron message for result %d, outcome has not changed", result.id)
        return

    task = dict(
        (datum.key, datum.value)
        for datum in result.data
        if datum.key in ('item', 'type',)
    )
    task['name'] = result.testcase.name
    body = {
        'task': task,
        'result': {
            'id': result.id,
            'submit_time': result.submit_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            'prev_outcome': prev_result.outcome if prev_result else None,
            'outcome': result.outcome,
            'log_url': result.ref_url,
        }
    }

    if include_job_url:  # only in the v1 API
        body['result']['job_url'] = result.groups[0].ref_url if result.groups else None

    try:
        msg = Message (
            topic='taskotron.result.new',
            body=body
        )
        publish(msg)
        log.debug("Message published")
    except PublishReturned as e:
        log.error('Fedora Messaging broker rejected message {}: {}'.format(msg.id, e))
    except ConnectionException as e:
        log.error('Error sending message {}: {}'.format(msg.id, e.reason))


def create_message(result):
    # Re-use the same structure as in the HTTP API v2.
    return SERIALIZE(result)


class MessagingPlugin(object):
    """ Abstract base class that messaging plugins must extend.

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
    """ A dummy plugin used for testing.  Just logs the messages. """
    # A class attribute where we store all messages published.
    # Used by the test suite.  This would cause a memory leak if used in prod.
    history = []

    def publish(self, message):
        self.history.append(message)
        log.info("%r->%r" % (self, message))


class FedmsgPlugin(MessagingPlugin):
    """ A fedmsg plugin, used to publish to the fedmsg bus. """

    def publish(self, message):

        try:
            msg = Message(
                topic='{}.result.new'.format(self.modname),
                body=message
            )
            publish(msg)
            log.debug("Message published")
        except PublishReturned as e:
            log.error('Fedora Messaging broker rejected message {}: {}'.format(msg.id, e))
        except ConnectionException as e:
            log.error('Error sending message {}: {}'.format(msg.id, e.reason))


class StompPlugin(MessagingPlugin):
    def __init__(self, **kwargs):
        # Ensure that we can import this at startup time.
        import stomp
        self.stomp = stomp

        super(StompPlugin, self).__init__(**kwargs)

        # Validate that some required config is present
        required = ['connection', 'destination']
        for attr in required:
            if getattr(self, attr, None) is None:
                raise ValueError("%r required for %r." % (attr, self))

    def publish(self, msg):
        msg = json.dumps(msg)
        kwargs = dict(body=msg, headers={}, destination=self.destination)

        if self.stomp.__version__[0] < 4:
            kwargs['message'] = kwargs.pop('body')  # On EL7, different sig.

        conn = self.stomp.Connection(**self.connection)
        conn.connect()
        try:
            conn.send(**kwargs)
            log.debug("Published message through stomp: %s", msg)
        finally:
            conn.disconnect()


def load_messaging_plugin(name, kwargs):
    """ Instantiate and return the appropriate messaging plugin. """
    points = pkg_resources.iter_entry_points('resultsdb.messaging.plugins')
    classes = {'dummy': DummyPlugin}
    classes.update(dict([(point.name, point.load()) for point in points]))

    log.debug("Found the following installed messaging plugin %r" % classes)
    if name not in classes:
        raise KeyError("%r not found in %r" % (name, classes.keys()))

    cls = classes[name]

    # Sanity check
    if not issubclass(cls, MessagingPlugin):
        raise TypeError("%s %r does not extend MessagingPlugin." % (name, cls))

    log.debug("Instantiating plugin %r named %s" % (cls, name))
    return cls(**kwargs)
