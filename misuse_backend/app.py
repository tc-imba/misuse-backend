from fastapi import FastAPI, Request, Query, BackgroundTasks
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from sqlmodel import Session, select
from datetime import datetime
import pathlib
import ipinfo
from loguru import logger

from redis import StrictRedis
from redis_cache import RedisCache
from redlock import RedLockFactory
from redlock import RedLockFactory

from misuse_backend.config import settings
from misuse_backend.models import History, engine

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

png_file = pathlib.Path(__file__).parent.parent / "download.png"
templates_dir = pathlib.Path(__file__).parent.parent / "templates"
# png_bytes = png_file.read_bytes()
templates = Jinja2Templates(directory=str(templates_dir.absolute()))

redis_client = StrictRedis(host="redis", decode_responses=True)
cache = RedisCache(redis_client=redis_client)
factory = RedLockFactory(
    connection_details=[
        {'host': 'redis', 'port': 6379, 'db': 0},
    ])
lock = factory.create_lock("distributed_lock")


def redlock_decorator(func):
    def wrapper(*args, **kwargs):
        with factory.create_lock("distributed_lock"):
            return func(*args, **kwargs)

    return wrapper


@cache.cache(ttl=14 * 24 * 60 * 60)
@redlock_decorator
def get_ipinfo(client_ip):
    handler = ipinfo.getHandler(settings.IPINFO_ACCESS_TOKEN)
    details = handler.getDetails(client_ip)
    city = details.all.get("city", "")
    region = details.all.get("region", "")
    country = details.all.get("country", "")
    result = list(filter(lambda x: len(x) > 0, [city, region, country]))
    geo = ", ".join(result)
    logger.info("ip: {}, city: {}, region: {}, country: {}, geo: {}", client_ip, city, region, country, geo)
    return geo


def record_path_background(url: str, method: str, client_ip: str, created_at: datetime):
    try:
        client_geo = get_ipinfo(client_ip)
    except Exception as e:
        logger.error("ip: {}, exception: {}", client_ip, str(e))
        client_geo = ""

    history = History(
        url=url,
        method=method,
        client_ip=client_ip,
        client_geo=client_geo,
        created_at=created_at,
    )
    session = Session(engine)
    session.add(history)
    session.commit()


@app.middleware("http")
async def remove_newline_in_url(request: Request, call_next):
    raw_url = str(request.url)
    url_prefix = f"{request.url.scheme}://{request.url.hostname}/"
    url_prefix_with_port = f"{request.url.scheme}://{request.url.hostname}:{request.url.port}/"
    if raw_url.startswith(url_prefix):
        raw_url = raw_url[len(url_prefix):]
    elif raw_url.startswith(url_prefix_with_port):
        raw_url = raw_url[len(url_prefix_with_port):]
    request.state.raw_url = raw_url
    request.scope['path'] = request.url.path.replace("\n", "\\n")
    response = await call_next(request)
    return response


@app.api_route("/", methods=["GET", "POST", "DELETE", "PUT", "OPTIONS", "HEAD", "PATCH", "TRACE"])
@app.api_route(
    "/{url:path}",
    methods=["GET", "POST", "DELETE", "PUT", "OPTIONS", "HEAD", "PATCH", "TRACE"]
)
def record_path(request: Request, background_tasks: BackgroundTasks, url: str = ""):
    query_params = str(request.query_params)
    if url == "" and len(query_params) == 0 and request.method == "GET":
        with Session(engine) as session:
            statement = select(History).order_by(History.id.desc()).limit(100)
            results = session.exec(statement)
            data = []
            for row in results:
                data.append(row.model_dump())

            return templates.TemplateResponse(
                request=request, name="index.html", context={"data": data}
            )

    if url != "favicon.ico":
        background_tasks.add_task(
            record_path_background,
            request.state.raw_url,
            request.method,
            request.client.host,
            datetime.utcnow(),
        )
    if settings.RETURN_TYPE == "png":
        return FileResponse(png_file)
    elif settings.RETURN_TYPE == "text":
        return PlainTextResponse(f"Hello, this is velocity.show at UTC time {datetime.utcnow()}.")

