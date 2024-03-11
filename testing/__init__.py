# SPDX-License-Identifier: GPL-2.0+
import datetime


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)
