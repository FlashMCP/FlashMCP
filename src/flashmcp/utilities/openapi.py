import logging
from typing import Any, Dict, List, Literal, Optional, Tuple, Union, cast

# Using the recommended library: openapi-pydantic
from openapi_pydantic import (
    MediaType,
    OpenAPI,
    Operation,
    Parameter,
    PathItem,
    Reference,
    RequestBody,
    Schema,
)
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

# --- Intermediate Representation (IR) Definition ---
# (IR models remain the same)

HttpMethod = Literal[
    "GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD", "TRACE"
]
ParameterLocation = Literal["path", "query", "header", "cookie"]
JsonSchema = Dict[str, Any]


class ParameterInfo(BaseModel):
    """Represents a single parameter for an HTTP operation in our IR."""

    name: str
    location: ParameterLocation  # Mapped from 'in' field of openapi-pydantic Parameter
    required: bool = False
    schema_: JsonSchema = Field(..., alias="schema")  # Target name in IR
    description: Optional[str] = None

    # No model_config needed here if we populate manually after accessing 'in'


class RequestBodyInfo(BaseModel):
    """Represents the request body for an HTTP operation in our IR."""

    required: bool = False
    content_schema: Dict[str, JsonSchema] = Field(
        default_factory=dict
    )  # Key: media type
    description: Optional[str] = None


class HTTPRoute(BaseModel):
    """Intermediate Representation for a single OpenAPI operation."""

    path: str
    method: HttpMethod
    operation_id: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    parameters: List[ParameterInfo] = Field(default_factory=list)
    request_body: Optional[RequestBodyInfo] = None


# --- Helper Functions ---


def _resolve_ref(
    item: Union[Reference, Schema, Parameter, RequestBody, Any], openapi: OpenAPI
) -> Any:
    """Resolves a potential Reference object to its target definition (no changes needed here)."""
    if isinstance(item, Reference):
        ref_str = item.ref
        try:
            if not ref_str.startswith("#/"):
                raise ValueError(
                    f"External or non-local reference not supported: {ref_str}"
                )
            parts = ref_str.strip("#/").split("/")
            target = openapi
            for part in parts:
                if part.isdigit() and isinstance(target, list):
                    target = target[int(part)]
                elif isinstance(target, BaseModel):
                    # Use model_extra for fields not explicitly defined (like components types)
                    # Check class fields first, then model_extra
                    if part in target.model_fields:  # Access class attribute here
                        target = getattr(target, part, None)
                    elif target.model_extra and part in target.model_extra:
                        target = target.model_extra[part]
                    else:
                        # Special handling for components sub-types common structure
                        if part == "components" and hasattr(target, "components"):
                            target = getattr(target, "components")
                        elif hasattr(target, part):  # Fallback check
                            target = getattr(target, part, None)
                        else:
                            target = None  # Part not found
                elif isinstance(target, dict):
                    target = target.get(part)
                else:
                    raise ValueError(
                        f"Cannot traverse part '{part}' in reference '{ref_str}' from type {type(target)}"
                    )
                if target is None:
                    raise ValueError(
                        f"Reference part '{part}' not found in path '{ref_str}'"
                    )
            if isinstance(target, Reference):
                return _resolve_ref(target, openapi)
            return target
        except (AttributeError, KeyError, IndexError, TypeError, ValueError) as e:
            raise ValueError(f"Failed to resolve reference '{ref_str}': {e}") from e
    return item


def _extract_schema_as_dict(
    schema_obj: Union[Schema, Reference], openapi: OpenAPI
) -> JsonSchema:
    """Resolves a schema/reference and returns it as a dictionary."""
    resolved_schema = _resolve_ref(schema_obj, openapi)
    if isinstance(resolved_schema, Schema):
        # Using exclude_none=True might be better than exclude_unset sometimes
        return resolved_schema.model_dump(mode="json", by_alias=True, exclude_none=True)
    elif isinstance(resolved_schema, dict):
        logger.warning(
            "Resolved schema reference resulted in a dict, not a Schema model."
        )
        return resolved_schema
    else:
        ref_str = getattr(schema_obj, "ref", "unknown")
        logger.warning(
            f"Expected Schema after resolving ref '{ref_str}', got {type(resolved_schema)}. Returning empty dict."
        )
        return {}


def _convert_to_parameter_location(param_in: str) -> ParameterLocation:
    """Convert string parameter location to our ParameterLocation type."""
    if param_in == "path":
        return "path"
    elif param_in == "query":
        return "query"
    elif param_in == "header":
        return "header"
    elif param_in == "cookie":
        return "cookie"
    else:
        logger.warning(f"Unknown parameter location: {param_in}, defaulting to 'query'")
        return "query"


def _extract_parameters(
    operation_params: Optional[List[Union[Parameter, Reference]]],
    path_item_params: Optional[List[Union[Parameter, Reference]]],
    openapi: OpenAPI,
) -> List[ParameterInfo]:
    """Extracts and resolves parameters using corrected attribute names."""
    extracted_params: List[ParameterInfo] = []
    seen_params: Dict[
        Tuple[str, str], bool
    ] = {}  # Use string keys to avoid type issues
    all_params_refs = (operation_params or []) + (path_item_params or [])

    for param_or_ref in all_params_refs:
        try:
            parameter = cast(Parameter, _resolve_ref(param_or_ref, openapi))
            if not isinstance(parameter, Parameter):
                # ... (error logging remains the same)
                continue

            # --- *** CORRECTED ATTRIBUTE ACCESS HERE *** ---
            param_in = parameter.param_in  # CORRECTED: Use 'param_in'
            param_location = _convert_to_parameter_location(param_in)
            param_schema_obj = parameter.param_schema  # CORRECTED: Use 'param_schema'
            # --- *** ---

            param_key = (parameter.name, param_in)
            if param_key in seen_params:
                continue
            seen_params[param_key] = True

            param_schema_dict = {}
            if param_schema_obj:  # Check if schema exists
                param_schema_dict = _extract_schema_as_dict(param_schema_obj, openapi)
            elif parameter.content:
                # Handle complex parameters with 'content'
                first_media_type = next(iter(parameter.content.values()), None)
                if (
                    first_media_type and first_media_type.media_type_schema
                ):  # CORRECTED: Use 'media_type_schema'
                    param_schema_dict = _extract_schema_as_dict(
                        first_media_type.media_type_schema, openapi
                    )
                    logger.debug(
                        f"Parameter '{parameter.name}' using schema from 'content' field."
                    )

            # Manually create ParameterInfo instance using correct field names
            param_info = ParameterInfo(
                name=parameter.name,
                location=param_location,  # Use converted parameter location
                required=parameter.required,
                schema=param_schema_dict,  # Populate 'schema' field in IR
                description=parameter.description,
            )
            extracted_params.append(param_info)

        except (
            ValidationError,
            ValueError,
            AttributeError,
            TypeError,
        ) as e:  # Added TypeError
            param_name = getattr(
                param_or_ref, "name", getattr(param_or_ref, "ref", "unknown")
            )
            logger.error(
                f"Failed to extract parameter '{param_name}': {e}", exc_info=False
            )

    return extracted_params


def _extract_request_body(
    request_body_or_ref: Optional[Union[RequestBody, Reference]], openapi: OpenAPI
) -> Optional[RequestBodyInfo]:
    """Extracts and resolves the request body using corrected attribute names."""
    if not request_body_or_ref:
        return None
    try:
        request_body = cast(RequestBody, _resolve_ref(request_body_or_ref, openapi))
        if not isinstance(request_body, RequestBody):
            # ... (error logging remains the same)
            return None

        content_schemas: Dict[str, JsonSchema] = {}
        if request_body.content:
            for media_type_str, media_type_obj in request_body.content.items():
                # --- *** CORRECTED ATTRIBUTE ACCESS HERE *** ---
                if (
                    isinstance(media_type_obj, MediaType)
                    and media_type_obj.media_type_schema
                ):  # CORRECTED: Use 'media_type_schema'
                    # --- *** ---
                    try:
                        # Use the corrected attribute here as well
                        schema_dict = _extract_schema_as_dict(
                            media_type_obj.media_type_schema, openapi
                        )
                        content_schemas[media_type_str] = schema_dict
                    except ValueError as schema_err:
                        logger.error(
                            f"Failed to extract schema for media type '{media_type_str}' in request body: {schema_err}"
                        )
                elif not isinstance(media_type_obj, MediaType):
                    logger.warning(
                        f"Skipping invalid media type object for '{media_type_str}' (type: {type(media_type_obj)}) in request body."
                    )
                elif not media_type_obj.media_type_schema:  # Corrected check
                    logger.warning(
                        f"Skipping media type '{media_type_str}' in request body because it lacks a schema."
                    )

        return RequestBodyInfo(
            required=request_body.required,
            content_schema=content_schemas,
            description=request_body.description,
        )
    except (ValidationError, ValueError, AttributeError) as e:
        ref_name = getattr(request_body_or_ref, "ref", "unknown")
        logger.error(
            f"Failed to extract request body '{ref_name}': {e}", exc_info=False
        )
        return None


# --- Main Parsing Function ---
# (No changes needed in the main loop logic, only in the helpers it calls)
def parse_openapi_to_http_routes(openapi_dict: Dict[str, Any]) -> List[HTTPRoute]:
    """
    Parses an OpenAPI schema dictionary into a list of HTTPRoute objects
    using the openapi-pydantic library.
    """
    routes: List[HTTPRoute] = []
    try:
        openapi: OpenAPI = OpenAPI.model_validate(openapi_dict)
        logger.info(f"Successfully parsed OpenAPI schema version: {openapi.openapi}")
    except ValidationError as e:
        logger.error(f"OpenAPI schema validation failed: {e}")
        error_details = e.errors()
        logger.error(f"Validation errors: {error_details}")
        raise ValueError(f"Invalid OpenAPI schema: {error_details}") from e

    if not openapi.paths:
        logger.warning("OpenAPI schema has no paths defined.")
        return []

    for path_str, path_item_obj in openapi.paths.items():
        if not isinstance(path_item_obj, PathItem):
            logger.warning(
                f"Skipping invalid path item object for path '{path_str}' (type: {type(path_item_obj)})"
            )
            continue

        path_level_params = path_item_obj.parameters

        # Iterate through possible HTTP methods defined in the PathItem model fields
        # Use model_fields from the class, not the instance
        for method_lower in PathItem.model_fields.keys():
            if method_lower not in [
                "get",
                "put",
                "post",
                "delete",
                "options",
                "head",
                "patch",
                "trace",
            ]:
                continue

            operation: Optional[Operation] = getattr(path_item_obj, method_lower, None)

            if operation and isinstance(operation, Operation):
                method_upper = cast(HttpMethod, method_lower.upper())
                logger.debug(f"Processing operation: {method_upper} {path_str}")
                try:
                    parameters = _extract_parameters(
                        operation.parameters, path_level_params, openapi
                    )
                    request_body_info = _extract_request_body(
                        operation.requestBody, openapi
                    )

                    route = HTTPRoute(
                        path=path_str,
                        method=method_upper,
                        operation_id=operation.operationId,
                        summary=operation.summary,
                        description=operation.description,
                        tags=operation.tags or [],
                        parameters=parameters,
                        request_body=request_body_info,
                    )
                    routes.append(route)
                    logger.info(
                        f"Successfully extracted route: {method_upper} {path_str}"
                    )
                except Exception as op_error:
                    op_id = operation.operationId or "unknown"
                    logger.error(
                        f"Failed to process operation {method_upper} {path_str} (ID: {op_id}): {op_error}",
                        exc_info=True,
                    )

    logger.info(f"Finished parsing. Extracted {len(routes)} HTTP routes.")
    return routes


# --- Example Usage (Optional) ---
if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s"
    )  # Set to INFO

    petstore_schema = {
        "openapi": "3.1.0",  # Keep corrected version
        "info": {"title": "Simple Pet Store API", "version": "1.0.0"},
        "paths": {
            "/pets": {
                "get": {
                    "summary": "List all pets",
                    "operationId": "listPets",
                    "tags": ["pets"],
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "description": "How many items to return",
                            "required": False,
                            "schema": {"type": "integer", "format": "int32"},
                        }
                    ],
                    "responses": {"200": {"description": "A paged array of pets"}},
                },
                "post": {
                    "summary": "Create a pet",
                    "operationId": "createPet",
                    "tags": ["pets"],
                    "requestBody": {"$ref": "#/components/requestBodies/PetBody"},
                    "responses": {"201": {"description": "Null response"}},
                },
            },
            "/pets/{petId}": {
                "get": {
                    "summary": "Info for a specific pet",
                    "operationId": "showPetById",
                    "tags": ["pets"],
                    "parameters": [
                        {
                            "name": "petId",
                            "in": "path",
                            "required": True,
                            "description": "The id of the pet",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "X-Request-ID",
                            "in": "header",
                            "required": False,
                            "schema": {"type": "string", "format": "uuid"},
                        },
                    ],
                    "responses": {"200": {"description": "Information about the pet"}},
                },
                "parameters": [  # Path level parameter example
                    {
                        "name": "traceId",
                        "in": "header",
                        "description": "Common trace ID",
                        "required": False,
                        "schema": {"type": "string"},
                    }
                ],
            },
        },
        "components": {
            "schemas": {
                "Pet": {
                    "type": "object",
                    "required": ["id", "name"],
                    "properties": {
                        "id": {"type": "integer", "format": "int64"},
                        "name": {"type": "string"},
                        "tag": {"type": "string"},
                    },
                }
            },
            "requestBodies": {
                "PetBody": {
                    "description": "Pet object",
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Pet"}
                        }
                    },
                }
            },
        },
    }

    print("--- Parsing Pet Store Schema using openapi-pydantic (Corrected) ---")
    try:
        http_routes = parse_openapi_to_http_routes(petstore_schema)
        print(f"\n--- Extracted {len(http_routes)} Routes ---")
        for i, route in enumerate(http_routes):
            print(f"\nRoute {i + 1}:")
            # Use model_dump for clean JSON-like output, show aliases from IR model
            print(
                json.dumps(route.model_dump(by_alias=True, exclude_none=True), indent=2)
            )  # exclude_none is often cleaner
    except ValueError as e:
        print(f"\nError parsing schema: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
