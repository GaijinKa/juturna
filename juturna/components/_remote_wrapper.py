import importlib
import pathlib
import tomllib
import sys

from juturna.components import _mapper as mapper

from juturna.utils.log_utils import jt_logger
from juturna.components._synchronisers import _SYNCHRONISERS

_logger = jt_logger()


def load_class(folder_path):
    """Load a node fetching its properties from config.toml"""
    folder_path = pathlib.Path(folder_path)

    # folder exists?
    if not folder_path.exists() or not folder_path.is_dir():
        raise FileNotFoundError(f'folder not found: {folder_path}')

    # config.toml exists?
    config_toml = folder_path / 'config.toml'
    if not config_toml.exists():
        raise FileNotFoundError(f'config.toml not found in: {folder_path}')

    try:
        with open(config_toml, encoding='utf-8') as f:
            config = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f'Error parsing config.toml: {e}') from e

    # 3. Extract the class name from the toml
    remote_opts = config.get('remote')
    if not remote_opts or 'class_name' not in remote_opts:
        raise ValueError("Field 'class_name' not found in config.toml")

    class_name = remote_opts['class_name']

    # 4. by convention, the main python file has the same name as the folder
    python_filename = f'{folder_path.name}.py'
    python_file_path = folder_path / python_filename

    if not python_file_path.exists():
        raise FileNotFoundError(
            f'No Python file found in the folder. Searched: {python_filename}'
        )

    # 5. load the module dynamically
    module_name = (
        folder_path.name
    )  # unique name for the module in sys.modules is the folder name

    spec = importlib.util.spec_from_file_location(module_name, python_file_path)

    if spec is None:
        raise ImportError(f'Impossible to create spec for: {python_file_path}')

    module = importlib.util.module_from_spec(spec)

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise ImportError(
            f'Error executing module {python_file_path}: {e}'
        ) from e

    # 6. Get the class
    try:
        class_obj = getattr(module, class_name)
        return class_obj, config_toml
    except AttributeError:
        raise AttributeError(
            f"class '{class_name}' not found in module {python_filename}. "
            f'available classes: {
                [attr for attr in dir(module) if not attr.startswith("_")]
            }'
        ) from None

def instantiate_remote_wrapper(folder_path: str, **kwargs):
    """Instantiate a remote wrapper from a folder path"""
    class_obj, default_config_toml = load_class(folder_path)

    # if no synchroniser is specified in the configuration, pass None, so the
    # order of sync selection is:
    # 1) if available, synchroniser specified in the configuration
    # 2) if available, node synchroniser
    # 3) default passthrough synchroniser
    synchroniser = _SYNCHRONISERS.get(node_sync)

    concrete_node = _node_module(
        **default_config_toml,
        **{
            'node_name': node_name,
            'pipe_name': pipe_name,
            'synchroniser': synchroniser,
        },
    )
    try:
        instance = class_obj(**kwargs)
        return instance
    except Exception as e:
        raise RuntimeError(
            f'Error instantiating class {class_obj.__name__}: {e}'
        ) from e