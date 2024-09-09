from fastapi import FastAPI, Request, Query, BackgroundTasks
from fastapi.responses import FileResponse
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

    return FileResponse(png_file)

# https://velocity.show/%60As%20you%20may%20know%2C%20our%20project%20%22kickstarting%20the%20world%E2%80%99s%20largest%20completion%20contract%20ADNOC%20DCE%22%20is%20awarded%20with%20Special%20Recognition%20for%20Integration%20and%20Collaboration.%20%22Congratulations%20to%20Ying%20Yue%20and%20whole%20CPU%20team%21%21%22%20%26%23%3B%0A%26%23%3B%20I%20would%20like%20to%20thank%20all%20of%20our%20CS%20%23%3B%26%23%3B%201.%20%26%23%3B%20closely%20engage%20with%20ANDNOC%20project%20team%20about%20the%20demand%2Fdelivery%23%3B%26%23%3B%202.%20%26%23%3B%20smartly%20quote%20all%20parts%20without%20issues%23%3B%26%23%3B%203.%20%26%23%3B%20diligently%20follow%20up%20about%20SO%20status%20no%20matter%20it%E2%80%99s%20expedite%20or%20defer%20or%20expedite%20after%20defer%23%3B%26%23%3B%204.%20%26%23%3B%20proactively%20work%20with%20planning%20team%20about%20delivery%20plan%23%3B%26%23%3B%20%26%23%3B%20I%20would%20like%20to%20say%20this%20is%20a%20great%20teamwork%20we%20do%2C%20and%20I%20see%20these%20points%20in%20our%20daily%20job%20as%20well.%20%26%23%3B%20This%20gives%20me%20an%20opportunity%20to%20shout%20loudly%20to%20all.%20%26%23%3B%20Proud%20of%20you%21%21%22
