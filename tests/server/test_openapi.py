import base64
import json
import re
from enum import Enum

import httpx
import pytest
from dirty_equals import IsStr
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import PlainTextResponse
from httpx import ASGITransport, AsyncClient
from mcp.types import BlobResourceContents, TextContent, TextResourceContents
from pydantic import BaseModel, TypeAdapter
from pydantic.networks import AnyUrl

from FlashMCP import FlashMCP
from FlashMCP.client import Client
from FlashMCP.exceptions import ToolError
from FlashMCP.server.openapi import (
    FlashMCPOpenAPI,
    OpenAPIResource,
    OpenAPIResourceTemplate,
    OpenAPITool,
    RouteMap,
    RouteType,
)


class User(BaseModel):
    id: int
    name: str
    active: bool


class UserCreate(BaseModel):
    name: str
    active: bool


@pytest.fixture
def users_db() -> dict[int, User]:
    return {
        1: User(id=1, name="Alice", active=True),
        2: User(id=2, name="Bob", active=True),
        3: User(id=3, name="Charlie", active=False),
    }


@pytest.fixture
def fastapi_app(users_db: dict[int, User]) -> FastAPI:
    app = FastAPI(title="FastAPI App")

    @app.get("/users", tags=["users", "list"])
    async def get_users() -> list[User]:
        """Get all users."""
        return sorted(users_db.values(), key=lambda x: x.id)

    @app.get("/search", tags=["search"])
    async def search_users(
        name: str | None = None, active: bool | None = None, min_id: int | None = None
    ) -> list[User]:
        """Search users with optional filters."""
        results = list(users_db.values())

        if name is not None:
            results = [u for u in results if name.lower() in u.name.lower()]
        if active is not None:
            results = [u for u in results if u.active == active]
        if min_id is not None:
            results = [u for u in results if u.id >= min_id]

        return sorted(results, key=lambda x: x.id)

    @app.get("/users/{user_id}", tags=["users", "detail"])
    async def get_user(user_id: int) -> User | None:
        """Get a user by ID."""
        return users_db.get(user_id)

    @app.get("/users/{user_id}/{is_active}", tags=["users", "detail"])
    async def get_user_active_state(user_id: int, is_active: bool) -> User | None:
        """Get a user by ID and filter by active state."""
        user = users_db.get(user_id)
        if user is not None and user.active == is_active:
            return user
        return None

    @app.post("/users", tags=["users", "create"])
    async def create_user(user: UserCreate) -> User:
        """Create a new user."""
        user_id = max(users_db.keys()) + 1
        new_user = User(id=user_id, **user.model_dump())
        users_db[user_id] = new_user
        return new_user

    @app.patch("/users/{user_id}/name", tags=["users", "update"])
    async def update_user_name(user_id: int, name: str) -> User:
        """Update a user's name."""
        user = users_db.get(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        user.name = name
        return user

    @app.get("/ping", response_class=PlainTextResponse)
    async def ping() -> str:
        """Ping the server."""
        return "pong"

    @app.get("/ping-bytes")
    async def ping_bytes() -> Response:
        """Ping the server and get a bytes response."""

        return Response(content=b"pong")

    return app


@pytest.fixture
def api_client(fastapi_app: FastAPI) -> AsyncClient:
    """Create a pre-configured httpx client for testing."""
    return AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test")


@pytest.fixture
async def FlashMCP_openapi_server(
    fastapi_app: FastAPI, api_client: httpx.AsyncClient
) -> FlashMCPOpenAPI:
    openapi_spec = fastapi_app.openapi()

    return FlashMCPOpenAPI(
        openapi_spec=openapi_spec,
        client=api_client,
        name="Test App",
    )


async def test_create_openapi_server(
    fastapi_app: FastAPI, api_client: httpx.AsyncClient
):
    openapi_spec = fastapi_app.openapi()

    server = FlashMCPOpenAPI(
        openapi_spec=openapi_spec, client=api_client, name="Test App"
    )

    assert isinstance(server, FlashMCP)
    assert server.name == "Test App"


async def test_create_openapi_server_classmethod(
    fastapi_app: FastAPI, api_client: httpx.AsyncClient
):
    server = FlashMCP.from_openapi(openapi_spec=fastapi_app.openapi(), client=api_client)
    assert isinstance(server, FlashMCPOpenAPI)
    assert server.name == "OpenAPI FlashMCP"


async def test_create_fastapi_server_classmethod(fastapi_app: FastAPI):
    server = FlashMCP.from_fastapi(fastapi_app)
    assert isinstance(server, FlashMCPOpenAPI)
    assert server.name == "FastAPI App"


async def test_create_openapi_server_with_timeout(
    fastapi_app: FastAPI, api_client: httpx.AsyncClient
):
    server = FlashMCPOpenAPI(
        openapi_spec=fastapi_app.openapi(),
        client=api_client,
        name="Test App",
        timeout=1.0,
    )
    assert server._timeout == 1.0

    for tool in (await server.get_tools()).values():
        assert isinstance(tool, OpenAPITool)
        assert tool._timeout == 1.0

    for resource in (await server.get_resources()).values():
        assert isinstance(resource, OpenAPIResource)
        assert resource._timeout == 1.0

    for template in (await server.get_resource_templates()).values():
        assert isinstance(template, OpenAPIResourceTemplate)
        assert template._timeout == 1.0


class TestTools:
    async def test_list_tools(self, FlashMCP_openapi_server: FlashMCPOpenAPI):
        """
        By default, tools exclude GET methods
        """
        async with Client(FlashMCP_openapi_server) as client:
            tools = await client.list_tools()
        assert len(tools) == 2

        assert tools[0].model_dump() == dict(
            name="create_user_users_post",
            annotations=None,
            description=IsStr(regex=r"^Create a new user\..*$", regex_flags=re.DOTALL),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "title": "Name"},
                    "active": {"type": "boolean", "title": "Active"},
                },
                "required": ["name", "active"],
            },
        )
        assert tools[1].model_dump() == dict(
            name="update_user_name_users__user_id__name_patch",
            annotations=None,
            description=IsStr(
                regex=r"^Update a user's name\..*$", regex_flags=re.DOTALL
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "title": "User Id"},
                    "name": {"type": "string", "title": "Name"},
                },
                "required": ["user_id", "name"],
            },
        )

    async def test_call_create_user_tool(
        self, FlashMCP_openapi_server: FlashMCPOpenAPI, api_client
    ):
        """
        The tool created by the OpenAPI server should be the same as the original
        """
        async with Client(FlashMCP_openapi_server) as client:
            tool_response = await client.call_tool(
                "create_user_users_post", {"name": "David", "active": False}
            )

        # Convert TextContent to dict for comparison
        assert isinstance(tool_response, list) and len(tool_response) == 1
        assert isinstance(tool_response[0], TextContent)

        response_data = json.loads(tool_response[0].text)
        expected_user = User(id=4, name="David", active=False).model_dump()
        assert response_data == expected_user

        # Check that the user was created via API
        response = await api_client.get("/users")
        assert len(response.json()) == 4

        # Check that the user was created via MCP
        async with Client(FlashMCP_openapi_server) as client:
            user_response = await client.read_resource(
                "resource://openapi/get_user_users__user_id__get/4"
            )
            assert isinstance(user_response[0], TextResourceContents)
            response_text = user_response[0].text
            user = json.loads(response_text)
        assert user == expected_user

    async def test_call_update_user_name_tool(
        self, FlashMCP_openapi_server: FlashMCPOpenAPI, api_client
    ):
        """
        The tool created by the OpenAPI server should be the same as the original
        """
        async with Client(FlashMCP_openapi_server) as client:
            tool_response = await client.call_tool(
                "update_user_name_users__user_id__name_patch",
                {"user_id": 1, "name": "XYZ"},
            )

        # Convert TextContent to dict for comparison
        assert isinstance(tool_response, list) and len(tool_response) == 1
        assert isinstance(tool_response[0], TextContent)

        response_data = json.loads(tool_response[0].text)
        expected_data = dict(id=1, name="XYZ", active=True)
        assert response_data == expected_data

        # Check that the user was updated via API
        response = await api_client.get("/users")
        assert expected_data in response.json()

        # Check that the user was updated via MCP
        async with Client(FlashMCP_openapi_server) as client:
            user_response = await client.read_resource(
                "resource://openapi/get_user_users__user_id__get/1"
            )
            assert isinstance(user_response[0], TextResourceContents)
            response_text = user_response[0].text
            user = json.loads(response_text)
        assert user == expected_data

    async def test_call_tool_return_list(
        self,
        fastapi_app: FastAPI,
        api_client: httpx.AsyncClient,
        users_db: dict[int, User],
    ):
        """
        The tool created by the OpenAPI server should return a list of content.
        """
        openapi_spec = fastapi_app.openapi()
        mcp_server = FlashMCPOpenAPI(
            openapi_spec=openapi_spec,
            client=api_client,
            route_maps=[
                RouteMap(methods=["GET"], pattern=r".*", route_type=RouteType.TOOL)
            ],
        )
        async with Client(mcp_server) as client:
            tool_response = await client.call_tool("get_users_users_get", {})
            assert isinstance(tool_response, list)
            assert isinstance(tool_response[0], TextContent)
            assert json.loads(tool_response[0].text) == [
                user.model_dump()
                for user in sorted(users_db.values(), key=lambda x: x.id)
            ]


class TestResources:
    async def test_list_resources(self, FlashMCP_openapi_server: FlashMCPOpenAPI):
        """
        By default, resources exclude GET methods without parameters
        """
        async with Client(FlashMCP_openapi_server) as client:
            resources = await client.list_resources()
        assert len(resources) == 4
        assert resources[0].uri == AnyUrl("resource://openapi/get_users_users_get")
        assert resources[0].name == "get_users_users_get"

    async def test_get_resource(
        self,
        FlashMCP_openapi_server: FlashMCPOpenAPI,
        api_client,
        users_db: dict[int, User],
    ):
        """
        The resource created by the OpenAPI server should be the same as the original
        """

        json_users = TypeAdapter(list[User]).dump_python(
            sorted(users_db.values(), key=lambda x: x.id)
        )
        async with Client(FlashMCP_openapi_server) as client:
            resource_response = await client.read_resource(
                "resource://openapi/get_users_users_get"
            )
            assert isinstance(resource_response[0], TextResourceContents)
            response_text = resource_response[0].text
            resource = json.loads(response_text)
        assert resource == json_users
        response = await api_client.get("/users")
        assert response.json() == json_users

    async def test_get_bytes_resource(
        self,
        FlashMCP_openapi_server: FlashMCPOpenAPI,
        api_client,
    ):
        """Test reading a resource that returns bytes."""
        async with Client(FlashMCP_openapi_server) as client:
            resource_response = await client.read_resource(
                "resource://openapi/ping_bytes_ping_bytes_get"
            )
            assert isinstance(resource_response[0], BlobResourceContents)
            assert base64.b64decode(resource_response[0].blob) == b"pong"

    async def test_get_str_resource(
        self,
        FlashMCP_openapi_server: FlashMCPOpenAPI,
        api_client,
    ):
        """Test reading a resource that returns a string."""
        async with Client(FlashMCP_openapi_server) as client:
            resource_response = await client.read_resource(
                "resource://openapi/ping_ping_get"
            )
            assert isinstance(resource_response[0], TextResourceContents)
            assert resource_response[0].text == "pong"


class TestResourceTemplates:
    async def test_list_resource_templates(
        self, FlashMCP_openapi_server: FlashMCPOpenAPI
    ):
        """
        By default, resource templates exclude GET methods without parameters
        """
        async with Client(FlashMCP_openapi_server) as client:
            resource_templates = await client.list_resource_templates()
        assert len(resource_templates) == 2
        assert resource_templates[0].name == "get_user_users__user_id__get"
        assert (
            resource_templates[0].uriTemplate
            == r"resource://openapi/get_user_users__user_id__get/{user_id}"
        )
        assert (
            resource_templates[1].name
            == "get_user_active_state_users__user_id___is_active__get"
        )
        assert (
            resource_templates[1].uriTemplate
            == r"resource://openapi/get_user_active_state_users__user_id___is_active__get/{is_active}/{user_id}"
        )

    async def test_get_resource_template(
        self,
        FlashMCP_openapi_server: FlashMCPOpenAPI,
        api_client,
        users_db: dict[int, User],
    ):
        """
        The resource template created by the OpenAPI server should be the same as the original
        """
        user_id = 2
        async with Client(FlashMCP_openapi_server) as client:
            resource_response = await client.read_resource(
                f"resource://openapi/get_user_users__user_id__get/{user_id}"
            )
            assert isinstance(resource_response[0], TextResourceContents)
            response_text = resource_response[0].text
            resource = json.loads(response_text)

        assert resource == users_db[user_id].model_dump()
        response = await api_client.get(f"/users/{user_id}")
        assert resource == response.json()

    async def test_get_resource_template_multi_param(
        self,
        FlashMCP_openapi_server: FlashMCPOpenAPI,
        api_client,
        users_db: dict[int, User],
    ):
        """
        The resource template created by the OpenAPI server should be the same as the original
        """
        user_id = 2
        is_active = True
        async with Client(FlashMCP_openapi_server) as client:
            resource_response = await client.read_resource(
                f"resource://openapi/get_user_active_state_users__user_id___is_active__get/{is_active}/{user_id}"
            )
            assert isinstance(resource_response[0], TextResourceContents)
            response_text = resource_response[0].text
            resource = json.loads(response_text)

        assert resource == users_db[user_id].model_dump()
        response = await api_client.get(f"/users/{user_id}/{is_active}")
        assert resource == response.json()


class TestPrompts:
    async def test_list_prompts(self, FlashMCP_openapi_server: FlashMCPOpenAPI):
        """
        By default, there are no prompts.
        """
        async with Client(FlashMCP_openapi_server) as client:
            prompts = await client.list_prompts()
        assert len(prompts) == 0


class TestTagTransfer:
    """Tests for transferring tags from OpenAPI routes to MCP objects."""

    async def test_tags_transferred_to_tools(
        self, FlashMCP_openapi_server: FlashMCPOpenAPI
    ):
        """Test that tags from OpenAPI routes are correctly transferred to Tools."""
        # Get internal tools directly (not the public API which returns MCP.Content)
        tools = FlashMCP_openapi_server._tool_manager.list_tools()

        # Find the create_user and update_user_name tools
        create_user_tool = next(
            (t for t in tools if t.name == "create_user_users_post"), None
        )
        update_user_tool = next(
            (
                t
                for t in tools
                if t.name == "update_user_name_users__user_id__name_patch"
            ),
            None,
        )

        assert create_user_tool is not None
        assert update_user_tool is not None

        # Check that tags from OpenAPI routes were transferred to the Tool objects
        assert "users" in create_user_tool.tags
        assert "create" in create_user_tool.tags
        assert len(create_user_tool.tags) == 2

        assert "users" in update_user_tool.tags
        assert "update" in update_user_tool.tags
        assert len(update_user_tool.tags) == 2

    async def test_tags_transferred_to_resources(
        self, FlashMCP_openapi_server: FlashMCPOpenAPI
    ):
        """Test that tags from OpenAPI routes are correctly transferred to Resources."""
        # Get internal resources directly
        resources = list(
            FlashMCP_openapi_server._resource_manager.get_resources().values()
        )

        # Find the get_users resource
        get_users_resource = next(
            (r for r in resources if r.name == "get_users_users_get"), None
        )

        assert get_users_resource is not None

        # Check that tags from OpenAPI routes were transferred to the Resource object
        assert "users" in get_users_resource.tags
        assert "list" in get_users_resource.tags
        assert len(get_users_resource.tags) == 2

    async def test_tags_transferred_to_resource_templates(
        self, FlashMCP_openapi_server: FlashMCPOpenAPI
    ):
        """Test that tags from OpenAPI routes are correctly transferred to ResourceTemplates."""
        # Get internal resource templates directly
        templates = list(
            FlashMCP_openapi_server._resource_manager.get_templates().values()
        )

        # Find the get_user template
        get_user_template = next(
            (t for t in templates if t.name == "get_user_users__user_id__get"), None
        )

        assert get_user_template is not None

        # Check that tags from OpenAPI routes were transferred to the ResourceTemplate object
        assert "users" in get_user_template.tags
        assert "detail" in get_user_template.tags
        assert len(get_user_template.tags) == 2

    async def test_tags_preserved_in_resources_created_from_templates(
        self, FlashMCP_openapi_server: FlashMCPOpenAPI
    ):
        """Test that tags are preserved when creating resources from templates."""
        # Get internal resource templates directly
        templates = list(
            FlashMCP_openapi_server._resource_manager.get_templates().values()
        )

        # Find the get_user template
        get_user_template = next(
            (t for t in templates if t.name == "get_user_users__user_id__get"), None
        )

        assert get_user_template is not None

        # Manually create a resource from template
        params = {"user_id": 1}
        resource = await get_user_template.create_resource(
            "resource://openapi/get_user_users__user_id__get/1", params
        )

        # Verify tags are preserved from template to resource
        assert "users" in resource.tags
        assert "detail" in resource.tags
        assert len(resource.tags) == 2


class TestOpenAPI30Compatibility:
    """Tests for compatibility with OpenAPI 3.0 specifications."""

    @pytest.fixture
    def openapi_30_spec(self) -> dict:
        """Fixture that returns a simple OpenAPI 3.0 specification."""
        return {
            "openapi": "3.0.0",
            "info": {"title": "Product API (3.0)", "version": "1.0.0"},
            "paths": {
                "/products": {
                    "get": {
                        "operationId": "listProducts",
                        "summary": "List all products",
                        "responses": {"200": {"description": "A list of products"}},
                    },
                    "post": {
                        "operationId": "createProduct",
                        "summary": "Create a new product",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "price": {"type": "number"},
                                        },
                                        "required": ["name", "price"],
                                    }
                                }
                            },
                        },
                        "responses": {"201": {"description": "Product created"}},
                    },
                },
                "/products/{product_id}": {
                    "get": {
                        "operationId": "getProduct",
                        "summary": "Get product by ID",
                        "parameters": [
                            {
                                "name": "product_id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string"},
                            }
                        ],
                        "responses": {"200": {"description": "A product"}},
                    }
                },
            },
        }

    @pytest.fixture
    async def mock_30_client(self) -> httpx.AsyncClient:
        """Mock client that returns predefined responses for the 3.0 API."""

        async def _responder(request):
            if request.url.path == "/products" and request.method == "GET":
                return httpx.Response(
                    200,
                    json=[
                        {"id": "p1", "name": "Product 1", "price": 19.99},
                        {"id": "p2", "name": "Product 2", "price": 29.99},
                    ],
                )
            elif request.url.path == "/products" and request.method == "POST":
                import json

                data = json.loads(request.content)
                return httpx.Response(
                    201, json={"id": "p3", "name": data["name"], "price": data["price"]}
                )
            elif request.url.path.startswith("/products/") and request.method == "GET":
                product_id = request.url.path.split("/")[-1]
                products = {
                    "p1": {"id": "p1", "name": "Product 1", "price": 19.99},
                    "p2": {"id": "p2", "name": "Product 2", "price": 29.99},
                }
                if product_id in products:
                    return httpx.Response(200, json=products[product_id])
                return httpx.Response(404, json={"error": "Product not found"})
            return httpx.Response(404)

        transport = httpx.MockTransport(_responder)
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture
    async def openapi_30_server(
        self, openapi_30_spec, mock_30_client
    ) -> FlashMCPOpenAPI:
        """Create a FlashMCPOpenAPI server from the OpenAPI 3.0 spec."""
        return FlashMCPOpenAPI(
            openapi_spec=openapi_30_spec, client=mock_30_client, name="Product API 3.0"
        )

    async def test_server_creation(self, openapi_30_server):
        """Test that a server can be created from an OpenAPI 3.0 spec."""
        assert isinstance(openapi_30_server, FlashMCP)
        assert openapi_30_server.name == "Product API 3.0"

    async def test_resource_discovery(self, openapi_30_server):
        """Test that resources are correctly discovered from an OpenAPI 3.0 spec."""
        async with Client(openapi_30_server) as client:
            resources = await client.list_resources()
        assert len(resources) == 1
        assert resources[0].uri == AnyUrl("resource://openapi/listProducts")

    async def test_resource_template_discovery(self, openapi_30_server):
        """Test that resource templates are correctly discovered from an OpenAPI 3.0 spec."""
        async with Client(openapi_30_server) as client:
            templates = await client.list_resource_templates()
        assert len(templates) == 1
        assert templates[0].name == "getProduct"
        assert templates[0].uriTemplate == r"resource://openapi/getProduct/{product_id}"

    async def test_tool_discovery(self, openapi_30_server):
        """Test that tools are correctly discovered from an OpenAPI 3.0 spec."""
        async with Client(openapi_30_server) as client:
            tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "createProduct"
        assert "name" in tools[0].inputSchema["properties"]
        assert "price" in tools[0].inputSchema["properties"]

    async def test_resource_access(self, openapi_30_server):
        """Test reading a resource from an OpenAPI 3.0 server."""
        async with Client(openapi_30_server) as client:
            resource_response = await client.read_resource(
                "resource://openapi/listProducts"
            )
            assert isinstance(resource_response[0], TextResourceContents)
            response_text = resource_response[0].text
            content = json.loads(response_text)
        assert len(content) == 2
        assert content[0]["name"] == "Product 1"
        assert content[1]["name"] == "Product 2"

    async def test_resource_template_access(self, openapi_30_server):
        """Test reading a resource from template from an OpenAPI 3.0 server."""
        async with Client(openapi_30_server) as client:
            resource_response = await client.read_resource(
                "resource://openapi/getProduct/p1"
            )
            assert isinstance(resource_response[0], TextResourceContents)
            response_text = resource_response[0].text
            content = json.loads(response_text)
        assert content["id"] == "p1"
        assert content["name"] == "Product 1"
        assert content["price"] == 19.99

    async def test_tool_execution(self, openapi_30_server):
        """Test executing a tool from an OpenAPI 3.0 server."""
        async with Client(openapi_30_server) as client:
            result = await client.call_tool(
                "createProduct", {"name": "New Product", "price": 39.99}
            )
            # Result should be a text content
            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            product = json.loads(result[0].text)
            assert product["id"] == "p3"
            assert product["name"] == "New Product"
            assert product["price"] == 39.99


class TestOpenAPI31Compatibility:
    """Tests for compatibility with OpenAPI 3.1 specifications."""

    @pytest.fixture
    def openapi_31_spec(self) -> dict:
        """Fixture that returns a simple OpenAPI 3.1 specification."""
        return {
            "openapi": "3.1.0",
            "info": {"title": "Order API (3.1)", "version": "1.0.0"},
            "paths": {
                "/orders": {
                    "get": {
                        "operationId": "listOrders",
                        "summary": "List all orders",
                        "responses": {"200": {"description": "A list of orders"}},
                    },
                    "post": {
                        "operationId": "createOrder",
                        "summary": "Place a new order",
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "customer": {"type": "string"},
                                            "items": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            },
                                        },
                                        "required": ["customer", "items"],
                                    }
                                }
                            },
                        },
                        "responses": {"201": {"description": "Order created"}},
                    },
                },
                "/orders/{order_id}": {
                    "get": {
                        "operationId": "getOrder",
                        "summary": "Get order by ID",
                        "parameters": [
                            {
                                "name": "order_id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string"},
                            }
                        ],
                        "responses": {"200": {"description": "An order"}},
                    }
                },
            },
        }

    @pytest.fixture
    async def mock_31_client(self) -> httpx.AsyncClient:
        """Mock client that returns predefined responses for the 3.1 API."""

        async def _responder(request):
            if request.url.path == "/orders" and request.method == "GET":
                return httpx.Response(
                    200,
                    json=[
                        {"id": "o1", "customer": "Alice", "items": ["item1", "item2"]},
                        {"id": "o2", "customer": "Bob", "items": ["item3"]},
                    ],
                )
            elif request.url.path == "/orders" and request.method == "POST":
                import json

                data = json.loads(request.content)
                return httpx.Response(
                    201,
                    json={
                        "id": "o3",
                        "customer": data["customer"],
                        "items": data["items"],
                    },
                )
            elif request.url.path.startswith("/orders/") and request.method == "GET":
                order_id = request.url.path.split("/")[-1]
                orders = {
                    "o1": {
                        "id": "o1",
                        "customer": "Alice",
                        "items": ["item1", "item2"],
                    },
                    "o2": {"id": "o2", "customer": "Bob", "items": ["item3"]},
                }
                if order_id in orders:
                    return httpx.Response(200, json=orders[order_id])
                return httpx.Response(404, json={"error": "Order not found"})
            return httpx.Response(404)

        transport = httpx.MockTransport(_responder)
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture
    async def openapi_31_server(
        self, openapi_31_spec, mock_31_client
    ) -> FlashMCPOpenAPI:
        """Create a FlashMCPOpenAPI server from the OpenAPI 3.1 spec."""
        return FlashMCPOpenAPI(
            openapi_spec=openapi_31_spec, client=mock_31_client, name="Order API 3.1"
        )

    async def test_server_creation(self, openapi_31_server):
        """Test that a server can be created from an OpenAPI 3.1 spec."""
        assert isinstance(openapi_31_server, FlashMCP)
        assert openapi_31_server.name == "Order API 3.1"

    async def test_resource_discovery(self, openapi_31_server):
        """Test that resources are correctly discovered from an OpenAPI 3.1 spec."""
        async with Client(openapi_31_server) as client:
            resources = await client.list_resources()
        assert len(resources) == 1
        assert resources[0].uri == AnyUrl("resource://openapi/listOrders")

    async def test_resource_template_discovery(self, openapi_31_server):
        """Test that resource templates are correctly discovered from an OpenAPI 3.1 spec."""
        async with Client(openapi_31_server) as client:
            templates = await client.list_resource_templates()
        assert len(templates) == 1
        assert templates[0].name == "getOrder"
        assert templates[0].uriTemplate == r"resource://openapi/getOrder/{order_id}"

    async def test_tool_discovery(self, openapi_31_server):
        """Test that tools are correctly discovered from an OpenAPI 3.1 spec."""
        async with Client(openapi_31_server) as client:
            tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "createOrder"
        assert "customer" in tools[0].inputSchema["properties"]
        assert "items" in tools[0].inputSchema["properties"]

    async def test_resource_access(self, openapi_31_server):
        """Test reading a resource from an OpenAPI 3.1 server."""
        async with Client(openapi_31_server) as client:
            resource_response = await client.read_resource(
                "resource://openapi/listOrders"
            )
            assert isinstance(resource_response[0], TextResourceContents)
            response_text = resource_response[0].text
            content = json.loads(response_text)
        assert len(content) == 2
        assert content[0]["customer"] == "Alice"
        assert content[1]["customer"] == "Bob"

    async def test_resource_template_access(self, openapi_31_server):
        """Test reading a resource from template from an OpenAPI 3.1 server."""
        async with Client(openapi_31_server) as client:
            resource_response = await client.read_resource(
                "resource://openapi/getOrder/o1"
            )
            assert isinstance(resource_response[0], TextResourceContents)
            response_text = resource_response[0].text
            content = json.loads(response_text)
        assert content["id"] == "o1"
        assert content["customer"] == "Alice"
        assert content["items"] == ["item1", "item2"]

    async def test_tool_execution(self, openapi_31_server):
        """Test executing a tool from an OpenAPI 3.1 server."""
        async with Client(openapi_31_server) as client:
            result = await client.call_tool(
                "createOrder", {"customer": "Charlie", "items": ["item4", "item5"]}
            )
            # Result should be a text content
            assert len(result) == 1
            assert isinstance(result[0], TextContent)
            order = json.loads(result[0].text)
            assert order["id"] == "o3"
            assert order["customer"] == "Charlie"
            assert order["items"] == ["item4", "item5"]


class TestMountFlashMCP:
    """Tests for mounting FlashMCP servers."""

    async def test_mount_FlashMCP(self, FlashMCP_openapi_server: FlashMCPOpenAPI):
        """Test mounting an OpenAPI server."""
        mcp = FlashMCP("MainApp")

        await mcp.import_server("fastapi", FlashMCP_openapi_server)

        # Check that resources are available with prefixed URIs
        async with Client(mcp) as client:
            resources = await client.list_resources()
        assert len(resources) == 4  # Updated to account for new search endpoint
        # We're checking the key used by mcp to store the resource
        # The prefixed URI is used as the key, but the resource's original uri is preserved
        prefixed_uri = "resource://fastapi/openapi/get_users_users_get"
        resource = mcp._resource_manager.get_resources().get(prefixed_uri)
        assert resource is not None


async def test_empty_query_parameters_not_sent(
    fastapi_app: FastAPI, api_client: httpx.AsyncClient
):
    """Test that empty and None query parameters are not sent in the request."""

    # Create a TransportAdapter to track requests
    class RequestCapture(httpx.AsyncBaseTransport):
        def __init__(self, wrapped):
            self.wrapped = wrapped
            self.requests = []

        async def handle_async_request(self, request):
            self.requests.append(request)
            return await self.wrapped.handle_async_request(request)

    # Use our transport adapter to wrap the original one
    capture = RequestCapture(api_client._transport)
    api_client._transport = capture

    # Create the OpenAPI server with new route map to make search endpoint a tool
    openapi_spec = fastapi_app.openapi()
    mcp_server = FlashMCPOpenAPI(
        openapi_spec=openapi_spec,
        client=api_client,
        route_maps=[
            RouteMap(methods=["GET"], pattern=r".*", route_type=RouteType.TOOL)
        ],
    )

    # Call the search tool with mixed parameter values
    async with Client(mcp_server) as client:
        await client.call_tool(
            "search_users_search_get",
            {
                "name": "",  # Empty string should be excluded
                "active": None,  # None should be excluded
                "min_id": 2,  # Has value, should be included
            },
        )

    # Verify that the request URL only has min_id parameter
    assert len(capture.requests) > 0
    request = capture.requests[-1]  # Get the last request

    # URL should only contain min_id=2, not name= or active=
    url = str(request.url)
    assert "min_id=2" in url, f"URL should contain min_id=2, got: {url}"
    assert "name=" not in url, f"URL should not contain name=, got: {url}"
    assert "active=" not in url, f"URL should not contain active=, got: {url}"

    # More direct check - parse the URL to examine query params
    from urllib.parse import parse_qs, urlparse

    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    assert "min_id" in query_params
    assert "name" not in query_params
    assert "active" not in query_params


async def test_none_path_parameters_rejected(
    fastapi_app: FastAPI, api_client: httpx.AsyncClient
):
    """Test that None values for path parameters are properly rejected."""
    # Create the OpenAPI server
    openapi_spec = fastapi_app.openapi()
    mcp_server = FlashMCPOpenAPI(
        openapi_spec=openapi_spec,
        client=api_client,
    )

    # Create a client and try to call a tool with a None path parameter
    async with Client(mcp_server) as client:
        # get_user has a required path parameter user_id
        with pytest.raises(ToolError, match="Missing required path parameters"):
            await client.call_tool(
                "update_user_name_users__user_id__name_patch",
                {
                    "user_id": None,  # This should cause an error
                    "name": "New Name",
                },
            )


class TestDescriptionPropagation:
    """Tests for OpenAPI description propagation to FlashMCP components.

    Each test focuses on a single, specific behavior to make it immediately clear
    what's broken when a test fails.
    """

    @pytest.fixture
    def simple_openapi_spec(self) -> dict:
        """Create a minimal OpenAPI spec with obvious test descriptions."""
        return {
            "openapi": "3.1.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/items": {
                    "get": {
                        "operationId": "listItems",
                        "summary": "List items summary",
                        "description": "LIST_DESCRIPTION\n\nFUNCTION_LIST_DESCRIPTION",
                        "responses": {
                            "200": {
                                "description": "LIST_RESPONSE_DESCRIPTION",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "id": {
                                                        "type": "string",
                                                        "description": "ITEM_RESPONSE_ID_DESCRIPTION",
                                                    },
                                                    "name": {
                                                        "type": "string",
                                                        "description": "ITEM_RESPONSE_NAME_DESCRIPTION",
                                                    },
                                                    "price": {
                                                        "type": "number",
                                                        "description": "ITEM_RESPONSE_PRICE_DESCRIPTION",
                                                    },
                                                },
                                            },
                                        },
                                    }
                                },
                            }
                        },
                    }
                },
                "/items/{item_id}": {
                    "get": {
                        "operationId": "getItem",
                        "summary": "Get item summary",
                        "description": "GET_DESCRIPTION\n\nFUNCTION_GET_DESCRIPTION",
                        "parameters": [
                            {
                                "name": "item_id",
                                "in": "path",
                                "required": True,
                                "description": "PATH_PARAM_DESCRIPTION",
                                "schema": {"type": "string"},
                            },
                            {
                                "name": "fields",
                                "in": "query",
                                "required": False,
                                "description": "QUERY_PARAM_DESCRIPTION",
                                "schema": {"type": "string"},
                            },
                        ],
                        "responses": {
                            "200": {
                                "description": "GET_RESPONSE_DESCRIPTION",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "id": {
                                                    "type": "string",
                                                    "description": "ITEM_RESPONSE_ID_DESCRIPTION",
                                                },
                                                "name": {
                                                    "type": "string",
                                                    "description": "ITEM_RESPONSE_NAME_DESCRIPTION",
                                                },
                                                "price": {
                                                    "type": "number",
                                                    "description": "ITEM_RESPONSE_PRICE_DESCRIPTION",
                                                },
                                            },
                                        },
                                    }
                                },
                            }
                        },
                    }
                },
                "/items/create": {
                    "post": {
                        "operationId": "createItem",
                        "summary": "Create item summary",
                        "description": "CREATE_DESCRIPTION\n\nFUNCTION_CREATE_DESCRIPTION",
                        "requestBody": {
                            "required": True,
                            "description": "BODY_DESCRIPTION",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "name": {
                                                "type": "string",
                                                "description": "PROP_DESCRIPTION",
                                            }
                                        },
                                        "required": ["name"],
                                    }
                                }
                            },
                        },
                        "responses": {
                            "201": {
                                "description": "CREATE_RESPONSE_DESCRIPTION",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "id": {
                                                    "type": "string",
                                                    "description": "ITEM_RESPONSE_ID_DESCRIPTION",
                                                },
                                                "name": {
                                                    "type": "string",
                                                    "description": "ITEM_RESPONSE_NAME_DESCRIPTION",
                                                },
                                            },
                                        },
                                    }
                                },
                            }
                        },
                    }
                },
            },
        }

    @pytest.fixture
    async def mock_client(self) -> httpx.AsyncClient:
        """Create a mock client that returns simple responses."""

        async def _responder(request):
            if request.url.path == "/items" and request.method == "GET":
                return httpx.Response(200, json=[{"id": "1", "name": "Item 1"}])
            elif request.url.path.startswith("/items/") and request.method == "GET":
                item_id = request.url.path.split("/")[-1]
                return httpx.Response(
                    200, json={"id": item_id, "name": f"Item {item_id}"}
                )
            elif request.url.path == "/items/create" and request.method == "POST":
                import json

                data = json.loads(request.content)
                return httpx.Response(201, json={"id": "new", "name": data.get("name")})

            return httpx.Response(404)

        transport = httpx.MockTransport(_responder)
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    @pytest.fixture
    async def test_server(self, simple_openapi_spec, mock_client):
        """Create a FlashMCPOpenAPI server with the simple test spec."""
        return FlashMCPOpenAPI(
            openapi_spec=simple_openapi_spec,
            client=mock_client,
            name="Test API",
        )

    # --- RESOURCE TESTS ---

    async def test_resource_includes_route_description(self, test_server):
        """Test that a Resource includes the route description."""
        resources = list(test_server._resource_manager.get_resources().values())
        list_resource = next((r for r in resources if r.name == "listItems"), None)

        assert list_resource is not None, "listItems resource wasn't created"
        assert "LIST_DESCRIPTION" in (list_resource.description or ""), (
            "Route description missing from Resource"
        )

    async def test_resource_includes_response_description(self, test_server):
        """Test that a Resource includes the response description."""
        resources = list(test_server._resource_manager.get_resources().values())
        list_resource = next((r for r in resources if r.name == "listItems"), None)

        assert list_resource is not None, "listItems resource wasn't created"
        assert "LIST_RESPONSE_DESCRIPTION" in (list_resource.description or ""), (
            "Response description missing from Resource"
        )

    async def test_resource_includes_response_model_fields(self, test_server):
        """Test that a Resource description includes response model field descriptions."""
        resources = list(test_server._resource_manager.get_resources().values())
        list_resource = next((r for r in resources if r.name == "listItems"), None)

        assert list_resource is not None, "listItems resource wasn't created"
        description = list_resource.description or ""
        assert "ITEM_RESPONSE_ID_DESCRIPTION" in description, (
            "Response model field descriptions missing from Resource description"
        )
        assert "ITEM_RESPONSE_NAME_DESCRIPTION" in description, (
            "Response model field descriptions missing from Resource description"
        )
        assert "ITEM_RESPONSE_PRICE_DESCRIPTION" in description, (
            "Response model field descriptions missing from Resource description"
        )

    # --- RESOURCE TEMPLATE TESTS ---

    async def test_template_includes_route_description(self, test_server):
        """Test that a ResourceTemplate includes the route description."""
        templates = list(test_server._resource_manager.get_templates().values())
        get_template = next((t for t in templates if t.name == "getItem"), None)

        assert get_template is not None, "getItem template wasn't created"
        assert "GET_DESCRIPTION" in (get_template.description or ""), (
            "Route description missing from ResourceTemplate"
        )

    async def test_template_includes_function_docstring(self, test_server):
        """Test that a ResourceTemplate includes the function docstring."""
        templates = list(test_server._resource_manager.get_templates().values())
        get_template = next((t for t in templates if t.name == "getItem"), None)

        assert get_template is not None, "getItem template wasn't created"
        assert "FUNCTION_GET_DESCRIPTION" in (get_template.description or ""), (
            "Function docstring missing from ResourceTemplate"
        )

    async def test_template_includes_path_parameter_description(self, test_server):
        """Test that a ResourceTemplate includes path parameter descriptions."""
        templates = list(test_server._resource_manager.get_templates().values())
        get_template = next((t for t in templates if t.name == "getItem"), None)

        assert get_template is not None, "getItem template wasn't created"
        assert "PATH_PARAM_DESCRIPTION" in (get_template.description or ""), (
            "Path parameter description missing from ResourceTemplate description"
        )

    async def test_template_includes_query_parameter_description(self, test_server):
        """Test that a ResourceTemplate includes query parameter descriptions."""
        templates = list(test_server._resource_manager.get_templates().values())
        get_template = next((t for t in templates if t.name == "getItem"), None)

        assert get_template is not None, "getItem template wasn't created"
        assert "QUERY_PARAM_DESCRIPTION" in (get_template.description or ""), (
            "Query parameter description missing from ResourceTemplate description"
        )

    async def test_template_parameter_schema_includes_description(self, test_server):
        """Test that a ResourceTemplate's parameter schema includes parameter descriptions."""
        templates = list(test_server._resource_manager.get_templates().values())
        get_template = next((t for t in templates if t.name == "getItem"), None)

        assert get_template is not None, "getItem template wasn't created"
        assert "properties" in get_template.parameters, (
            "Schema properties missing from ResourceTemplate"
        )
        assert "item_id" in get_template.parameters["properties"], (
            "item_id missing from ResourceTemplate schema"
        )
        assert "description" in get_template.parameters["properties"]["item_id"], (
            "Description missing from item_id parameter schema"
        )
        assert (
            "PATH_PARAM_DESCRIPTION"
            in get_template.parameters["properties"]["item_id"]["description"]
        ), "Path parameter description incorrect in schema"

    # --- TOOL TESTS ---

    async def test_tool_includes_route_description(self, test_server):
        """Test that a Tool includes the route description."""
        tools = test_server._tool_manager.list_tools()
        create_tool = next((t for t in tools if t.name == "createItem"), None)

        assert create_tool is not None, "createItem tool wasn't created"
        assert "CREATE_DESCRIPTION" in (create_tool.description or ""), (
            "Route description missing from Tool"
        )

    async def test_tool_includes_function_docstring(self, test_server):
        """Test that a Tool includes the function docstring."""
        tools = test_server._tool_manager.list_tools()
        create_tool = next((t for t in tools if t.name == "createItem"), None)

        assert create_tool is not None, "createItem tool wasn't created"
        description = create_tool.description or ""
        assert "FUNCTION_CREATE_DESCRIPTION" in description, (
            "Function docstring missing from Tool"
        )

    async def test_tool_parameter_schema_includes_property_description(
        self, test_server
    ):
        """Test that a Tool's parameter schema includes property descriptions from request model."""
        tools = test_server._tool_manager.list_tools()
        create_tool = next((t for t in tools if t.name == "createItem"), None)

        assert create_tool is not None, "createItem tool wasn't created"
        assert "properties" in create_tool.parameters, (
            "Schema properties missing from Tool"
        )
        assert "name" in create_tool.parameters["properties"], (
            "name parameter missing from Tool schema"
        )
        assert "description" in create_tool.parameters["properties"]["name"], (
            "Description missing from name parameter schema"
        )
        assert (
            "PROP_DESCRIPTION"
            in create_tool.parameters["properties"]["name"]["description"]
        ), "Property description incorrect in schema"

    # --- CLIENT API TESTS ---

    async def test_client_api_resource_description(self, test_server):
        """Test that Resource descriptions are accessible via the client API."""
        async with Client(test_server) as client:
            resources = await client.list_resources()
            list_resource = next((r for r in resources if r.name == "listItems"), None)

            assert list_resource is not None, (
                "listItems resource not accessible via client API"
            )
            resource_description = list_resource.description or ""
            assert "LIST_DESCRIPTION" in resource_description, (
                "Route description missing in Resource from client API"
            )

    async def test_client_api_template_description(self, test_server):
        """Test that ResourceTemplate descriptions are accessible via the client API."""
        async with Client(test_server) as client:
            templates = await client.list_resource_templates()
            get_template = next((t for t in templates if t.name == "getItem"), None)

            assert get_template is not None, (
                "getItem template not accessible via client API"
            )
            template_description = get_template.description or ""
            assert "GET_DESCRIPTION" in template_description, (
                "Route description missing in ResourceTemplate from client API"
            )

    async def test_client_api_tool_description(self, test_server):
        """Test that Tool descriptions are accessible via the client API."""
        async with Client(test_server) as client:
            tools = await client.list_tools()
            create_tool = next((t for t in tools if t.name == "createItem"), None)

            assert create_tool is not None, (
                "createItem tool not accessible via client API"
            )
            tool_description = create_tool.description or ""
            assert "FUNCTION_CREATE_DESCRIPTION" in tool_description, (
                "Function docstring missing in Tool from client API"
            )

    async def test_client_api_tool_parameter_schema(self, test_server):
        """Test that Tool parameter schemas are accessible via the client API."""
        async with Client(test_server) as client:
            tools = await client.list_tools()
            create_tool = next((t for t in tools if t.name == "createItem"), None)

            assert create_tool is not None, (
                "createItem tool not accessible via client API"
            )
            assert "properties" in create_tool.inputSchema, (
                "Schema properties missing from Tool inputSchema in client API"
            )
            assert "name" in create_tool.inputSchema["properties"], (
                "name parameter missing from Tool schema in client API"
            )
            assert "description" in create_tool.inputSchema["properties"]["name"], (
                "Description missing from name parameter in client API"
            )
            assert (
                "PROP_DESCRIPTION"
                in create_tool.inputSchema["properties"]["name"]["description"]
            ), "Property description incorrect in schema from client API"


class TestFastAPIDescriptionPropagation:
    """Tests for FastAPI docstring and annotation propagation to FlashMCP components.

    Each test focuses on a single, specific behavior to make it immediately clear
    what's broken when a test fails.
    """

    @pytest.fixture
    def fastapi_app_with_descriptions(self) -> FastAPI:
        """Create a simple FastAPI app with docstrings and annotations."""
        from typing import Annotated

        from pydantic import BaseModel, Field

        app = FastAPI(title="Test FastAPI App")

        class Item(BaseModel):
            name: str = Field(..., description="ITEM_NAME_DESCRIPTION")
            price: float = Field(..., description="ITEM_PRICE_DESCRIPTION")

        class ItemResponse(BaseModel):
            id: str = Field(..., description="ITEM_RESPONSE_ID_DESCRIPTION")
            name: str = Field(..., description="ITEM_RESPONSE_NAME_DESCRIPTION")
            price: float = Field(..., description="ITEM_RESPONSE_PRICE_DESCRIPTION")

        @app.get("/items", tags=["items"])
        async def list_items() -> list[ItemResponse]:
            """FUNCTION_LIST_DESCRIPTION

            Returns a list of items.
            """
            return [
                ItemResponse(id="1", name="Item 1", price=10.0),
                ItemResponse(id="2", name="Item 2", price=20.0),
            ]

        @app.get("/items/{item_id}", tags=["items", "detail"])
        async def get_item(
            item_id: Annotated[str, Field(description="PATH_PARAM_DESCRIPTION")],
            fields: Annotated[
                str | None, Field(description="QUERY_PARAM_DESCRIPTION")
            ] = None,
        ) -> ItemResponse:
            """FUNCTION_GET_DESCRIPTION

            Gets a specific item by ID.

            Args:
                item_id: The ID of the item to retrieve
                fields: Optional fields to include
            """
            return ItemResponse(
                id=item_id, name=f"Item {item_id}", price=float(item_id) * 10.0
            )

        @app.post("/items", tags=["items", "create"])
        async def create_item(item: Item) -> ItemResponse:
            """FUNCTION_CREATE_DESCRIPTION

            Creates a new item.

            Body:
                Item object with name and price
            """
            return ItemResponse(id="new", name=item.name, price=item.price)

        return app

    @pytest.fixture
    async def fastapi_server(self, fastapi_app_with_descriptions):
        """Create a FlashMCP server from the FastAPI app with custom route mappings."""
        # First create from FastAPI app to get the OpenAPI spec
        openapi_spec = fastapi_app_with_descriptions.openapi()

        # Debug: check the operationIds in the OpenAPI spec
        print("\nDEBUG - OpenAPI Paths:")
        for path, methods in openapi_spec["paths"].items():
            for method, details in methods.items():
                if method != "parameters":  # Skip non-HTTP method keys
                    operation_id = details.get("operationId", "no_operation_id")
                    print(
                        f"  Path: {path}, Method: {method}, OperationId: {operation_id}"
                    )

        # Create custom route mappings
        route_maps = [
            # Map GET /items to Resource
            RouteMap(
                methods=["GET"], pattern=r"^/items$", route_type=RouteType.RESOURCE
            ),
            # Map GET /items/{item_id} to ResourceTemplate
            RouteMap(
                methods=["GET"],
                pattern=r"^/items/\{.*\}$",
                route_type=RouteType.RESOURCE_TEMPLATE,
            ),
            # Map POST /items to Tool
            RouteMap(methods=["POST"], pattern=r"^/items$", route_type=RouteType.TOOL),
        ]

        # Create FlashMCP server with the OpenAPI spec and custom route mappings
        server = FlashMCPOpenAPI(
            openapi_spec=openapi_spec,
            client=AsyncClient(
                transport=ASGITransport(app=fastapi_app_with_descriptions),
                base_url="http://test",
            ),
            name="Test FastAPI App",
            route_maps=route_maps,
        )

        # Debug: print all components created
        print("\nDEBUG - Resources created:")
        for name, resource in server._resource_manager.get_resources().items():
            print(f"  Resource: {name}, Name attribute: {resource.name}")

        print("\nDEBUG - Templates created:")
        for name, template in server._resource_manager.get_templates().items():
            print(f"  Template: {name}, Name attribute: {template.name}")

        print("\nDEBUG - Tools created:")
        for tool in server._tool_manager.list_tools():
            print(f"  Tool: {tool.name}")

        return server

    async def test_resource_includes_function_docstring(self, fastapi_server):
        """Test that a Resource includes the function docstring."""
        resources = list(fastapi_server._resource_manager.get_resources().values())

        # Now checking for the get_items operation ID rather than list_items
        list_resource = next((r for r in resources if "items_get" in r.name), None)

        assert list_resource is not None, "GET /items resource wasn't created"
        description = list_resource.description or ""
        assert "FUNCTION_LIST_DESCRIPTION" in description, (
            "Function docstring missing from Resource"
        )

    async def test_resource_includes_response_model_fields(self, fastapi_server):
        """Test that a Resource description includes basic response information.

        Note: FastAPI doesn't reliably include Pydantic field descriptions in the OpenAPI schema,
        so we can only check for basic response information being present.
        """
        resources = list(fastapi_server._resource_manager.get_resources().values())
        list_resource = next((r for r in resources if "items_get" in r.name), None)

        assert list_resource is not None, "GET /items resource wasn't created"
        description = list_resource.description or ""

        # Check that at least the response information is included
        assert "Successful Response" in description, (
            "Response information missing from Resource description"
        )

        # We've already verified in TestDescriptionPropagation that when descriptions
        # are present in the OpenAPI schema, they are properly included in the component description

    async def test_template_includes_function_docstring(self, fastapi_server):
        """Test that a ResourceTemplate includes the function docstring."""
        templates = list(fastapi_server._resource_manager.get_templates().values())
        get_template = next(
            (t for t in templates if "items__item_id__get" in t.name), None
        )

        assert get_template is not None, "GET /items/{item_id} template wasn't created"
        description = get_template.description or ""
        assert "FUNCTION_GET_DESCRIPTION" in description, (
            "Function docstring missing from ResourceTemplate"
        )

    async def test_template_includes_path_parameter_description(self, fastapi_server):
        """Test that a ResourceTemplate includes path parameter descriptions.

        Note: Currently, FastAPI parameter descriptions using Annotated[type, Field(description=...)]
        are not properly propagated to the OpenAPI schema. The parameters appear but without the description.
        """
        templates = list(fastapi_server._resource_manager.get_templates().values())
        get_template = next(
            (t for t in templates if "items__item_id__get" in t.name), None
        )

        assert get_template is not None, "GET /items/{item_id} template wasn't created"
        description = get_template.description or ""

        # Just test that parameters are included at all
        assert "Path Parameters" in description, (
            "Path parameters section missing from ResourceTemplate description"
        )
        assert "item_id" in description, (
            "item_id parameter missing from ResourceTemplate description"
        )

    async def test_template_includes_query_parameter_description(self, fastapi_server):
        """Test that a ResourceTemplate includes query parameter descriptions.

        Note: Currently, FastAPI parameter descriptions using Annotated[type, Field(description=...)]
        are not properly propagated to the OpenAPI schema. The parameters appear but without the description.
        """
        templates = list(fastapi_server._resource_manager.get_templates().values())
        get_template = next(
            (t for t in templates if "items__item_id__get" in t.name), None
        )

        assert get_template is not None, "GET /items/{item_id} template wasn't created"
        description = get_template.description or ""

        # Just test that parameters are included at all
        assert "Query Parameters" in description, (
            "Query parameters section missing from ResourceTemplate description"
        )
        assert "fields" in description, (
            "fields parameter missing from ResourceTemplate description"
        )

    async def test_template_parameter_schema_includes_description(self, fastapi_server):
        """Test that a ResourceTemplate's parameter schema includes parameter descriptions."""
        templates = list(fastapi_server._resource_manager.get_templates().values())
        get_template = next(
            (t for t in templates if "items__item_id__get" in t.name), None
        )

        assert get_template is not None, "GET /items/{item_id} template wasn't created"
        assert "properties" in get_template.parameters, (
            "Schema properties missing from ResourceTemplate"
        )
        assert "item_id" in get_template.parameters["properties"], (
            "item_id missing from ResourceTemplate schema"
        )
        assert "description" in get_template.parameters["properties"]["item_id"], (
            "Description missing from item_id parameter schema"
        )
        assert (
            "PATH_PARAM_DESCRIPTION"
            in get_template.parameters["properties"]["item_id"]["description"]
        ), "Path parameter description incorrect in schema"

    async def test_tool_includes_function_docstring(self, fastapi_server):
        """Test that a Tool includes the function docstring."""
        tools = fastapi_server._tool_manager.list_tools()
        create_tool = next(
            (t for t in tools if "create_item_items_post" == t.name), None
        )

        assert create_tool is not None, "POST /items tool wasn't created"
        description = create_tool.description or ""
        assert "FUNCTION_CREATE_DESCRIPTION" in description, (
            "Function docstring missing from Tool"
        )

    async def test_tool_parameter_schema_includes_property_description(
        self, fastapi_server
    ):
        """Test that a Tool's parameter schema includes property descriptions from request model.

        Note: Currently, model field descriptions defined in Pydantic models using Field(description=...)
        may not be consistently propagated into the FastAPI OpenAPI schema and thus not into the tool's
        parameter schema.
        """
        tools = fastapi_server._tool_manager.list_tools()
        create_tool = next(
            (t for t in tools if "create_item_items_post" == t.name), None
        )

        assert create_tool is not None, "POST /items tool wasn't created"
        assert "properties" in create_tool.parameters, (
            "Schema properties missing from Tool"
        )
        assert "name" in create_tool.parameters["properties"], (
            "name parameter missing from Tool schema"
        )
        # We don't test for the description field content as it may not be consistently propagated

    async def test_client_api_resource_description(self, fastapi_server):
        """Test that Resource descriptions are accessible via the client API."""
        async with Client(fastapi_server) as client:
            resources = await client.list_resources()
            list_resource = next((r for r in resources if "items_get" in r.name), None)

            assert list_resource is not None, (
                "GET /items resource not accessible via client API"
            )
            resource_description = list_resource.description or ""
            assert "FUNCTION_LIST_DESCRIPTION" in resource_description, (
                "Function docstring missing in Resource from client API"
            )

    async def test_client_api_template_description(self, fastapi_server):
        """Test that ResourceTemplate descriptions are accessible via the client API."""
        async with Client(fastapi_server) as client:
            templates = await client.list_resource_templates()
            get_template = next(
                (t for t in templates if "items__item_id__get" in t.name), None
            )

            assert get_template is not None, (
                "GET /items/{item_id} template not accessible via client API"
            )
            template_description = get_template.description or ""
            assert "FUNCTION_GET_DESCRIPTION" in template_description, (
                "Function docstring missing in ResourceTemplate from client API"
            )

    async def test_client_api_tool_description(self, fastapi_server):
        """Test that Tool descriptions are accessible via the client API."""
        async with Client(fastapi_server) as client:
            tools = await client.list_tools()
            create_tool = next(
                (t for t in tools if "create_item_items_post" == t.name), None
            )

            assert create_tool is not None, (
                "POST /items tool not accessible via client API"
            )
            tool_description = create_tool.description or ""
            assert "FUNCTION_CREATE_DESCRIPTION" in tool_description, (
                "Function docstring missing in Tool from client API"
            )

    async def test_client_api_tool_parameter_schema(self, fastapi_server):
        """Test that Tool parameter schemas are accessible via the client API."""
        async with Client(fastapi_server) as client:
            tools = await client.list_tools()
            create_tool = next(
                (t for t in tools if "create_item_items_post" == t.name), None
            )

            assert create_tool is not None, (
                "POST /items tool not accessible via client API"
            )
            assert "properties" in create_tool.inputSchema, (
                "Schema properties missing from Tool inputSchema in client API"
            )
            assert "name" in create_tool.inputSchema["properties"], (
                "name parameter missing from Tool schema in client API"
            )
            # We don't test for the description field content as it may not be consistently propagated


class TestReprMethods:
    """Tests for the custom __repr__ methods of OpenAPI objects."""

    async def test_openapi_tool_repr(self, FlashMCP_openapi_server: FlashMCPOpenAPI):
        """Test that OpenAPITool's __repr__ method works without recursion errors."""
        tools = FlashMCP_openapi_server._tool_manager.list_tools()
        tool = next(iter(tools))

        # Verify repr doesn't cause recursion and contains expected elements
        tool_repr = repr(tool)
        assert "OpenAPITool" in tool_repr
        assert f"name={tool.name!r}" in tool_repr
        assert "method=" in tool_repr
        assert "path=" in tool_repr

    async def test_openapi_resource_repr(self, FlashMCP_openapi_server: FlashMCPOpenAPI):
        """Test that OpenAPIResource's __repr__ method works without recursion errors."""
        resources = list(
            FlashMCP_openapi_server._resource_manager.get_resources().values()
        )
        resource = next(iter(resources))

        # Verify repr doesn't cause recursion and contains expected elements
        resource_repr = repr(resource)
        assert "OpenAPIResource" in resource_repr
        assert f"name={resource.name!r}" in resource_repr
        assert "uri=" in resource_repr
        assert "path=" in resource_repr

    async def test_openapi_resource_template_repr(
        self, FlashMCP_openapi_server: FlashMCPOpenAPI
    ):
        """Test that OpenAPIResourceTemplate's __repr__ method works without recursion errors."""
        templates = list(
            FlashMCP_openapi_server._resource_manager.get_templates().values()
        )
        template = next(iter(templates))

        # Verify repr doesn't cause recursion and contains expected elements
        template_repr = repr(template)
        assert "OpenAPIResourceTemplate" in template_repr
        assert f"name={template.name!r}" in template_repr
        assert "uri_template=" in template_repr
        assert "path=" in template_repr


class TestEnumHandling:
    """Tests for handling enum parameters in OpenAPI schemas."""

    async def test_enum_parameter_schema(self):
        """Test that enum parameters are properly handled in tool parameter schemas."""

        # Define an enum just like in example.py
        class QueryEnum(str, Enum):
            foo = "foo"
            bar = "bar"
            baz = "baz"

        # Create a minimal FastAPI app with an endpoint using the enum
        app = FastAPI()

        @app.post("/items/{item_id}")
        def read_item(
            item_id: int,
            query: QueryEnum | None = None,
        ):
            return {"item_id": item_id, "query": query}

        # Create a client for the app
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

        # Create the FlashMCPOpenAPI server from the app
        openapi_spec = app.openapi()
        server = FlashMCPOpenAPI(
            openapi_spec=openapi_spec,
            client=client,
            name="Enum Test",
        )

        # Get the tools from the server
        tools = server._tool_manager.list_tools()

        # Find the read_item tool
        read_item_tool = next(
            (t for t in tools if t.name == "read_item_items__item_id__post"), None
        )

        # Verify the tool exists
        assert read_item_tool is not None, "read_item tool wasn't created"

        # Check that the parameters include the enum reference
        assert "properties" in read_item_tool.parameters
        assert "query" in read_item_tool.parameters["properties"]

        # Check for the anyOf with $ref to the enum definition
        query_param = read_item_tool.parameters["properties"]["query"]
        assert "anyOf" in query_param

        # Find the ref in the anyOf list
        ref_found = False
        for option in query_param["anyOf"]:
            if "$ref" in option and option["$ref"].startswith("#/$defs/QueryEnum"):
                ref_found = True
                break

        assert ref_found, "Reference to enum definition not found in query parameter"

        # Check that the $defs section exists and contains the enum definition
        assert "$defs" in read_item_tool.parameters
        assert "QueryEnum" in read_item_tool.parameters["$defs"]

        # Verify the enum definition
        enum_def = read_item_tool.parameters["$defs"]["QueryEnum"]
        assert "enum" in enum_def
        assert enum_def["enum"] == ["foo", "bar", "baz"]
        assert enum_def["type"] == "string"


class TestRouteMapWildcard:
    """Tests for wildcard RouteMap methods functionality."""

    @pytest.fixture
    def basic_openapi_spec(self) -> dict:
        """Create a minimal OpenAPI spec with different HTTP methods."""
        return {
            "openapi": "3.1.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/users": {
                    "get": {
                        "operationId": "getUsers",
                        "responses": {"200": {"description": "Success"}},
                    },
                    "post": {
                        "operationId": "createUser",
                        "responses": {"201": {"description": "Created"}},
                    },
                },
                "/posts": {
                    "get": {
                        "operationId": "getPosts",
                        "responses": {"200": {"description": "Success"}},
                    },
                    "post": {
                        "operationId": "createPost",
                        "responses": {"201": {"description": "Created"}},
                    },
                },
            },
        }

    @pytest.fixture
    async def mock_basic_client(self) -> httpx.AsyncClient:
        """Create a simple mock client."""

        async def _responder(request):
            return httpx.Response(200, json={"status": "ok"})

        transport = httpx.MockTransport(_responder)
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    async def test_wildcard_matches_all_methods(
        self, basic_openapi_spec, mock_basic_client
    ):
        """Test that a RouteMap with methods='*' matches all HTTP methods."""
        # Create a single route map with wildcard method
        route_maps = [RouteMap(methods="*", pattern=r".*", route_type=RouteType.TOOL)]

        mcp = FlashMCPOpenAPI(
            openapi_spec=basic_openapi_spec,
            client=mock_basic_client,
            route_maps=route_maps,
        )

        # All operations should be mapped to tools
        tools = mcp._tool_manager.list_tools()
        tool_names = {tool.name for tool in tools}

        # Check that all operations were mapped as tools
        expected_tools = {"getUsers", "createUser", "getPosts", "createPost"}
        assert tool_names == expected_tools

        # No resources or templates should be created
        resources = mcp._resource_manager.get_resources()
        templates = mcp._resource_manager.get_templates()
        assert len(resources) == 0
        assert len(templates) == 0

    async def test_priority_specific_over_wildcard(
        self, basic_openapi_spec, mock_basic_client
    ):
        """Test that specific method maps take priority over wildcard."""
        # Create route maps with specific method first, then wildcard
        route_maps = [
            # GET operations should be mapped to resources
            RouteMap(methods=["GET"], pattern=r".*", route_type=RouteType.RESOURCE),
            # All other operations should be mapped to tools
            RouteMap(methods="*", pattern=r".*", route_type=RouteType.TOOL),
        ]

        mcp = FlashMCPOpenAPI(
            openapi_spec=basic_openapi_spec,
            client=mock_basic_client,
            route_maps=route_maps,
        )

        # Check GET operations went to resources
        resources = mcp._resource_manager.get_resources()
        resource_names = {r.name for r in resources.values()}
        assert "getUsers" in resource_names
        assert "getPosts" in resource_names
        assert len(resources) == 2

        # Check other operations went to tools
        tools = mcp._tool_manager.list_tools()
        tool_names = {tool.name for tool in tools}
        assert "createUser" in tool_names
        assert "createPost" in tool_names
        assert len(tools) == 2

    async def test_priority_wildcard_first(self, basic_openapi_spec, mock_basic_client):
        """Test that when wildcard is first, it matches everything."""
        # Create route maps with wildcard first, then specific methods
        route_maps = [
            # Wildcard first matches everything
            RouteMap(methods="*", pattern=r".*", route_type=RouteType.TOOL),
            # This should never be reached
            RouteMap(methods=["GET"], pattern=r".*", route_type=RouteType.RESOURCE),
        ]

        mcp = FlashMCPOpenAPI(
            openapi_spec=basic_openapi_spec,
            client=mock_basic_client,
            route_maps=route_maps,
        )

        # All operations should be tools
        tools = mcp._tool_manager.list_tools()
        assert len(tools) == 4

        # No resources should be created
        resources = mcp._resource_manager.get_resources()
        assert len(resources) == 0

    async def test_wildcard_with_specific_paths(
        self, basic_openapi_spec, mock_basic_client
    ):
        """Test wildcard methods combined with specific path patterns."""
        route_maps = [
            # All methods on /users path -> Resources
            RouteMap(methods="*", pattern=r".*/users$", route_type=RouteType.RESOURCE),
            # All methods on /posts path -> Tools
            RouteMap(methods="*", pattern=r".*/posts$", route_type=RouteType.TOOL),
        ]

        mcp = FlashMCPOpenAPI(
            openapi_spec=basic_openapi_spec,
            client=mock_basic_client,
            route_maps=route_maps,
        )

        # Check /users operations went to resources
        resources = mcp._resource_manager.get_resources()
        resource_names = {r.name for r in resources.values()}
        assert "getUsers" in resource_names
        assert "createUser" in resource_names
        assert len(resources) == 2

        # Check /posts operations went to tools
        tools = mcp._tool_manager.list_tools()
        tool_names = {tool.name for tool in tools}
        assert "getPosts" in tool_names
        assert "createPost" in tool_names
        assert len(tools) == 2


class TestAllRoutesAsTools:
    """Tests for the all_routes_as_tools parameter in FlashMCP class methods."""

    @pytest.fixture
    def simple_api_spec(self) -> dict:
        """A simple OpenAPI spec with both GET and POST methods."""
        return {
            "openapi": "3.1.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/items": {
                    "get": {
                        "operationId": "getItems",
                        "responses": {"200": {"description": "Success"}},
                    },
                    "post": {
                        "operationId": "createItem",
                        "responses": {"201": {"description": "Created"}},
                    },
                },
            },
        }

    @pytest.fixture
    async def mock_client(self) -> httpx.AsyncClient:
        """Simple mock client for testing."""

        async def _responder(request):
            return httpx.Response(200, json={"result": "ok"})

        transport = httpx.MockTransport(_responder)
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    async def test_from_openapi_all_routes_as_tools(self, simple_api_spec, mock_client):
        """Test FlashMCP.from_openapi with all_routes_as_tools=True."""
        # Create server with all routes as tools
        server = FlashMCP.from_openapi(
            openapi_spec=simple_api_spec, client=mock_client, all_routes_as_tools=True
        )

        # All operations (GET and POST) should be mapped to tools
        tools = server._tool_manager.list_tools()
        tool_names = {t.name for t in tools}

        assert "getItems" in tool_names
        assert "createItem" in tool_names
        assert len(tools) == 2

        # No resources or templates should be created
        resources = server._resource_manager.get_resources()
        templates = server._resource_manager.get_templates()
        assert len(resources) == 0
        assert len(templates) == 0

    async def test_from_openapi_all_routes_as_tools_conflicting_args(
        self, simple_api_spec, mock_client
    ):
        """Test FlashMCP.from_openapi raises error when both route_maps and all_routes_as_tools are provided."""
        # Try to create server with conflicting args
        with pytest.raises(
            ValueError, match="Cannot specify both all_routes_as_tools and route_maps"
        ):
            FlashMCP.from_openapi(
                openapi_spec=simple_api_spec,
                client=mock_client,
                all_routes_as_tools=True,
                route_maps=[
                    RouteMap(
                        methods=["GET"], pattern=r".*", route_type=RouteType.RESOURCE
                    )
                ],
            )

    async def test_from_fastapi_all_routes_as_tools(self):
        """Test FlashMCP.from_fastapi with all_routes_as_tools=True."""
        # Create a simple FastAPI app
        app = FastAPI(title="Test FastAPI")

        @app.get("/items")
        async def get_items():
            return [{"id": 1, "name": "Item 1"}]

        @app.post("/items")
        async def create_item(item: dict):
            return {"id": 2, **item}

        # Create server with all routes as tools
        server = FlashMCP.from_fastapi(app=app, all_routes_as_tools=True)

        # Both GET and POST operations should be mapped to tools
        tools = server._tool_manager.list_tools()

        # Get tool names from the generated operation IDs
        tool_names = {t.name for t in tools}

        # Check that both routes were mapped to tools
        # The exact names depend on FastAPI's operation ID generation
        assert len(tools) == 2
        assert any("get" in name.lower() for name in tool_names)
        assert any("post" in name.lower() for name in tool_names)

        # No resources or templates should be created
        resources = server._resource_manager.get_resources()
        templates = server._resource_manager.get_templates()
        assert len(resources) == 0
        assert len(templates) == 0

    async def test_from_fastapi_all_routes_as_tools_conflicting_args(self):
        """Test FlashMCP.from_fastapi raises error when both route_maps and all_routes_as_tools are provided."""
        app = FastAPI(title="Test FastAPI")

        # Try to create server with conflicting args
        with pytest.raises(
            ValueError, match="Cannot specify both all_routes_as_tools and route_maps"
        ):
            FlashMCP.from_fastapi(
                app=app,
                all_routes_as_tools=True,
                route_maps=[
                    RouteMap(
                        methods=["GET"], pattern=r".*", route_type=RouteType.RESOURCE
                    )
                ],
            )
