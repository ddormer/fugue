from fugue.interceptors.basic import Interceptor
from fugue.interceptors.nevow import _enter_nevow, _error_nevow, _leave_nevow
from fugue.util import namespace

_ns = namespace(__name__)
TWISTED_REQUEST = _ns('request')


_enter_twisted = _enter_nevow(TWISTED_REQUEST)


_error_twisted = _error_nevow(TWISTED_REQUEST)


def _leave_twisted(context):
    """
    Leave stage for Twisted interceptor.

    Adds a callback to `_leave_nevow` that calls ``finish`` on the request.
    """
    def _finish_request(context):
        context.get(TWISTED_REQUEST).finish()
        return context
    d = _leave_nevow(TWISTED_REQUEST)(context)
    d.addCallback(_finish_request)
    return d


def twisted():
    """
    An interceptor that converts a Twisted request into a standard request map
    on enter and writes the response back to Twisted on leave. The Twisted
    request is expected to exist at the context key `TWISTED_REQUEST`.
    """
    return Interceptor(
        name='twisted',
        enter=_enter_twisted,
        leave=_leave_twisted,
        error=_error_twisted)


__all__ = ['twisted', 'TWISTED_REQUEST']
