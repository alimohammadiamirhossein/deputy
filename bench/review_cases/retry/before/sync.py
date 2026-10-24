"""Push records to the remote inventory service."""


def push(record, send):
    """Send one record and return the service's response. `send` raises ConnectionError when
    the service is unreachable."""
    return send(record)
