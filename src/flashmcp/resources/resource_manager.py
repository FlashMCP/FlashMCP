import logging

from mcp.server.FlashMCP.resources import (
    ResourceManager as BaseResourceManager,
)

logger = logging.getLogger(__name__)


class ResourceManager(BaseResourceManager):
    """ResourceManager that adds methods to import resources from other managers."""

    def import_resources(
        self, manager: "ResourceManager", prefix: str | None = None
    ) -> None:
        """Import resources from another resource manager.

        Resources are imported with a prefixed URI if a prefix is provided. For example,
        if a resource has URI "data://users" and you import it with prefix "app+", the
        imported resource will have URI "app+data://users". If no prefix is provided,
        the original URI is used.

        Args:
            manager: The ResourceManager to import from
            prefix: A prefix to apply to the resource URIs, including the delimiter.
                   For example, "app+" would result in URIs like "app+data://users".
                   If None, the original URI is used.
        """
        for uri, resource in manager._resources.items():
            # Create prefixed URI and copy the resource with the new URI
            prefixed_uri = f"{prefix}{uri}" if prefix else uri

            # Log the import
            logger.debug(f"Importing resource with URI {uri} as {prefixed_uri}")

            # Store directly in resources dictionary
            self._resources[prefixed_uri] = resource

    def import_templates(
        self, manager: "ResourceManager", prefix: str | None = None
    ) -> None:
        """Import resource templates from another resource manager.

        Templates are imported with a prefixed URI template if a prefix is provided.
        For example, if a template has URI template "data://users/{id}" and you import
        it with prefix "app+", the imported template will have URI template
        "app+data://users/{id}". If no prefix is provided, the original URI template is used.

        Args:
            manager: The ResourceManager to import templates from
            prefix: A prefix to apply to the template URIs, including the delimiter.
                   For example, "app+" would result in URI templates like "app+data://users/{id}".
                   If None, the original URI template is used.
        """
        for uri_template, template in manager._templates.items():
            # Create prefixed URI template and copy the template with the new URI template
            prefixed_uri_template = (
                f"{prefix}{uri_template}" if prefix else uri_template
            )

            # Log the import
            logger.debug(
                f"Importing resource template with URI {uri_template} as {prefixed_uri_template}"
            )

            # Store directly in templates dictionary
            self._templates[prefixed_uri_template] = template
