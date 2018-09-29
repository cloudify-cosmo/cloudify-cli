from opentracing import Format
from jaeger_client import reporter, sampler, Tracer

_tracer = None


class CloudifyTracer(object):
    """Simplified tracer class.
    """

    def __init__(self):
        """Initialize the Jaeger Client tracer wrapper.
        """
        self.tracer = Tracer(
            'no-op',
            reporter=reporter.NullReporter(),
            sampler=sampler.ProbabilisticSampler(0))
        self.current_span = None

    def inject(self, span_context, carrier):
        """Serializes the span_context and adds it to the carrier.

        :param span_context: span context to serialize.
        :param carrier: a dict obj to add the serialized span context to.
        """
        self.tracer.inject(span_context, Format.HTTP_HEADERS, carrier)

    def start_span(self, operation_name):
        """Same as jaeger_client.Tracer's start_span(..) method but this one
        saves the last span.

        :param operation_name: operation name.
        """
        self.current_span = self.tracer.start_span(operation_name,
                                                   self.current_span)
        return self.current_span


def init_tracing(operation_name):
    """Initializes the Opentracing tracer and starts a span with the given
    name.

    :param operation_name: operation name to start a span with.
    """
    global _tracer
    _tracer = CloudifyTracer()
    _tracer.start_span(operation_name)


def get_tracer():
    """
    :return: current tracer instance.
    """
    return _tracer
