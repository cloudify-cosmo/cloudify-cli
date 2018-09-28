import opentracing
from jaeger_client import constants, codecs
from opentracing_instrumentation.request_context import get_current_span, \
    span_in_context

from logger import get_logger

logger = get_logger()

_tracer = None


class Tracer(object):
    """Simplified tracer class.
    """
    def __init__(self, operation_name):
        curr_span = get_current_span()
        self.span = opentracing.Tracer().start_span(
            operation_name,
            child_of=curr_span)
        self.span.__enter__()
        self.span_ctx = span_in_context(self.span)
        self.span_ctx.__enter__()
        self._tracer_http_codec = self._get_http_codec()

    def destroy(self):
        """Destroys the span and span context.
        """
        self.span_ctx.__exit__(None, None, None)
        self.span.__exit__(None, None, None)

    @staticmethod
    def _get_http_codec():
        """Initializes an HTTP codec to serialize the span context.

        :return: an initialized HTTP codec instance.
        """
        return codecs.TextCodec(
            url_encoding=True,
            trace_id_header=constants.TRACE_ID_HEADER,
            baggage_header_prefix=constants.BAGGAGE_HEADER_PREFIX,
            debug_id_header=constants.DEBUG_ID_HEADER_KEY)

    def inject(self, span_context, carrier):
        """Serializes the span_context and adds it to the carrier.

        :param span_context: span context to serialize.
        :param carrier: a dict obj to add the serialized span context to.
        """
        self._tracer_http_codec.inject(span_context, carrier)


def init_tracing(operation_name):
    """Initializes the Opentracing tracer and starts a span with the given
    name.

    :param operation_name: operation name to start a span with.
    """
    global _tracer
    logger.debug('Initializing tracer...')
    _tracer = Tracer(operation_name)


def close():
    """Destroys the tracer.

    :raises RuntimeError: whenever 'close' is called before 'init_tracing'.
    """
    if not _tracer:
        raise RuntimeError(
            'Tracer closed before initialized, call "init_tracing" first.')
    logger.debug('Destroying tracer...')
    _tracer.destroy()


def get_tracer():
    """
    :return: current tracer instance.
    """
    return _tracer
