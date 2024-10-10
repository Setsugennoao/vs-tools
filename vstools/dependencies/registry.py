import importlib.util
from dataclasses import dataclass, field
from typing import Iterable

from stgpytools import CustomPermissionError, CustomTypeError

from .enums import InstallModeEnum

__all__: list[str] = [
    'PackageDependencyRegistry',
    'dependency_registry',

    'PluginInfo',
    'PackageInfo',
]


@dataclass
class PluginInfo:
    """Information about a plugin."""

    required_functions: list[str] = field(default_factory=list)
    """A list of function names that must be provided by the plugin."""

    url: str | None = None
    """The URL where the plugin can be downloaded or found, if available."""

    optional: bool = False
    """Indicates whether the plugin is optional or required."""


@dataclass
class PackageInfo:
    """Information about a package."""

    required_functions: list[str] = field(default_factory=list)
    """A list of function names that must be provided by the package."""

    version: str | None = None
    """The version of the package, if specified."""

    url: str | None = None
    """The URL where the package can be downloaded or found, if available."""

    optional: bool = False
    """Indicates whether the package is optional or required."""


@dataclass
class PackageDependencyRegistry:
    """A registry for managing package dependencies and plugins."""

    plugin_registry: dict[str, dict[str, PluginInfo]] = field(default_factory=dict)
    """
    A registry of plugins and their metadata.

    Structure:
    {
        package_name (str): {
            plugin_name (str): PluginInfo,
            #  Additional plugins...
        },
        #  Additional packages...
    }
    """

    package_registry: dict[str, dict[str, PackageInfo]] = field(default_factory=dict)
    """
    A registry of packages and their metadata.

    Structure:
    {
        package_name (str): PackageInfo,
        #  Additional packages...
    }
    """

    vsrepo_available: bool = field(init=False)
    """A flag indicating whether the 'vsrepo' module is available."""

    install_mode: InstallModeEnum = field(default=InstallModeEnum.PROMPT)
    """The installation mode for handling missing dependencies."""

    def __post_init__(self) -> None:
        self.vsrepo_available = importlib.util.find_spec('vsrepo') is not None
        # TODO: Ensure vspreview's setting is set here if possible

    def set_install_mode(self, install_mode: InstallModeEnum) -> None:
        """
        Set the installation mode for handling missing dependencies.

        This method can only be called from the vspreview package.
        This is to prevent abuse from package maintainers.

        :param install_mode:                The installation mode to set.
        :type install_mode:                 The installation mode.

        :raises CustomPermissionError:      If called from a package other than vspreview.
        """

        from ..utils.package import get_calling_package

        if get_calling_package() != 'vspreview':
            raise CustomPermissionError("This method can only be called from the vspreview package.")

        if not isinstance(install_mode, InstallModeEnum):
            raise CustomTypeError(
                "install_mode must be an instance of InstallModeEnum, "
                f"not {type(install_mode).__name__}", self.set_install_mode
            )

        self.install_mode = install_mode

    def add_plugin(
        self,
        dependency: str,
        functions: Iterable[str] | None = None,
        parent_package: str | None = None,
        *,
        url: str | None = None,
        optional: bool = False,
    ) -> None:
        """
        Register a plugin for a package.

        :param dependency:              The name of the plugin to depend on.
        :param functions:               A list of functions used by the plugin.
                                        A check is performed to ensure the installed plugin has these functions.
        :param parent_package:          The name of the package that depends on this plugin.
        :param url:                     The url to the plugin's download page. Defaults to None.
        :param optional:                Whether the plugin is optional. Defaults to False.
        """

        if not parent_package:
            from ..utils.package import get_calling_package

            parent_package = get_calling_package()

        if not dependency:
            return

        if parent_package not in self.plugin_registry:
            self.plugin_registry[parent_package] = {}

        plugin_info = self.plugin_registry[parent_package].get(dependency, PluginInfo())

        if functions:
            new_functions = [functions] if isinstance(functions, str) else functions
            plugin_info.required_functions.extend(list(set(new_functions) - set(plugin_info.required_functions)))

        if url:
            plugin_info.url = url

        plugin_info.optional = optional

        self.plugin_registry[parent_package][dependency] = plugin_info

    def add_package(
        self,
        dependency: str,
        functions: str | list[str] | None = None,
        parent_package: str | None = None,
        *,
        version: str | None = None,
        optional: bool = False,
        url: str | None = None,
    ) -> None:
        """
        Register a package dependency.

        :param dependency:              The name of the dependency to register.
        :param functions:               A function or list of functions to check for in the dependency.
                                        Defaults to None.
        :param parent_package:          The name of the package that depends on this dependency.
        :param version:                 The required version of the dependency. Defaults to None.
        :param optional:                Whether the dependency is optional. Defaults to False.
        :param url:                     The url to the dependency's download page. Defaults to None.
        """

        if not parent_package:
            from ..utils.package import get_calling_package

            parent_package = get_calling_package()

        if not dependency:
            return

        if parent_package not in self.package_registry:
            self.package_registry[parent_package] = {}

        package_info = self.package_registry[parent_package].get(dependency, PackageInfo())

        if functions:
            new_functions = [functions] if isinstance(functions, str) else functions
            package_info.required_functions.extend(list(set(new_functions) - set(package_info.required_functions)))

        if url:
            package_info.url = url

        if version:
            package_info.version = version

        package_info.optional = optional

        self.package_registry[parent_package][dependency] = package_info


dependency_registry = PackageDependencyRegistry()
