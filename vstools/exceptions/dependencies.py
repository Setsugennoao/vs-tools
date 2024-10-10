import importlib.util
import warnings
from typing import Any

from stgpytools import CustomValueError, FuncExceptT

from ..dependencies.registry import PackageInfo, PluginInfo, dependency_registry
from ..dependencies.enums import InstallModeEnum

__all__: list[str] = [
    'DependencyRegistryError',

    'PluginNotFoundError',
    'PackageNotFoundError',
]


prompt_y = ('yes', 'y', '')
prompt_opts = "(yes/no) [yes]"


class DependencyRegistryError(CustomValueError):
    """Base class for dependency registry errors."""

    @classmethod
    def _get_package(cls, parent_package: str | None = None) -> str:
        """
        Get the package name, either from the provided value or by auto-detection.

        :param parent_package:      The name of the parent package. If None, auto-detect.

        :return:                    The package name.
        """

        if parent_package is not None:
            return parent_package

        from ..utils.package import get_calling_package

        return get_calling_package(3)

    @staticmethod
    def _check_pypi(package: str) -> bool:
        """
        Check if the package is available on PyPI and install if necessary based on the install mode.

        :param package:     The package to check.

        :return:            True if the package was installed or already exists, False otherwise.
        """

        if dependency_registry.install_mode is InstallModeEnum.MANUAL:
            return False

        try:
            importlib.import_module(package)
            return True
        except ImportError:
            pass

        import subprocess
        import sys

        def run_pip(args: list[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.run([sys.executable, '-m', 'pip'] + args, capture_output=True, text=True, check=False)

        if importlib.util.find_spec(package) is not None:
            return True

        print(f'Package \'{package}\' is not installed.')

        should_install = DependencyRegistryError._prompt_user_for_install(package)

        if not should_install:
            print(f'Installation of \'{package}\' cancelled.')
            return False

        result = run_pip(['install', package])

        if result.returncode == 0:
            print(f'Successfully installed \'{package}\'')
            return True

        print(f'Failed to install \'{package}\'. Error: {result.stderr}')
        return False

    @staticmethod
    def _check_vsrepo(plugin: str) -> bool:
        """
        Check if the plugin is available in VSRepo and install if necessary based on the install mode.

        :param plugin:      The plugin to check.

        :return:            True if the plugin was installed or already exists, False otherwise.
        """

        if dependency_registry.install_mode is InstallModeEnum.MANUAL:
            return False

        if not dependency_registry.vsrepo_available:
            return False

        import subprocess

        def run_vsrepo(args: Any) -> Any:
            try:
                return subprocess.run(['vsrepo'] + args, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                return e
            except FileNotFoundError:
                print('Failed to run vsrepo: command not found')

        result = run_vsrepo(['available', plugin])

        if result.returncode != 0 or 'not found' in result.stdout.lower():
            return False

        print(f'Plugin \'{plugin}\' is available in VSRepo but not installed.')

        should_install = DependencyRegistryError._prompt_user_for_install(plugin)

        if not should_install:
            print(f'Installation of \'{plugin}\' cancelled.')
            return False

        result = run_vsrepo(['install', plugin])

        if result and result.returncode == 0:
            print(f'Successfully installed \'{plugin}\'')
            return True

        print(f'Failed to install \'{plugin}\'')
        return False

    @staticmethod
    def _prompt_user_for_install(package_or_plugin: str) -> bool:
        """
        Prompt the user for installation based on the install mode.

        :param package_or_plugin:    The package or plugin name to install.

        :return:                     True if the user wants to install, False otherwise.
        """

        if dependency_registry.install_mode is InstallModeEnum.AUTO:
            return True

        try:
            prompt = input(f'Do you want to install \'{package_or_plugin}\'? {prompt_opts}: ')
            return prompt.lower().strip() in prompt_y
        except EOFError as e:
            msg = f'Could not prompt the user to install \'{package_or_plugin}\'! '
            msg += 'Please install this plugin/package manually'

            try:
                from vspreview import is_preview

                if is_preview():
                    msg += ' or set the dependency install mode in VSPreview to \'auto\''
            except ModuleNotFoundError:
                pass

            msg += f'! Error: {e}'

            warnings.warn(msg, UserWarning)

            return False

    @classmethod
    def _get_missing_functions(cls, plugin_functions: list[str], plugin: str) -> list[str]:
        from vstools import core

        plugin_obj = getattr(core, plugin)

        return [
            f for f in plugin_functions if not hasattr(plugin_obj, f)
            and not hasattr(getattr(plugin_obj, f, None), '__call__')
        ]

    @classmethod
    def _format_message(
        cls, base_msg: str, missing: list[str],
        version: str | None = None, url: str | None = None,
        prompt_update: bool = False
    ) -> str:
        msg = f'{base_msg}: [{', '.join(missing)}]. '

        if version:
            msg += f'Required version: {version}. '

        if url:
            msg += f'Download URL: {url}'

        if prompt_update:
            msg += 'You may need to update!'

        return msg


class PluginNotFoundError(DependencyRegistryError):
    """Raised when a required plugin is not found in the registry."""

    def __init__(
        self, func: FuncExceptT, parent_package: str, plugin: str,
        message: str = 'Plugin \'{plugin}\' not found for package \'{parent_package}\'',
        **kwargs: Any
    ) -> None:
        super().__init__(message, func, parent_package=parent_package, plugin=plugin, **kwargs)

    @classmethod
    def check(
        cls, func: FuncExceptT, plugins: str | list[str] | None = None,
        message: str | None = None, parent_package: str | None = None, **kwargs: Any
    ) -> None:
        """
        Check if plugin(s) exist in the registry and raise an error if they don't.

        :param func:                    The function to check.
        :param plugins:                 The plugin or list of plugins to check for.
                                        If None, check all plugins in the caller package's namespace.
        :param message:                 Optional custom error message.
        :param parent_package:          The package name to check for. If None, check all packages.
        :param kwargs:                  Additional keyword arguments.

        :raises PluginNotFoundError:    If any plugin is not found in the registry.
        """

        from vstools import core

        parent_package = cls._get_package(parent_package)

        if plugins is not None:
            plugins_to_check = [plugins] if isinstance(plugins, str) else plugins
        else:
            plugins_to_check = list(dependency_registry.plugin_registry.get(parent_package, {}).keys())

        missing_plugins = []
        missing_functions = {}

        for plugin in plugins_to_check:
            plugin_data = dependency_registry.plugin_registry[parent_package].get(plugin)

            if plugin_data and plugin_data.optional:
                if not hasattr(core, plugin):
                    warnings.warn(
                        f'Optional plugin \'{plugin}\' for \'{parent_package}\' is not installed.', UserWarning
                    )

                continue

            if not hasattr(core, plugin):
                if cls._check_vsrepo(plugin):
                    continue

                missing_plugins.append(plugin)
                continue

            if not plugin_data or not plugin_data.required_functions:
                continue

            if missing_funcs := cls._get_missing_functions(plugin_data.required_functions, plugin):
                missing_functions[plugin] = missing_funcs

        if missing_plugins or missing_functions:
            error_messages = []

            if missing_plugins:
                error_messages.append(
                    f'Plugin(s) not found for package \'{parent_package}\': {', '.join(missing_plugins)}'
                )

            for plugin, funcs in missing_functions.items():
                plugin_info: PluginInfo = dependency_registry.plugin_registry[parent_package][plugin]

                error_messages.append(cls._format_message(
                    f'Plugin \'{plugin}\' for package \'{parent_package}\' is missing the following function(s)',
                    missing=funcs, url=plugin_info.url, prompt_update=True
                ))

            raise cls(
                func, parent_package,
                ', '.join(missing_plugins + list(missing_functions.keys())),
                message or '\n'.join(error_messages),
                **kwargs
            )


class PackageNotFoundError(DependencyRegistryError):
    """Raised when a required package is not found in the registry."""

    def __init__(
        self, func: FuncExceptT, parent_package: str,
        package: str | None = None, message: str | None = None,
        **kwargs: Any
    ) -> None:
        super().__init__(
            message or f'Package \'{package or parent_package}\' not found in the registry',
            func, parent_package=parent_package, **kwargs
        )

    @classmethod
    def check(
        cls, func: FuncExceptT, packages: str | list[str] | None = None,
        message: str | None = None, parent_package: str | None = None, **kwargs: Any
    ) -> None:
        """
        Check if package(s) exist in the registry and raise an error if they don't.

        :param func:                    The function to check.
        :param packages:                The package or list of packages to check for.
                                        If None, check all packages in the caller package's namespace.
        :param message:                 Optional custom error message.
        :param parent_package:          The package name to check for. If None, check all packages.
        :param kwargs:                  Additional keyword arguments.

        :raises PackageNotFoundError:   If any package is not found in the registry.
        """

        parent_package = cls._get_package(parent_package)

        if packages is not None:
            packages_to_check = [packages] if isinstance(packages, str) else packages
        else:
            packages_to_check = list(dependency_registry.package_registry.get(parent_package, {}).keys())

        missing_packages = []
        missing_functions = {}

        for pkg in packages_to_check:
            package_data: PackageInfo = dependency_registry.package_registry[parent_package][pkg]

            if package_data.optional:
                if importlib.util.find_spec(pkg) is None:
                    warnings.warn(
                        f'Optional package \'{pkg}\' for \'{parent_package}\' is not installed.', UserWarning
                    )

                continue

            if not package_data.required_functions:
                continue

            if cls._check_pypi(pkg) or cls._check_vsrepo(pkg):
                continue

            if missing_funcs := cls._get_missing_functions(package_data.required_functions, pkg):
                missing_functions[pkg] = missing_funcs

        if missing_packages or missing_functions:
            error_messages = []

            if missing_packages:
                error_messages.append(
                    f'Package(s) not found for package \'{parent_package}\': {', '.join(missing_packages)}'
                )

            for pkg, funcs in missing_functions.items():
                pkg_info = dependency_registry.package_registry[parent_package][pkg]

                error_messages.append(cls._format_message(
                    f'Package \'{pkg}\' for package \'{parent_package}\' is missing the following function(s)',
                    missing=funcs, url=pkg_info.url, version=pkg_info.version
                ))

            raise cls(
                func, parent_package,
                package=', '.join(missing_packages + list(missing_functions.keys())),
                message=message or '\n'.join(error_messages),
                **kwargs
            )
