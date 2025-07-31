"""Functions for interacting with the RNV data hub API.

This module provides the ClientFunctions class for requesting access tokens and querying the Data Hub API.
Based on: https://github.com/Rhein-Neckar-Verkehr/data-hub-python-client
"""

import json
import logging

import requests
from requests.exceptions import RequestException, SSLError, Timeout

_LOGGER = logging.getLogger(__name__)


class ClientFunctions:
    """Functions for interacting with the RNV data hub API."""

    def __init__(self, opts: dict) -> None:
        """Initialize ClientFunctions."""
        self.opts = opts

    def request_access_token(self) -> dict | None:
        """Request an access token from the oauth2 authorization server.

        :return: Access token message body or None if failed.
        """
        if not self.opts.get("OAUTH_URL"):
            raise ValueError("OAUTH_URL is missing from opts or is None.")

        rq_body = (
            f"grant_type=client_credentials&client_id={self.opts['CLIENT_ID']}"
            f"&client_secret={self.opts['CLIENT_SECRET']}&resource={self.opts['RESOURCE_ID']}"
        )
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            response = requests.post(
                self.opts["OAUTH_URL"], headers=headers, data=rq_body, timeout=10
            )
            response.raise_for_status()
            return response.json()

        except SSLError as e:
            _LOGGER.error("SSL error while requesting access token: %s", e)
        except Timeout:
            _LOGGER.error("Request timed out while requesting access token")
        except RequestException as e:
            _LOGGER.error("HTTP error while requesting access token: %s", e)
        except Exception:
            _LOGGER.exception("Unexpected error requesting access token")

        return None

    def request_query_response(self, query: str, at_response: dict) -> dict | None:
        """Do GraphQL query in a POST request and obtain the response from Data Hub API.

        :param query: GraphQL query as string.
        :param at_response: Access token message body.
        :return: Query response message body or None if failed.
        """
        post_data_str = json.dumps({"query": query})
        headers = {
            "Authorization": f"Bearer {at_response['access_token']}",
            "Content-Type": "application/json",
            "Content-Length": str(len(post_data_str)),
        }

        try:
            response = requests.post(
                self.opts["CLIENT_API_URL"],
                headers=headers,
                data=post_data_str,
                timeout=10,
            )
            response.raise_for_status()
            return response.json()

        except SSLError as e:
            _LOGGER.error("SSL error during GraphQL query: %s", e)
        except Timeout:
            _LOGGER.error("Request timed out during GraphQL query")
        except RequestException as e:
            _LOGGER.error("HTTP error during GraphQL query: %s", e)
        except Exception:
            _LOGGER.exception("Unexpected error during GraphQL query")

        return None
