# SPDX-License-Identifier: GPL-2.0+
from flask import jsonify
from flask import current_app as app

from resultsdb import db
from resultsdb.messaging import (
    load_messaging_plugin,
    create_message,
    publish_taskotron_message,
)
from resultsdb.serializers.api_v2 import Serializer

SERIALIZE = Serializer().serialize


def commit_result(result):
    """
    Saves result in database and publishes message.

    Returns value for the POST HTTP API response.
    """
    db.session.add(result)
    db.session.commit()

    app.logger.debug(
        "Created new result for testcase %s with outcome %s",
        result.testcase.name,
        result.outcome,
    )

    if app.config["MESSAGE_BUS_PUBLISH"]:
        app.logger.debug("Preparing to publish message for result id %d", result.id)
        plugin = load_messaging_plugin(
            name=app.config["MESSAGE_BUS_PLUGIN"],
            kwargs=app.config["MESSAGE_BUS_KWARGS"],
        )
        plugin.publish(create_message(result))

    if app.config["MESSAGE_BUS_PUBLISH_TASKOTRON"]:
        app.logger.debug("Preparing to publish Taskotron message for result id %d", result.id)
        publish_taskotron_message(result)

    return jsonify(SERIALIZE(result)), 201
