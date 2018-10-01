from copy import deepcopy
import pickle

from opentracing import Format
from jaeger_client import reporter, sampler, Tracer

SPANS_TO_REPORT = 'spans_to_report'
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
            sampler=sampler.ConstSampler(True))
        self.current_span = None

    def inject(self, span_context, carrier):
        """Serializes the span_context and adds it to the carrier.

        :param span_context: span context to serialize.
        :param carrier: a dict obj to add the serialized span context to.
        """
        ctx_cpy = deepcopy(span_context)
        baggage = ctx_cpy.baggage
        if SPANS_TO_REPORT in baggage:
            baggage[SPANS_TO_REPORT] = pickle.dumps(baggage[SPANS_TO_REPORT])
        self.tracer.inject(ctx_cpy, Format.HTTP_HEADERS, carrier)

    def start_span(self, operation_name):
        """Same as jaeger_client.Tracer's start_span(..) method but this one
        saves the last span.

        :param operation_name: operation name.
        """
        span = self.tracer.start_span(operation_name,
                                      self.current_span)
        baggage = span.context.baggage
        if SPANS_TO_REPORT not in baggage:
            baggage[SPANS_TO_REPORT] = dict()
        s_dict = self._get_span_dict(span)
        baggage[SPANS_TO_REPORT][s_dict['span_id']] = pickle.dumps(s_dict)
        self.current_span = span
        return self.current_span

    @staticmethod
    def _get_span_dict(span):
        s_dict = dict()
        s_fields = ['operation_name', 'start_time', 'logs', 'tags']
        s_ctx_fields = ['trace_id', 'span_id', 'parent_id', 'flags',
                        'debug_id']
        for field in s_fields:
            s_dict[field] = getattr(span, field)
        context = span.context
        for field in s_ctx_fields:
            s_dict[field] = getattr(context, field)
        return s_dict

    @staticmethod
    def remove_spans_to_report(span_context):
        """Removes all the spans to report field in the context baggage.

        :param span_context: span context obj.
        """
        if SPANS_TO_REPORT in span_context.baggage:
            del span_context.baggage[SPANS_TO_REPORT]


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
