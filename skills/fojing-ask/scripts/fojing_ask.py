#!/usr/bin/env python3
"""
FojingAsk - CLI tool for CBETA RAG API
Provides search and ask subcommands for Buddhist scripture queries
"""

import argparse
import json
import sys
import os
from pathlib import Path
import requests
from typing import Dict, Any, Optional


class FojingAskClient:
    """Client for CBETA RAG API"""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize client with config"""
        if config_path is None:
            config_path = os.path.expanduser("~/.config/cbeta-rag/config.json")

        self.config_path = config_path
        self.config = self._load_config()
        self.api_url = self.config.get("api_url", "http://192.168.50.12:8000")
        self.api_key = self.config.get("api_key")
        self.default_top_k = self.config.get("default_top_k", 5)
        self.timeout = 30

    def _load_config(self) -> Dict[str, Any]:
        """Load config from JSON file"""
        config_path = Path(self.config_path)

        if not config_path.exists():
            return {}

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return {}

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with auth"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _error_response(self, message: str) -> Dict[str, Any]:
        """Create error response"""
        return {"status": "error", "message": message}

    def search(self, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        """Execute search command"""
        # Validate config
        if not self.api_key:
            return self._error_response(
                "API key not configured. Please set api_key in ~/.config/cbeta-rag/config.json. "
                "See references/SETUP.md for configuration instructions."
            )

        if top_k is None:
            top_k = self.default_top_k

        try:
            url = f"{self.api_url}/v1/search"
            payload = {"query": query, "top_k": top_k}

            response = requests.post(
                url, json=payload, headers=self._get_headers(), timeout=self.timeout
            )

            if response.status_code != 200:
                return self._error_response(
                    f"API error: {response.status_code} - {response.text}"
                )

            api_response = response.json()

            return {
                "status": "success",
                "query": query,
                "results": api_response.get("results", []),
            }

        except requests.exceptions.Timeout:
            return self._error_response(
                f"Request timeout after {self.timeout} seconds. API server may be unavailable."
            )
        except requests.exceptions.ConnectionError:
            return self._error_response(
                f"Connection error. Cannot reach API at {self.api_url}. "
                "Check SETUP.md for server configuration."
            )
        except requests.exceptions.RequestException as e:
            return self._error_response(f"Request error: {str(e)}")
        except json.JSONDecodeError:
            return self._error_response("Invalid JSON response from API")

    def ask(self, question: str) -> Dict[str, Any]:
        """Execute ask command (RAG chat)"""
        # Validate config
        if not self.api_key:
            return self._error_response(
                "API key not configured. Please set api_key in ~/.config/cbeta-rag/config.json. "
                "See references/SETUP.md for configuration instructions."
            )

        try:
            url = f"{self.api_url}/v1/chat/completions"
            payload = {"messages": [{"role": "user", "content": question}], "rag": True}

            response = requests.post(
                url, json=payload, headers=self._get_headers(), timeout=self.timeout
            )

            if response.status_code != 200:
                return self._error_response(
                    f"API error: {response.status_code} - {response.text}"
                )

            api_response = response.json()

            # Extract answer from OpenAI-compatible response
            answer = ""
            if "choices" in api_response and len(api_response["choices"]) > 0:
                choice = api_response["choices"][0]
                if "message" in choice:
                    answer = choice["message"].get("content", "")

            result = {"status": "success", "question": question, "answer": answer}

            # Add sources if available
            if "sources" in api_response:
                result["sources"] = api_response["sources"]

            return result

        except requests.exceptions.Timeout:
            return self._error_response(
                f"Request timeout after {self.timeout} seconds. API server may be unavailable."
            )
        except requests.exceptions.ConnectionError:
            return self._error_response(
                f"Connection error. Cannot reach API at {self.api_url}. "
                "Check SETUP.md for server configuration."
            )
        except requests.exceptions.RequestException as e:
            return self._error_response(f"Request error: {str(e)}")
        except json.JSONDecodeError:
            return self._error_response("Invalid JSON response from API")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="FojingAsk - Query CBETA Buddhist scriptures via RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s search "金刚经"
  %(prog)s search "般若" --top-k 10
  %(prog)s ask "什么是般若波罗蜜多？"
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Search subcommand
    search_parser = subparsers.add_parser("search", help="Search scriptures by keyword")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Number of results to return (default: from config)",
    )
    search_parser.add_argument(
        "--config",
        help="Path to config file (default: ~/.config/cbeta-rag/config.json)",
    )

    # Ask subcommand
    ask_parser = subparsers.add_parser("ask", help="Ask question with RAG")
    ask_parser.add_argument("question", help="Question to ask")
    ask_parser.add_argument(
        "--config",
        help="Path to config file (default: ~/.config/cbeta-rag/config.json)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize client
    config_path = getattr(args, "config", None)
    client = FojingAskClient(config_path=config_path)

    # Execute command
    if args.command == "search":
        result = client.search(args.query, top_k=args.top_k)
    elif args.command == "ask":
        result = client.ask(args.question)
    else:
        result = {"status": "error", "message": "Unknown command"}

    # Output JSON
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # Exit with appropriate code
    sys.exit(0 if result.get("status") == "success" else 1)


if __name__ == "__main__":
    main()
