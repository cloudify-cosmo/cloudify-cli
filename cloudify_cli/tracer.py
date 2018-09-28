import opentracing
from opentracing_instrumentation.request_context import get_current_span, \
    span_in_context

from logger import get_logger

logger = get_logger()
_tracer = None


class Tracer(object):
    def __init__(self, operation_name):
        curr_span = get_current_span()
        self.span = opentracing.Tracer().start_span(
            operation_name,
            child_of=curr_span)
        self.span.__enter__()
        self.span_ctx = span_in_context(self.span)
        self.span_ctx.__enter__()

    def destroy(self, exc_type, exc_val, exc_tb):
        self.span_ctx.__exit__(exc_type, exc_val, exc_tb)
        self.span.__exit__(exc_type, exc_val, exc_tb)


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
