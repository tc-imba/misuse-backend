import uvicorn
from misuse_backend.config import settings


def main():
    uvicorn.run(
        app="misuse_backend.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.WORKERS == 1 and settings.DEBUG,
        reload_dirs=["misuse_backend"],
        workers=settings.WORKERS,
        # log_level=settings.LOGGING_LEVEL,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == '__main__':
    main()
