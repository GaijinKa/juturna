import pathlib
import logging

import uvicorn
import fastapi
import pydantic

import juturna as jt

from juturna.components._pipeline_manager import PipelineManager

app = fastapi.FastAPI()
logger = logging.getLogger('jt.remote_service')

class PipelineConfig(pydantic.BaseModel):
    version: str
    plugins: list
    pipeline: dict


@app.post('/process')
def process_node(pipeline_config: PipelineConfig):
    container = PipelineManager().create_pipeline(pipeline_config.model_dump())
    logger.info(f'created pipe, id {container["pipeline_id"]}')

    return container


def listen(
    host: str,
    port: int,
    folder: str,
    log_level: str,
    log_format: str,
    log_file: str,
):
    jt.log.formatter(log_format)
    jt.log.jt_logger().setLevel(log_level)

    if log_file:
        _handler = logging.FileHandler(log_file)
        jt.log.add_handler(_handler)

    logger.info('starting juturna service...')

    try:
        pathlib.Path(folder).mkdir(parents=True)
        logger.info(f'pipeline folder {folder} created')
    except FileExistsError:
        logger.info(f'pipeline folder {folder} exists, skipping...')

    PipelineManager().set_base_folder(folder)

    logger.info(f'service address: {host}:{port}')

    uvicorn.run(
        'juturna.cli.commands._juturna_service:app',
        host=host,
        port=port,
    )
