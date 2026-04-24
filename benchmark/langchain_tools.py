"""Lazy tool registry for TMC-ChordTools benchmark execution."""

from __future__ import annotations

import importlib
import os
from tempfile import mkdtemp
from typing import Callable, Dict, Iterable


def _build_closest_airport():
    from amadeus import Client
    from langchain_community.tools.amadeus.closest_airport import AmadeusClosestAirport

    AmadeusClosestAirport.model_rebuild()
    return AmadeusClosestAirport()


def _build_arxiv():
    from langchain_community.tools import ArxivQueryRun

    return ArxivQueryRun()


def _build_brave_search():
    from langchain_community.tools.brave_search.tool import BraveSearch

    return BraveSearch.from_api_key(
        api_key=os.environ.get("BRAVE_SEARCH_API_KEY", "fake-key"),
        search_kwargs={"count": 1},
    )


def _build_duckduckgo_search():
    from langchain_community.tools import DuckDuckGoSearchRun

    return DuckDuckGoSearchRun()


def _build_duckduckgo_results_json():
    from langchain_community.tools import DuckDuckGoSearchResults

    return DuckDuckGoSearchResults()


def _build_open_weather_map():
    from langchain_community.tools import OpenWeatherMapQueryRun
    from langchain_community.utilities import OpenWeatherMapAPIWrapper

    return OpenWeatherMapQueryRun(api_wrapper=OpenWeatherMapAPIWrapper())


def _build_reddit_search():
    from langchain_community.tools import RedditSearchRun
    from langchain_community.utilities.reddit_search import RedditSearchAPIWrapper

    return RedditSearchRun(
        api_wrapper=RedditSearchAPIWrapper(
            reddit_client_id=os.environ.get("REDDIT_CLIENT_ID", "fake-key"),
            reddit_client_secret=os.environ.get("REDDIT_CLIENT_SECRET", "fake-key"),
            reddit_user_agent="Langchain-based application",
        )
    )


def _build_semanticscholar():
    from langchain_community.tools.semanticscholar import SemanticScholarQueryRun

    return SemanticScholarQueryRun()


def _build_sleep():
    from langchain_community.tools.sleep.tool import SleepTool

    return SleepTool()


def _build_stack_exchange():
    from langchain_community.tools import StackExchangeTool
    from langchain_community.utilities import StackExchangeAPIWrapper

    return StackExchangeTool(api_wrapper=StackExchangeAPIWrapper())


def _build_tavily_search_results_json():
    from langchain_community.tools import TavilySearchResults

    return TavilySearchResults(max_results=1)


def _build_tavily_answer():
    from langchain_community.tools import TavilyAnswer

    return TavilyAnswer(max_results=1)


def _build_wikipedia():
    from langchain_community.tools import WikipediaQueryRun
    from langchain_community.utilities import WikipediaAPIWrapper

    return WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())


def _build_wikidata():
    from langchain_community.tools.wikidata.tool import WikidataQueryRun
    from langchain_community.utilities.wikidata import WikidataAPIWrapper

    return WikidataQueryRun(api_wrapper=WikidataAPIWrapper())


def _build_yahoo_finance_news():
    from langchain_community.tools import YahooFinanceNewsTool

    return YahooFinanceNewsTool()


def _build_youtube_search():
    from langchain_community.tools import YouTubeSearchTool

    return YouTubeSearchTool()


def _build_terminal():
    from langchain_community.tools import ShellTool

    return ShellTool()


_DIRECT_TOOL_FACTORIES: Dict[str, Callable[[], object]] = {
    "closest_airport": _build_closest_airport,
    "arxiv": _build_arxiv,
    "brave_search": _build_brave_search,
    "duckduckgo_search": _build_duckduckgo_search,
    "duckduckgo_results_json": _build_duckduckgo_results_json,
    "open_weather_map": _build_open_weather_map,
    "reddit_search": _build_reddit_search,
    "semanticscholar": _build_semanticscholar,
    "sleep": _build_sleep,
    "stack_exchange": _build_stack_exchange,
    "tavily_search_results_json": _build_tavily_search_results_json,
    "tavily_answer": _build_tavily_answer,
    "wikipedia": _build_wikipedia,
    "Wikidata": _build_wikidata,
    "yahoo_finance_news": _build_yahoo_finance_news,
    "youtube_search": _build_youtube_search,
    "terminal": _build_terminal,
}


def _load_file_tools() -> Dict[str, object]:
    from langchain_community.agent_toolkits import FileManagementToolkit

    toolkit = FileManagementToolkit(root_dir=mkdtemp(prefix="tmc_chordtools_"))
    return {tool.name: tool for tool in toolkit.get_tools()}


def _load_financial_tools() -> Dict[str, object]:
    from langchain_community.agent_toolkits.financial_datasets.toolkit import (
        FinancialDatasetsAPIWrapper,
        FinancialDatasetsToolkit,
    )

    toolkit = FinancialDatasetsToolkit(
        api_wrapper=FinancialDatasetsAPIWrapper(
            financial_datasets_api_key=os.environ.get("FINANCIAL_DATASETS_API_KEY", "fake-key")
        )
    )
    return {tool.name: tool for tool in toolkit.get_tools()}


def _load_polygon_tools() -> Dict[str, object]:
    from langchain_community.agent_toolkits.polygon.toolkit import PolygonToolkit
    from langchain_community.utilities.polygon import PolygonAPIWrapper

    toolkit = PolygonToolkit.from_polygon_api_wrapper(PolygonAPIWrapper())
    return {tool.name: tool for tool in toolkit.get_tools()}


def _load_request_tools() -> Dict[str, object]:
    from langchain_community.agent_toolkits.openapi.toolkit import RequestsToolkit
    from langchain_community.utilities.requests import TextRequestsWrapper

    toolkit = RequestsToolkit(
        requests_wrapper=TextRequestsWrapper(headers={}),
        allow_dangerous_requests=True,
    )
    return {tool.name: tool for tool in toolkit.get_tools()}


_GROUP_LOADERS: Dict[str, Callable[[], Dict[str, object]]] = {
    "filesystem": _load_file_tools,
    "financial": _load_financial_tools,
    "polygon": _load_polygon_tools,
    "requests": _load_request_tools,
}

_TOOL_GROUPS: Dict[str, str] = {
    "file_delete": "filesystem",
    "file_search": "filesystem",
    "move_file": "filesystem",
    "read_file": "filesystem",
    "balance_sheets": "financial",
    "cash_flow_statements": "financial",
    "income_statements": "financial",
    "polygon_aggregates": "polygon",
    "polygon_financials": "polygon",
    "polygon_ticker_news": "polygon",
    "requests_put": "requests",
}

_DIRECT_TOOL_IMPORTS: Dict[str, tuple[str, ...]] = {
    "closest_airport": ("amadeus", "langchain_community.tools.amadeus.closest_airport"),
    "arxiv": ("arxiv", "langchain_community.tools"),
    "brave_search": ("langchain_community.tools.brave_search.tool",),
    "duckduckgo_search": ("langchain_community.tools",),
    "duckduckgo_results_json": ("langchain_community.tools",),
    "open_weather_map": ("pyowm", "langchain_community.tools", "langchain_community.utilities"),
    "reddit_search": ("praw", "langchain_community.tools", "langchain_community.utilities.reddit_search"),
    "semanticscholar": ("semanticscholar", "langchain_community.tools.semanticscholar"),
    "sleep": ("langchain_community.tools.sleep.tool",),
    "stack_exchange": ("stackapi", "langchain_community.tools", "langchain_community.utilities"),
    "tavily_search_results_json": ("langchain_community.tools",),
    "tavily_answer": ("langchain_community.tools",),
    "wikipedia": ("wikipedia", "langchain_community.tools", "langchain_community.utilities"),
    "Wikidata": ("wikibase_rest_api_client", "langchain_community.tools.wikidata.tool", "langchain_community.utilities.wikidata"),
    "yahoo_finance_news": ("yfinance", "langchain_community.tools",),
    "youtube_search": ("youtube_search", "langchain_community.tools"),
    "terminal": ("langchain_community.tools",),
}

_GROUP_IMPORTS: Dict[str, tuple[str, ...]] = {
    "filesystem": ("langchain_community.agent_toolkits",),
    "financial": ("langchain_community.agent_toolkits.financial_datasets.toolkit",),
    "polygon": ("langchain_community.agent_toolkits.polygon.toolkit", "langchain_community.utilities.polygon"),
    "requests": ("langchain_community.agent_toolkits.openapi.toolkit", "langchain_community.utilities.requests"),
}


def load_langchain_tools(requested_tool_names: Iterable[str]) -> Dict[str, object]:
    requested = {name for name in requested_tool_names if name}
    if not requested:
        return {}

    loaded: Dict[str, object] = {}
    grouped_requests: Dict[str, set[str]] = {}

    for tool_name in requested:
        if tool_name in _DIRECT_TOOL_FACTORIES:
            loaded[tool_name] = _DIRECT_TOOL_FACTORIES[tool_name]()
            continue
        group_name = _TOOL_GROUPS.get(tool_name)
        if not group_name:
            raise KeyError(f"No tool loader configured for: {tool_name}")
        grouped_requests.setdefault(group_name, set()).add(tool_name)

    for group_name, tool_names in grouped_requests.items():
        candidates = _GROUP_LOADERS[group_name]()
        for tool_name in tool_names:
            if tool_name in candidates:
                loaded[tool_name] = candidates[tool_name]

    missing = sorted(requested - set(loaded))
    if missing:
        raise KeyError(f"Unable to instantiate requested tools: {', '.join(missing)}")
    return loaded


def validate_langchain_tool_imports(requested_tool_names: Iterable[str]) -> Dict[str, Dict[str, str]]:
    requested = {name for name in requested_tool_names if name}
    validation: Dict[str, Dict[str, str]] = {}

    for tool_name in requested:
        try:
            if tool_name in _DIRECT_TOOL_IMPORTS:
                for module_name in _DIRECT_TOOL_IMPORTS[tool_name]:
                    importlib.import_module(module_name)
            else:
                group_name = _TOOL_GROUPS.get(tool_name)
                if not group_name:
                    raise KeyError(f"No tool loader configured for: {tool_name}")
                for module_name in _GROUP_IMPORTS[group_name]:
                    importlib.import_module(module_name)
            validation[tool_name] = {"status": "ok"}
        except Exception as exc:
            validation[tool_name] = {
                "status": "error",
                "type": type(exc).__name__,
                "message": str(exc),
            }
    return validation
