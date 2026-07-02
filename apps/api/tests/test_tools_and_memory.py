"""Unit tests for built-in tools, MCP client, and memory stubs.

Covers the verification scenarios from the audit plan:
- Safe / unsafe calculator expressions
- Allowed / blocked URLs (SSRF protection)
- Timezone handling in get_datetime
- Memory stub behaviour with employee ID
- MCP client manager (real implementation)
- MCP connector registry integrity
- Employee-specific tool allowlist enforcement (built-in + MCP)
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
    """search_memory tool tests."""

    @pytest.mark.anyio
    async def test_returns_no_results_for_unknown(self):
        from unittest.mock import AsyncMock, MagicMock
        from uuid import uuid4
        from app.agent.tools.executor import search_memory
        
        emp_uuid = uuid4()
        mock_emp = MagicMock()
        mock_emp.org_id = uuid4()
        mock_emp.cognee_dataset_name = "test_dataset"
        mock_emp.cognee_user_id = "user_1"
        
        mock_db = AsyncMock()
        mock_db.scalar.side_effect = [mock_emp, None]
        
        with patch("app.agent.tools.executor.recall", new_callable=AsyncMock) as mock_recall:
            mock_recall.return_value = []
            
            result = await search_memory.ainvoke(
                {"query": "sprint deadline"},
                config={"configurable": {"employee_id": str(emp_uuid), "db": mock_db}}
            )
            assert "No relevant memory found" in result

    @pytest.mark.anyio
    async def test_includes_employee_id_when_present(self):
        from unittest.mock import AsyncMock, MagicMock
        from uuid import uuid4
        from app.agent.tools.executor import search_memory

        emp_uuid = uuid4()
        mock_emp = MagicMock()
        mock_emp.org_id = uuid4()
        mock_emp.cognee_dataset_name = "test_dataset"
        mock_emp.cognee_user_id = "user_1"

        mock_db = AsyncMock()
        mock_db.scalar.side_effect = [mock_emp, None]

        with patch("app.agent.tools.executor.recall", new_callable=AsyncMock) as mock_recall:
            mock_recall.return_value = [{"dataset_name": "test_dataset", "text": f"some fact about {emp_uuid}"}]

            result = await search_memory.ainvoke(
                {"query": "policy"},
                config={"configurable": {"employee_id": str(emp_uuid), "db": mock_db}},
            )
            assert str(emp_uuid) in result

    @pytest.mark.anyio
    async def test_shows_unknown_when_no_employee_id(self):
        from app.agent.tools.executor import search_memory

        result = await search_memory.ainvoke(
            {"query": "policy"},
            config={"configurable": {}},
        )
        assert "unavailable" in result.lower()

    @pytest.mark.anyio
    async def test_no_config_at_all(self):
        from app.agent.tools.executor import search_memory

        result = await search_memory.ainvoke({"query": "policy"})
        assert "unavailable" in result.lower()


class TestIngestMemory:
    """ingest_memory tool tests."""

    @pytest.mark.anyio
    async def test_returns_success_message(self):
        from unittest.mock import AsyncMock, MagicMock
        from uuid import uuid4
        from app.agent.tools.executor import ingest_memory

        emp_uuid = uuid4()
        mock_emp = MagicMock()
        mock_emp.org_id = uuid4()
        mock_emp.cognee_dataset_name = "test_dataset"
        mock_emp.cognee_user_id = "user_1"

        mock_db = AsyncMock()
        mock_db.scalar.side_effect = [mock_emp, None]

        with patch("app.agent.tools.executor.remember", new_callable=AsyncMock) as mock_remember:
            mock_remember.return_value = None

            result = await ingest_memory.ainvoke(
                {"content": "deadline is Friday"},
                config={"configurable": {"employee_id": str(emp_uuid), "db": mock_db}}
            )
            assert "successfully remembered" in result.lower()

    @pytest.mark.anyio
    async def test_includes_employee_id(self):
        from unittest.mock import AsyncMock, MagicMock
        from uuid import uuid4
        from app.agent.tools.executor import ingest_memory

        emp_uuid = uuid4()
        mock_emp = MagicMock()
        mock_emp.org_id = uuid4()
        mock_emp.cognee_dataset_name = "test_dataset"
        mock_emp.cognee_user_id = "user_1"

        mock_db = AsyncMock()
        mock_db.scalar.side_effect = [mock_emp, None]

        with patch("app.agent.tools.executor.remember", new_callable=AsyncMock) as mock_remember:
            mock_remember.return_value = None

            result = await ingest_memory.ainvoke(
                {"content": "important fact"},
                config={"configurable": {"employee_id": str(emp_uuid), "db": mock_db}},
            )
            assert "successfully remembered" in result.lower()


# =============================================================================
# MCP client manager tests (real implementation)
# =============================================================================


class TestMcpClientManager:
    """MCPClientManager tests — mock MultiServerMCPClient to verify
    tool loading, name prefixing, and error handling."""

    @pytest.mark.anyio
    async def test_connect_with_no_connections_returns_empty(self):
        from app.agent.tools.mcp.client import MCPClientManager

        mgr = MCPClientManager()
        tools = await mgr.connect([])
        assert tools == []

    @pytest.mark.anyio
    async def test_disconnect_does_not_raise(self):
        from app.agent.tools.mcp.client import MCPClientManager

        mgr = MCPClientManager()
        await mgr.disconnect()  # Should not raise

    @pytest.mark.anyio
    async def test_connect_loads_and_prefixes_tools(self):
        """When MultiServerMCPClient returns tools, they get the mcp__ prefix."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from langchain_core.tools import tool as lc_tool

        from app.agent.tools.mcp.client import MCPClientManager, ResolvedConnection
        from app.agent.tools.mcp.connectors.registry import ConnectorSpec

        @lc_tool
        def list_repos() -> str:
            """List repos."""
            return "repo1, repo2"

        @lc_tool
        def search_code(query: str) -> str:
            """Search code."""
            return f"results for {query}"

        spec = ConnectorSpec(
            slug="github",
            name="GitHub",
            description="GitHub MCP",
            base_url="https://api.githubcopilot.com/mcp/",
            transport="streamable_http",
            auth_type="pat_bearer",
        )

        # Mock MultiServerMCPClient to return our tools per server
        with patch(
            "app.agent.tools.mcp.client.MultiServerMCPClient"
        ) as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.get_tools = AsyncMock(
                side_effect=lambda server_name: {
                    "github": [list_repos],
                }.get(server_name, [])
            )
            mock_client_cls.return_value = mock_instance

            mgr = MCPClientManager()
            tools = await mgr.connect([
                ResolvedConnection(slug="github", connector=spec, credentials="ghp_test"),
            ])

        # Should have 1 tool from our mock
        assert len(tools) == 1
        # Tool name should be prefixed: mcp__github__list_repos
        assert tools[0].name == "mcp__github__list_repos"

    @pytest.mark.anyio
    async def test_connect_multiple_servers_prefixes_correctly(self):
        """Tools from different servers get different mcp__{slug} prefixes."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from langchain_core.tools import tool as lc_tool

        from app.agent.tools.mcp.client import MCPClientManager, ResolvedConnection
        from app.agent.tools.mcp.connectors.registry import ConnectorSpec

        @lc_tool
        def search(query: str) -> str:
            """Search the web."""
            return f"web: {query}"

        github_spec = ConnectorSpec(
            slug="github",
            name="GitHub",
            description="GitHub MCP",
            base_url="https://api.githubcopilot.com/mcp/",
            transport="streamable_http",
            auth_type="pat_bearer",
        )
        web_spec = ConnectorSpec(
            slug="web_search",
            name="Web Search",
            description="Free web search",
            base_url="https://search.example.com/mcp",
            transport="streamable_http",
            auth_type="none",
        )

        with patch(
            "app.agent.tools.mcp.client.MultiServerMCPClient"
        ) as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.get_tools = AsyncMock(
                side_effect=lambda server_name: {
                    "github": [search],
                    "web_search": [search],
                }.get(server_name, [])
            )
            mock_client_cls.return_value = mock_instance

            mgr = MCPClientManager()
            tools = await mgr.connect([
                ResolvedConnection(slug="github", connector=github_spec, credentials="ghp_test"),
                ResolvedConnection(slug="web_search", connector=web_spec, credentials=None),
            ])

        assert len(tools) == 2
        tool_names = {t.name for t in tools}
        assert "mcp__github__search" in tool_names
        assert "mcp__web_search__search" in tool_names
        # No name collision despite same underlying tool name
        assert len(tool_names) == 2

    @pytest.mark.anyio
    async def test_error_per_server_is_graceful(self):
        """When one server fails, others still load successfully."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from langchain_core.tools import tool as lc_tool

        from app.agent.tools.mcp.client import MCPClientManager, ResolvedConnection
        from app.agent.tools.mcp.connectors.registry import ConnectorSpec

        @lc_tool
        def search(query: str) -> str:
            """Search."""
            return f"results: {query}"

        good_spec = ConnectorSpec(
            slug="good",
            name="Good",
            description="Works",
            base_url="https://good.example.com/mcp",
            transport="streamable_http",
            auth_type="none",
        )
        bad_spec = ConnectorSpec(
            slug="bad",
            name="Bad",
            description="Fails",
            base_url="https://bad.example.com/mcp",
            transport="streamable_http",
            auth_type="none",
        )

        with patch(
            "app.agent.tools.mcp.client.MultiServerMCPClient"
        ) as mock_client_cls:
            mock_instance = MagicMock()
            mock_instance.get_tools = AsyncMock(
                side_effect=lambda server_name: (
                    [search] if server_name == "good"
                    else (_ for _ in ()).throw(RuntimeError("connection refused"))
                )
            )
            mock_client_cls.return_value = mock_instance

            mgr = MCPClientManager()
            tools = await mgr.connect([
                ResolvedConnection(slug="good", connector=good_spec, credentials=None),
                ResolvedConnection(slug="bad", connector=bad_spec, credentials=None),
            ])

        # Good server loaded, bad one skipped
        assert len(tools) == 1
        assert tools[0].name == "mcp__good__search"

    @pytest.mark.anyio
    async def test_connect_skips_unknown_connector(self):
        """When a connection references a slug not in REGISTRY, it is skipped."""
        from app.agent.tools.mcp.client import MCPClientManager, ResolvedConnection
        from app.agent.tools.mcp.connectors.registry import ConnectorSpec

        # This spec is NOT in REGISTRY
        unknown_spec = ConnectorSpec(
            slug="unknown",
            name="Unknown",
            description="Not registered",
            base_url="https://unknown.example.com/mcp",
        )

        mgr = MCPClientManager()
        tools = await mgr.connect([
            ResolvedConnection(slug="unknown", connector=unknown_spec, credentials=None),
        ])

        # Should still resolve (the manager doesn't check REGISTRY — that's
        # the router's job). This test verifies we don't crash on any valid
        # ConnectorSpec.
        assert tools == []  # No tools from a mock without patching


# =============================================================================
# MCP tool name helpers
# =============================================================================


class TestMcpToolNameHelpers:
    """_is_mcp_tool and _mcp_slug correctly parse mcp__{slug}__{tool} names."""

    def test_is_mcp_tool_true_for_prefixed(self):
        from app.agent.nodes.llm_call import _is_mcp_tool

        class _FakeTool:
            name = "mcp__github__list_repos"

        assert _is_mcp_tool(_FakeTool()) is True

    def test_is_mcp_tool_false_for_builtin(self):
        from app.agent.nodes.llm_call import _is_mcp_tool

        class _FakeTool:
            name = "search_web"

        assert _is_mcp_tool(_FakeTool()) is False

    def test_is_mcp_tool_false_for_no_prefix(self):
        from app.agent.nodes.llm_call import _is_mcp_tool

        class _FakeTool:
            name = "github__list_repos"

        assert _is_mcp_tool(_FakeTool()) is False

    def test_mcp_slug_extracts_correctly(self):
        from app.agent.nodes.llm_call import _mcp_slug

        class _FakeTool:
            name = "mcp__github__list_repos"

        assert _mcp_slug(_FakeTool()) == "github"

    def test_mcp_slug_with_multisection_tool_name(self):
        from app.agent.nodes.llm_call import _mcp_slug

        class _FakeTool:
            name = "mcp__web_search__fetch_page"

        assert _mcp_slug(_FakeTool()) == "web_search"

    def test_mcp_slug_empty_for_non_mcp(self):
        from app.agent.nodes.llm_call import _mcp_slug

        class _FakeTool:
            name = "search_web"

        assert _mcp_slug(_FakeTool()) == ""

    def test_mcp_slug_empty_for_too_short(self):
        from app.agent.nodes.llm_call import _mcp_slug

        class _FakeTool:
            name = "mcp__only"

        assert _mcp_slug(_FakeTool()) == ""


# =============================================================================
# Connector registry tests
# =============================================================================


class TestConnectorRegistry:
    """ConnectorSpec and REGISTRY are well-formed."""

    def test_registry_is_dict(self):
        from app.agent.tools.mcp.connectors import REGISTRY

        assert isinstance(REGISTRY, dict)

    def test_connector_spec_validation(self):
        from app.agent.tools.mcp.connectors.registry import ConnectorSpec

        spec = ConnectorSpec(
            slug="test",
            name="Test Connector",
            description="A test connector",
            base_url="https://test.example.com/mcp",
            auth_type="none",
        )
        assert spec.slug == "test"
        assert spec.transport == "streamable_http"
        assert spec.auth_type == "none"
        assert spec.default_scopes == []

    def test_connector_spec_auth_types(self):
        from app.agent.tools.mcp.connectors.registry import ConnectorSpec

        for auth in ("none", "api_key_header", "pat_bearer", "oauth2"):
            spec = ConnectorSpec(
                slug="test",
                name="Test",
                description="Test",
                base_url="https://test.example.com/mcp",
                auth_type=auth,  # type: ignore[arg-type]
            )
            assert spec.auth_type == auth



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
        assert general_tools == all_names - {"escalate_to_human", "escalate_to_human_interactive"}, (
            "General template should have access to all built-in tools except escalation"
        )


class TestEmployeeMcpAllowlist:
    """MCP server allowlist on EmployeeTemplate gates MCP tool binding."""

    def test_default_templates_have_empty_mcp_allowlist(self):
        """HR template keeps no MCP servers; others allow free web_search in Phase 1."""
        from app.employees.templates import TEMPLATES

        for slug, template in TEMPLATES.items():
            assert isinstance(template.allowed_mcp_servers, list), (
                f"Template '{slug}' allowed_mcp_servers must be a list"
            )
        # HR template remains the most restricted — no MCP servers
        assert TEMPLATES["hr_specialist"].allowed_mcp_servers == [], (
            "HR template should have empty allowed_mcp_servers"
        )
        # Phase 1: general, sales, and support get the free web_search MCP
        for slug in ("general", "sales_rep", "support_agent"):
            assert "web_search" in TEMPLATES[slug].allowed_mcp_servers, (
                f"Template '{slug}' should allow web_search in Phase 1"
            )

    def test_can_set_wildcard_mcp_allowlist(self):
        """allowed_mcp_servers=["*"] should be a valid config."""
        from app.employees.templates import EmployeeTemplate

        tmpl = EmployeeTemplate(
            name="Test",
            role="Test",
            system_prompt_template="You are a test.",
            allowed_tools=["search_web"],
            allowed_mcp_servers=["*"],
        )
        assert tmpl.allowed_mcp_servers == ["*"]

    def test_can_set_specific_mcp_servers(self):
        """allowed_mcp_servers can list specific slugs."""
        from app.employees.templates import EmployeeTemplate

        tmpl = EmployeeTemplate(
            name="Test",
            role="Test",
            system_prompt_template="You are a test.",
            allowed_tools=["search_web"],
            allowed_mcp_servers=["github", "web_search"],
        )
        assert tmpl.allowed_mcp_servers == ["github", "web_search"]


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

    def test_contains_expected_tools(self):
        from app.agent.tools import BUILT_IN_TOOLS

        names = {t.name for t in BUILT_IN_TOOLS}
        expected = {
            "search_web",
            "get_datetime",
            "calculate",
            "fetch_url",
            "search_memory",
            "ingest_memory",
            "check_background_task",
            "cancel_background_task",
            "escalate_to_human",
            "escalate_to_human_interactive",
        }
        assert names == expected

    def test_tool_names_are_unique(self):
        from app.agent.tools import BUILT_IN_TOOLS

        names = [t.name for t in BUILT_IN_TOOLS]
        assert len(names) == len(set(names)), f"Duplicate tool names: {names}"

    def test_memory_tools_exist(self):
        """Memory tools exist in BUILT_IN_TOOLS."""
        from app.agent.tools import BUILT_IN_TOOLS

        names = [t.name for t in BUILT_IN_TOOLS]
        assert "search_memory" in names
        assert "ingest_memory" in names
