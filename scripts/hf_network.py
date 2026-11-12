"""Authenticated reads with bounded rate-limit/transport retries, page by page."""
from __future__ import annotations

import math
import re
import time
from email.utils import parsedate_to_datetime


def retry_delay(headers, attempt):
    headers = {k.lower(): v for k, v in headers.items()}
    delays = []
    value = headers.get('retry-after', '')
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = parsedate_to_datetime(value).timestamp() - time.time()
        except (ValueError, TypeError, OverflowError):
            seconds = None
    if seconds is not None and math.isfinite(seconds):
        delays.append(max(0, seconds))
    delays.extend(int(v) for v in re.findall(r'(?:^|[;,])\s*t=(\d+)', headers.get('ratelimit', '')))
    return math.ceil(max(delays)) + 1 if delays else min(60 * 2**attempt, 300)


def retry_429(operation, label, max_retries=6):
    """Retry explicit rate-limit responses only; never replay an ambiguous failure."""
    for attempt in range(max_retries + 1):
        try:
            return operation()
        except Exception as error:
            response = getattr(error, 'response', None)
            status = getattr(response, 'status_code', None) if response is not None else getattr(error, 'code', None)
            if status != 429 or attempt == max_retries:
                raise
            headers = response.headers if response is not None else error.headers
            delay = retry_delay(headers or {}, attempt)
            # urllib HTTPError owns an open response. Release it before waiting.
            if response is None and hasattr(error, 'close'):
                error.close()
            print(f'HF rate limit (429): {label}. Waiting {delay}s; retry {attempt + 1}/{max_retries}.', flush=True)
            remaining = delay
            while remaining > 0:
                interval = min(60, remaining)
                time.sleep(interval)
                remaining -= interval
                if remaining:
                    print(f'Waiting for HF rate limit reset: {remaining}s remaining.', flush=True)


def retry_read(operation, label, max_retries=3):
    """Retry transient transport/server failures only for explicitly read-only calls."""
    import httpx
    for attempt in range(max_retries + 1):
        try:
            return operation()
        except Exception as error:
            response = getattr(error, 'response', None)
            status = getattr(response, 'status_code', None) if response is not None else getattr(error, 'code', None)
            transient = status in {500, 502, 503, 504} or (
                status is None and isinstance(error, (OSError, httpx.TransportError)))
            if not transient or attempt == max_retries:
                raise
            if response is None and hasattr(error, 'close'):
                error.close()
            delay = 2 ** attempt
            print(f'Transient read failure ({type(error).__name__}): {label}; retrying in {delay}s.', flush=True)
            time.sleep(delay)


def http_client(**kwargs):
    # Imports stay lazy: offline package checks do not require the upload SDK.
    import httpx

    class RateLimitClient(httpx.Client):
        def send(self, request, **send_kwargs):
            # paths-info uses POST but is a buffered, read-only metadata query.
            readonly = request.method in {'GET', 'HEAD'} or (
                request.method == 'POST' and '/paths-info/' in request.url.path)
            if not readonly:
                return super().send(request, **send_kwargs)

            def read_request():
                response = super(RateLimitClient, self).send(request, **send_kwargs)
                if response.status_code in {429, 500, 502, 503, 504}:
                    response.close()
                    response.raise_for_status()
                return response

            # Retry this page alone, including the first SDK pagination request.
            # Exhaustion raises, preventing another SDK status-based retry loop.
            return retry_read(lambda: retry_429(read_request, 'Hub metadata/download request'),
                              'Hub metadata/download request')

    return RateLimitClient(follow_redirects=True, timeout=None, **kwargs)


def authenticated_api():
    from huggingface_hub import HfApi, set_client_factory
    set_client_factory(http_client)
    # Explicit True also works when HF_HUB_DISABLE_IMPLICIT_TOKEN is enabled.
    # Never forward this token to the separate anonymous browser/CORS checks.
    return HfApi(token=True)
