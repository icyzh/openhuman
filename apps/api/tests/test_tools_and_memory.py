"""Unit tests for built-in tools and memory stubs (Phase 5).

Covers the verification scenarios from the audit plan:
- Safe / unsafe calculator expressions
- Allowed / blocked URLs (SSRF protection)
- Timezone handling in get_datetime
- Memory stub behaviour with employee ID
- MCP client stub isolation
- Employee-specific tool allowlist enforcement
"""

from unittest.mock import MagicMock, patch

import pytest

# =============================================================================
# SSRF validators (pure functions — no I/O)
# =============================================================================


class TestValidateUrl:
    """_validate_url rejects internal / dangerous URLs before any network I/O."""

    def test_allows_public_https(self):
        from app.agent.tools.executor import _validate_url

        assert _validate_url("https://example.com") == ""
        assert _validate_url("https://en.wikipedia.org/wiki/Python") == ""

    def test_allows_public_http(self):
        from app.agent.tools.executor import _validate_url

        assert _validate_url("http://example.com") == ""

    def test_blocks_file_scheme(self):
        from app.agent.tools.executor import _validate_url

        result = _validate_url("file:///etc/passwd")
        assert "file" in result.lower()

    def test_blocks_ftp_scheme(self):
        from app.agent.tools.executor import _validate_url

        result = _validate_url("ftp://example.com/file")
        assert "ftp" in result.lower()

    def test_blocks_gopher_scheme(self):
        from app.agent.tools.executor import _validate_url

        result = _validate_url("gopher://localhost:70/1")
        assert "gopher" in result.lower()

    def test_blocks_no_scheme(self):
        from app.agent.tools.executor import _validate_url

        result = _validate_url("just-a-string")
        assert result != ""

    def test_blocks_no_hostname(self):
        from app.agent.tools.executor import _validate_url

        result = _validate_url("http:///path-only")
        assert result != ""

    def test_blocks_localhost(self):
        from app.agent.tools.executor import _validate_url

        result = _validate_url("http://localhost:8000/admin")
        assert "localhost" in result.lower()

    def test_blocks_loopback_ip(self):
        from app.agent.tools.executor import _validate_url

        result = _validate_url("http://127.0.0.1:8080/secret")
        assert "127.0.0.1" in result

    def test_blocks_metadata_endpoint(self):
        from app.agent.tools.executor import _validate_url

        result = _validate_url("http://169.254.169.254/latest/meta-data")
        assert "169.254.169.254" in result

    def test_blocks_private_10_net(self):
        from app.agent.tools.executor import _validate_url

        result = _validate_url("http://10.0.0.1/internal")
        assert "10.0.0.1" in result

    def test_blocks_private_192_168_net(self):
        from app.agent.tools.executor import _validate_url

        result = _validate_url("http://192.168.1.1/admin")
        assert "192.168.1.1" in result

    def test_blocks_private_172_16_net(self):
        from app.agent.tools.executor import _validate_url

        result = _validate_url("http://172.16.0.1/api")
        assert "172.16.0.1" in result

    def test_blocks_link_local(self):
        from app.agent.tools.executor import _validate_url

        result = _validate_url("http://169.254.1.1/")
        assert "169.254.1.1" in result

    def test_blocks_zero_ip(self):
        from app.agent.tools.executor import _validate_url

        result = _validate_url("http://0.0.0.0:80/")
        assert "0.0.0.0" in result

    def test_blocks_ipv6_loopback(self):
        from app.agent.tools.executor import _validate_url

        result = _validate_url("http://[::1]:8080/")
        assert "::1" in result


class TestIsPrivateHost:
    """_is_private_host resolves hostnames and checks address ranges."""

    def test_literal_ipv4_loopback(self):
        from app.agent.tools.executor import _is_private_host

        assert _is_private_host("127.0.0.1") is True

    def test_literal_ipv4_private(self):
        from app.agent.tools.executor import _is_private_host

        assert _is_private_host("10.0.0.1") is True
        assert _is_private_host("192.168.1.1") is True
        assert _is_private_host("172.16.0.1") is True

    def test_literal_ipv6_loopback(self):
        from app.agent.tools.executor import _is_private_host

        assert _is_private_host("::1") is True

    def test_literal_public_ip_passes(self):
        from app.agent.tools.executor import _is_private_host

        assert _is_private_host("8.8.8.8") is False
        assert _is_private_host("1.1.1.1") is False


# =============================================================================
# Calculator tests
# =============================================================================


class TestCalculate:
    """calculate should safely evaluate arithmetic and reject dangerous input."""

    def test_simple_addition(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "2 + 3"})
        assert result == "5"

    def test_subtraction(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "10 - 7"})
        assert result == "3"

    def test_multiplication(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "4 * 5"})
        assert result == "20"

    def test_division(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "10 / 4"})
        assert result == "2.5"

    def test_power(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "2 ** 10"})
        assert result == "1024"

    def test_compound_expression(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "2 + 3 * 4 - 6 / 2"})
        assert result == "11.0"

    def test_parentheses(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "(2 + 3) * 4"})
        assert result == "20"

    def test_unary_minus(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "-5 + 3"})
        assert result == "-2"

    def test_float_numbers(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "3.14 * 2"})
        assert result == "6.28"

    # --- unsafe expressions --------------------------------------------------

    def test_rejects_function_call(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "__import__('os').system('ls')"})
        assert "Error" in result

    def test_rejects_attribute_access(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "().__class__.__bases__[0].__subclasses__()"})
        assert "Error" in result

    def test_rejects_name_access(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "open('/etc/passwd')"})
        assert "Error" in result

    def test_rejects_boolean_ops(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "1 and 2"})
        assert "Error" in result

    def test_rejects_comparisons(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "1 < 2"})
        assert "Error" in result

    def test_rejects_lambda(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "(lambda x: x)(1)"})
        assert "Error" in result

    def test_rejects_comprehension(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "[x for x in range(10)]"})
        assert "Error" in result

    def test_rejects_assignment(self):
        from app.agent.tools.executor import calculate

        result = calculate.invoke({"expression": "x = 1"})
        assert "Error" in result


# =============================================================================
# get_datetime tests
# =============================================================================


class TestGetDateTime:
    """get_datetime should honour valid timezone names and fall back to UTC."""

    def test_default_utc(self):
        from app.agent.tools.executor import get_datetime

        result = get_datetime.invoke({})
        assert "UTC" in result
        assert "Current date and time:" in result

    def test_explicit_utc(self):
        from app.agent.tools.executor import get_datetime

        result = get_datetime.invoke({"timezone": "UTC"})
        assert "UTC" in result

    def test_valid_timezone(self):
        from app.agent.tools.executor import get_datetime

        result = get_datetime.invoke({"timezone": "America/New_York"})
        assert "America/New_York" in result
        assert "Current date and time:" in result

    def test_another_valid_timezone(self):
        from app.agent.tools.executor import get_datetime

        result = get_datetime.invoke({"timezone": "Asia/Tokyo"})
        assert "Asia/Tokyo" in result

    def test_invalid_timezone_falls_back_to_utc(self):
        from app.agent.tools.executor import get_datetime

        result = get_datetime.invoke({"timezone": "Mars/Olympus"})
        assert "UTC" in result
        assert "Current date and time:" in result

    def test_nonsense_timezone_falls_back(self):
        from app.agent.tools.executor import get_datetime

        result = get_datetime.invoke({"timezone": "not-a-real-timezone"})
        assert "UTC" in result


# =============================================================================
# fetch_url SSRF tests (no network)
# =============================================================================


class TestFetchUrlSsrF:
    """fetch_url must reject internal / dangerous URLs before making requests."""

    @pytest.mark.anyio
    async def test_blocks_file_url(self):
        from app.agent.tools.executor import fetch_url

        result = await fetch_url.ainvoke({"url": "file:///etc/passwd"})
        assert "Cannot fetch URL" in result

    @pytest.mark.anyio
    async def test_blocks_localhost(self):
        from app.agent.tools.executor import fetch_url

        result = await fetch_url.ainvoke({"url": "http://localhost:8000/secret"})
        assert "Cannot fetch URL" in result

    @pytest.mark.anyio
    async def test_blocks_loopback_ip(self):
        from app.agent.tools.executor import fetch_url

        result = await fetch_url.ainvoke({"url": "http://127.0.0.1/api"})
        assert "Cannot fetch URL" in result

    @pytest.mark.anyio
    async def test_blocks_private_10_net(self):
        from app.agent.tools.executor import fetch_url

        result = await fetch_url.ainvoke({"url": "http://10.0.0.1/internal"})
        assert "Cannot fetch URL" in result

    @pytest.mark.anyio
    async def test_blocks_192_168_net(self):
        from app.agent.tools.executor import fetch_url

        result = await fetch_url.ainvoke({"url": "http://192.168.1.1/admin"})
        assert "Cannot fetch URL" in result

    @pytest.mark.anyio
    async def test_blocks_metadata_endpoint(self):
        from app.agent.tools.executor import fetch_url

        result = await fetch_url.ainvoke(
            {"url": "http://169.254.169.254/latest/meta-data"}
        )
        assert "Cannot fetch URL" in result


# =============================================================================
# Memory stub tests
# =============================================================================


class TestSearchMemory:
    """search_memory is a clearly marked mock / deferred stub."""

    @pytest.mark.anyio
    async def test_returns_no_results_for_unknown(self):
        from app.agent.tools.executor import search_memory

        result = await search_memory.ainvoke({"query": "sprint deadline"})
        assert "No relevant memory found" in result

    @pytest.mark.anyio
    async def test_includes_employee_id_when_present(self):
        from app.agent.tools.executor import search_memory

        result = await search_memory.ainvoke(
            {"query": "policy"},
            config={"configurable": {"employee_id": "emp-42"}},
        )
        assert "emp-42" in result

    @pytest.mark.anyio
    async def test_shows_unknown_when_no_employee_id(self):
        from app.agent.tools.executor import search_memory

        result = await search_memory.ainvoke(
            {"query": "policy"},
            config={"configurable": {}},
        )
        assert "unknown" in result.lower()

    @pytest.mark.anyio
    async def test_no_config_at_all(self):
        from app.agent.tools.executor import search_memory

        result = await search_memory.ainvoke({"query": "policy"})
        assert "unknown" in result.lower()


class TestIngestMemory:
    """ingest_memory is a clearly marked mock / deferred stub."""

    @pytest.mark.anyio
    async def test_returns_success_message(self):
        from app.agent.tools.executor import ingest_memory

        result = await ingest_memory.ainvoke({"content": "deadline is Friday"})
        assert "Fact successfully remembered" in result

    @pytest.mark.anyio
    async def test_includes_employee_id(self):
        from app.agent.tools.executor import ingest_memory

        result = await ingest_memory.ainvoke(
            {"content": "important fact"},
            config={"configurable": {"employee_id": "emp-7"}},
        )
        assert "emp-7" in result


# =============================================================================
# MCP client stub tests
# =============================================================================


class TestMcpClient:
    """MCP client is a clearly isolated stub."""

    @pytest.mark.anyio
    async def test_connect_returns_empty_list(self):
        from app.agent.tools.mcp_client import MCPClientManager

        mgr = MCPClientManager()
        tools = await mgr.connect([])
        assert tools == []

    @pytest.mark.anyio
    async def test_connect_always_returns_empty(self):
        from app.agent.tools.mcp_client import MCPClientManager

        mgr = MCPClientManager()
        tools = await mgr.connect(
            [{"server": "github", "token": "fake"}]
        )
        assert tools == []

    @pytest.mark.anyio
    async def test_disconnect_does_not_raise(self):
        from app.agent.tools.mcp_client import MCPClientManager

        mgr = MCPClientManager()
        # Should not raise
        await mgr.disconnect()


# =============================================================================
# Employee tool allowlist tests
# =============================================================================


class TestEmployeeToolAllowlist:
    """llm_call_node must bind only the template-allowed tools for each employee."""

    def test_tool_names_match_templates(self):
        """All tool names referenced in templates must exist in BUILT_IN_TOOLS."""
        from app.agent.tools import BUILT_IN_TOOLS
        from app.employees.templates import TEMPLATES

        built_in_names = {t.name for t in BUILT_IN_TOOLS}

        for slug, template in TEMPLATES.items():
            for tool_name in template.allowed_tools:
                assert tool_name in built_in_names, (
                    f"Template '{slug}' references tool '{tool_name}' "
                    f"which is not in BUILT_IN_TOOLS: {built_in_names}"
                )

    def test_hr_template_has_restricted_tools(self):
        """HR template must NOT include all built-in tools (no escalation)."""
        from app.agent.tools import BUILT_IN_TOOLS
        from app.employees.templates import HR_TEMPLATE

        all_names = {t.name for t in BUILT_IN_TOOLS}
        hr_tools = set(HR_TEMPLATE.allowed_tools)
        # HR should have a subset, not the full set
        assert hr_tools.issubset(all_names)
        assert hr_tools != all_names, (
            "HR template should not grant all tools — violates least privilege"
        )

    def test_sales_template_has_restricted_tools(self):
        from app.agent.tools import BUILT_IN_TOOLS
        from app.employees.templates import SALES_TEMPLATE

        all_names = {t.name for t in BUILT_IN_TOOLS}
        sales_tools = set(SALES_TEMPLATE.allowed_tools)
        assert sales_tools.issubset(all_names)
        assert sales_tools != all_names

    def test_support_template_has_restricted_tools(self):
        from app.agent.tools import BUILT_IN_TOOLS
        from app.employees.templates import SUPPORT_TEMPLATE

        all_names = {t.name for t in BUILT_IN_TOOLS}
        support_tools = set(SUPPORT_TEMPLATE.allowed_tools)
        assert support_tools.issubset(all_names)
        assert support_tools != all_names

    def test_general_template_may_have_all_tools(self):
        """General assistant may have the full tool set — it's the fallback."""
        from app.agent.tools import BUILT_IN_TOOLS
        from app.employees.templates import GENERAL_TEMPLATE

        all_names = {t.name for t in BUILT_IN_TOOLS}
        general_tools = set(GENERAL_TEMPLATE.allowed_tools)
        assert general_tools == all_names, (
            "General template should have access to all built-in tools"
        )


# =============================================================================
# search_web tests (mocked — no real network)
# =============================================================================


class TestSearchWeb:
    """search_web should handle results and failures gracefully."""

    def test_formats_results(self):
        from app.agent.tools.executor import search_web

        mock_results = [
            {
                "title": "Python Programming",
                "body": "Python is a high-level language.",
                "href": "https://python.org",
            },
            {
                "title": "Learn Python",
                "body": "Tutorials and guides.",
                "href": "https://learnpython.com",
            },
        ]
        with patch(
            "app.agent.tools.executor.DDGS"
        ) as mock_ddgs:
            mock_instance = MagicMock()
            mock_instance.text.return_value = mock_results
            mock_ddgs.return_value.__enter__.return_value = mock_instance

            # search_web is sync-wrapped as langchain tool, invoke runs the
            # async function inside the tool's event-loop handling
            import asyncio
            result = asyncio.run(search_web.ainvoke({"query": "python"}))

        assert "Python Programming" in result
        assert "python.org" in result

    def test_no_results(self):
        from app.agent.tools.executor import search_web

        with patch(
            "app.agent.tools.executor.DDGS"
        ) as mock_ddgs:
            mock_instance = MagicMock()
            mock_instance.text.return_value = []
            mock_ddgs.return_value.__enter__.return_value = mock_instance

            import asyncio
            result = asyncio.run(search_web.ainvoke({"query": "xyznonexistent"}))
        assert result == "No results found."

    def test_search_error_handled(self):
        from app.agent.tools.executor import search_web

        with patch(
            "app.agent.tools.executor.DDGS",
            side_effect=RuntimeError("network error"),
        ):
            import asyncio
            result = asyncio.run(search_web.ainvoke({"query": "test"}))
        assert "Error performing web search" in result


# =============================================================================
# Tool list sanity checks
# =============================================================================


class TestBuiltInTools:
    """BUILT_IN_TOOLS list must contain the expected tools."""

    def test_contains_all_six_tools(self):
        from app.agent.tools import BUILT_IN_TOOLS

        names = {t.name for t in BUILT_IN_TOOLS}
        expected = {
            "search_web",
            "get_datetime",
            "calculate",
            "fetch_url",
            "search_memory",
            "ingest_memory",
        }
        assert names == expected

    def test_tool_names_are_unique(self):
        from app.agent.tools import BUILT_IN_TOOLS

        names = [t.name for t in BUILT_IN_TOOLS]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"

    def test_memory_tools_are_last(self):
        """Memory tools appear last — convention for deferred implementations."""
        from app.agent.tools import BUILT_IN_TOOLS

        names = [t.name for t in BUILT_IN_TOOLS]
        assert names[-2:] == ["search_memory", "ingest_memory"]
