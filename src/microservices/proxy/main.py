from fastapi import FastAPI, Request, HTTPException
import httpx
import os
import random

app = FastAPI()

MONOLITH_URL = os.getenv("MONOLITH_URL", "http://monolith:8080")
MOVIES_SERVICE_URL = os.getenv("MOVIES_SERVICE_URL", "http://movies-service:8081")
GRADUAL_MIGRATION = os.getenv("GRADUAL_MIGRATION", "false").lower() == "true"
MOVIES_MIGRATION_PERCENT = int(os.getenv("MOVIES_MIGRATION_PERCENT", "0"))

print("my proxy service")

# создание асинхр http клиентa для проксирования
client = httpx.AsyncClient()

@app.api_route("/api/movies", methods=["GET", "POST", "PUT", "DELETE"])
async def movies_proxy(request: Request):
    use_movies_service = False
    if GRADUAL_MIGRATION:
        if random.randint(1, 100) <= MOVIES_MIGRATION_PERCENT:
            use_movies_service = True
    else:
        use_movies_service = False

    target_url = MOVIES_SERVICE_URL if use_movies_service else MONOLITH_URL
    path = str(request.url.path) + ("?" + str(request.url.query) if request.url.query else "")
    proxied_url = target_url + path.replace("/api/movies", "/api/movies")

    print("\n proxied_url: ")
    print(proxied_url)

    body = await request.body()
    headers = dict(request.headers)
    headers.pop("host", None)

    try:
        response = await client.request(
            method=request.method,
            url=proxied_url,
            content=body,
            headers=headers,
            timeout=10.0
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка проксирования: {e}")

    return response.content, response.status_code, response.headers.items()

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def fallback_proxy(path: str, request: Request):
    target_url = MONOLITH_URL
    full_url = target_url + "/" + path + ("?" + str(request.url.query) if request.url.query else "")

    body = await request.body()
    headers = dict(request.headers)
    headers.pop("host", None)

    try:
        response = await client.request(
            method=request.method,
            url=full_url,
            content=body,
            headers=headers,
            timeout=10.0
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка проксирования: {e}")

    return response.content, response.status_code, response.headers.items()
