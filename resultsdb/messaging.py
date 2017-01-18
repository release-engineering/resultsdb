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

import pkg_resources

import fedmsg

import logging
log = logging.getLogger(__name__)


class MessagingPlugin(object):
    """ Abstract base class that messaging plugins must extend.

    Two abstract methods are declared which must be implemented:
        - create_message(result, prev_result=None)
        - publish(message)

    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @abc.abstractmethod
    def create_message(self, result, prev_result=None):
        pass

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

    def create_message(self, result, prev_result):
        return dict(id=result.id)


class FedmsgPlugin(MessagingPlugin):
    """ A fedmsg plugin, used to publish to the fedmsg bus. """

    def publish(self, message):
        fedmsg.publish(**message)

    def create_message(self, result, prev_result):
        task = dict(
            (datum.key, datum.value)
            for datum in result.data
            if datum.key in ('item', 'type',)
        )
        task['name'] = result.testcase.name
        msg = {
            'topic': 'result.new',
            'modname': self.modname,
            'msg': {
                'task': task,
                'result': {
                    'id': result.id,
                    'submit_time': result.submit_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    'prev_outcome': prev_result.outcome if prev_result else None,
                    'outcome': result.outcome,
                    'log_url': result.ref_url,
                }
            }
        }

        # For the v1 API
        if hasattr(result, 'job'):
            msg['msg']['result']['job_url'] = result.job.ref_url

        # For the v2 API
        if hasattr(result, 'group'):
            msg['msg']['result']['group_url'] = result.group.ref_url

        return msg


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
