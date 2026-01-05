"""Functions for interacting with the RNV data hub API.

This module provides the ClientFunctions class for requesting access tokens and querying the Data Hub API.
Based on: https://github.com/Rhein-Neckar-Verkehr/data-hub-python-client
"""
import asyncio
import logging
from typing import Any, Optional

import aiohttp
from aiohttp import ClientError, ClientResponseError, ClientSSLError

from ..const import CLIENT_NAME

_LOGGER = logging.getLogger(__name__)


class ClientFunctions:
    """Async functions for interacting with the RNV data hub API."""

    def __init__(self, url: str, session: Optional[aiohttp.ClientSession] = None) -> None:
        self.url = url
        self._session = session

    async def get(self, path: str, params: dict | None = None) -> dict | None:
        """Async GET request. If a session was not provided, use a temporary one."""
        full_url = f"{self.url}/{path}"
        headers = {
            "User-Agent": CLIENT_NAME,
            "Accept": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=10)

        session = self._session
        if session is None:
            async with aiohttp.ClientSession() as session:
                return await self._do_get(session, full_url, headers, params, timeout)
        return await self._do_get(session, full_url, headers, params, timeout)

    async def _do_get(
        self,
        session: aiohttp.ClientSession,
        full_url: str,
        headers: dict[str, str],
        params: Optional[dict],
        timeout: aiohttp.ClientTimeout,
    ) -> dict | None:
        try:
            async with session.get(full_url, headers=headers, params=params, timeout=timeout) as resp:
                resp.raise_for_status()
                return await resp.json()
        except ClientSSLError as e:
            _LOGGER.error("SSL error during GET request: %s", e)
            raise
        except asyncio.TimeoutError:
            _LOGGER.error("Request timed out during GET request")
            raise
        except ClientResponseError as e:
            # ClientResponseError does not always include body; log status/message
            _LOGGER.error("HTTP error during GET request: %s (status=%s)", e.message, e.status)
            raise
        except ClientError as e:
            _LOGGER.error("HTTP client error during GET request: %s", e)
            raise
        except Exception as e:
            _LOGGER.exception("Unexpected error during GET request: %s", e)
            raise

    async def post(self, path: str, data: dict) -> dict | None:
        """Async POST request. Sends JSON body."""
        full_url = f"{self.url}/{path}"
        headers = {
            "User-Agent": CLIENT_NAME,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        timeout = aiohttp.ClientTimeout(total=10)

        session = self._session
        if session is None:
            async with aiohttp.ClientSession() as session:
                return await self._do_post(session, full_url, headers, data, timeout)
        return await self._do_post(session, full_url, headers, data, timeout)

    async def _do_post(
        self,
        session: aiohttp.ClientSession,
        full_url: str,
        headers: dict[str, str],
        data: dict,
        timeout: aiohttp.ClientTimeout,
    ) -> dict | None:
        try:
            async with session.post(full_url, headers=headers, json=data, timeout=timeout) as resp:
                resp.raise_for_status()
                return await resp.json()
        except ClientSSLError as e:
            _LOGGER.error("SSL error during POST request: %s", e)
            raise
        except asyncio.TimeoutError:
            _LOGGER.error("Request timed out during POST request")
            raise
        except ClientResponseError as e:
            _LOGGER.error("HTTP error during POST request: %s (status=%s)", e.message, e.status)
            raise
        except ClientError as e:
            _LOGGER.error("HTTP client error during POST request: %s", e)
            raise
        except Exception as e:
            _LOGGER.exception("Unexpected error during POST request: %s", e)
            raise
