import cgi

from hyperlink import URL
from pyrsistent import freeze, m
from twisted.internet.defer import Deferred, succeed

from fugue._keys import REQUEST, RESPONSE
from fugue.interceptors.basic import Interceptor
from fugue.util import namespace


_ns = namespace(__name__)
NEVOW_REQUEST = _ns('request')


def _get_headers(headers, name, default=None):
    """
    All values for a header by name.
    """
    return headers.getRawHeaders(name, [default])


def _get_first_header(headers, name, default=None):
    """
    Only the first value for a header by name.
    """
    return _get_headers(headers, name, default)[0]


def _get_content_type(headers, default=b'application/octet-stream'):
    """
    Parse the ``Content-Type`` header into the content type and character
    encoding.
    """
    content_type = _get_first_header(headers, b'content-type', default)
    _, options = cgi.parse_header(content_type)
    return content_type, options.get('charset')


def _nevow_request_to_request_map(req):
    """
    Convert a Nevow request object into an immutable request map.
    """
    headers = req.requestHeaders
    content_type, character_encoding = _get_content_type(headers)
    return m(
        body=req.content,
        content_type=content_type,
        content_length=_get_first_header(headers, b'content-length'),
        character_encoding=character_encoding,
        headers=freeze(dict(headers.getAllRawHeaders())),
        remote_addr=req.getClientIP(),
        request_method=req.method,
        server_name=req.getRequestHostname(),
        server_port=req.host.port,
        scheme=b'https' if req.isSecure() else b'http',
        #ssl_client_cert=XXX,
        uri=URL.from_text(req.uri.decode('ascii')),
        #query_string
        #path_info
        #protocol
    )


def _send_response(context):
    """
    Write a response to the network.
    """
    req = context[NEVOW_REQUEST]
    response = context[RESPONSE]
    req.setResponseCode(response['status'])
    for k, v in response.get('headers', []):
        req.responseHeaders.setRawHeaders(k, v)
    req.write(response['body'])


def _send_error(context, message):
    """
    Write an error response to the network.
    """
    _send_response(
        context.set(
            RESPONSE,
            m(status=500,
              body=message)))


def _enter_nevow(context):
    """
    Enter stage for Nevow interceptor.

    Extract information from a Nevow request into an immutable data structure.
    """
    return context.set(
        REQUEST,
        _nevow_request_to_request_map(context[NEVOW_REQUEST]))


def _leave_nevow(context):
    """
    Leave stage for Nevow interceptor.

    Set the HTTP status code, any response headers and write the body (`bytes`
    or `Deferred`) to the network. If ``RESPONSE`` is notexistent, an HTTP 500
    error is written to the network instead.
    """
    def _leave(body, context):
        context = context.set('body', body)
        _send_response(context)
        return context

    response = context.get(RESPONSE)
    if response is None:
        _send_error(context, 'Internal server error: no response')
        return succeed(context)
    body = response.get('body')
    d = body if isinstance(body, Deferred) else succeed(body)
    d.addCallback(_leave, context)
    return d


def _error_nevow(context, error):
    """
    Error stage for Nevow interceptor.
    """
    # XXX: log error
    _send_error(context, 'Internal server error: exception')
    return context


def nevow():
    """
    An interceptor that converts a Nevow request into a standard request map on
    enter and writes the response back to Nevow on leave.

    The Nevow request is expected to exist at the context key `NEVOW_REQUEST`.
    """
    return Interceptor(
        name='nevow',
        enter=_enter_nevow,
        leave=_leave_nevow,
        error=_error_nevow)


__all__ = ['nevow', 'NEVOW_REQUEST']
