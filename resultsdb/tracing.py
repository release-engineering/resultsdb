# SPDX-License-Identifier: GPL-2.0+

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_tracing(app, engine):  # pragma: no cover
    endpoint = app.config.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
    service_name = app.config.get("OTEL_EXPORTER_SERVICE_NAME")
    if not endpoint or not service_name:
        return
    resource = Resource(attributes={SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)
    instrumentor = FlaskInstrumentor()
    instrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    otlp_exporter = OTLPSpanExporter(
        endpoint=app.config["OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"]
    )
    processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
