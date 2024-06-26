from fastapi import FastAPI, Request, Query, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates

from sqlmodel import Session, select
from datetime import datetime
import pathlib
import ipinfo
from loguru import logger

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


@app.get("/")
def root(request: Request, limit: int = Query(100), offset: int = Query(0)):
    with Session(engine) as session:
        statement = select(History)
        results = session.exec(statement)
        data = []
        for row in results:
            data.append(row.dict())

        return templates.TemplateResponse(
            request=request, name="index.html", context={"data": data}
        )


def record_path_background(url: str, query_params: str, method: str, client_ip: str, created_at: datetime):
    if query_params:
        url = f"{url}?{query_params}"

    client_geo = get_ipinfo(client_ip)

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


@app.api_route(
    "/{url:path}",
    methods=["GET", "POST", "DELETE", "PUT", "OPTIONS", "HEAD", "PATCH", "TRACE"]
)
def record_path(request: Request, url: str, background_tasks: BackgroundTasks) -> FileResponse:
    if url != "favicon.ico":
        background_tasks.add_task(
            record_path_background,
            url,
            str(request.query_params),
            request.method,
            request.client.host,
            datetime.utcnow(),
        )

    return FileResponse(png_file)
