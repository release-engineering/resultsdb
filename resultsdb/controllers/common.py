# SPDX-License-Identifier: GPL-2.0+
from flask import current_app as app
from flask import jsonify

from resultsdb.messaging import create_message, publish_taskotron_message
from resultsdb.models import db
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

    if app.messaging_plugin:
        app.logger.debug("Preparing to publish message for result id %d", result.id)
        message = create_message(result)
        app.messaging_plugin.publish(message)

    if app.config["MESSAGE_BUS_PUBLISH_TASKOTRON"]:
        app.logger.debug(
            "Preparing to publish Taskotron message for result id %d", result.id
        )
        publish_taskotron_message(result)

    return jsonify(SERIALIZE(result)), 201
