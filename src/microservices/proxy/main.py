import logging
from fastapi import FastAPI, Request, HTTPException
import httpx
import os
import random
import time
import json
import re


app = FastAPI()

# Настройка логгера
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("proxy-service")

MONOLITH_URL = os.getenv("MONOLITH_URL", "http://monolith:8080")
MOVIES_SERVICE_URL = os.getenv("MOVIES_SERVICE_URL", "http://movies-service:8081")
GRADUAL_MIGRATION = os.getenv("GRADUAL_MIGRATION", "false").lower() == "true"
MOVIES_MIGRATION_PERCENT = int(os.getenv("MOVIES_MIGRATION_PERCENT", "0"))

client = httpx.AsyncClient()

def extract_id(content: bytes) -> str:
    try:
        data = json.loads(content)
        if isinstance(data, list) and len(data) > 0:
            return str(data[0].get('id', '1'))
        return str(data.get('id', '1'))
    except:
        return '1'

@app.api_route("/api/movies", methods=["GET", "POST", "PUT", "DELETE"])
async def movies_proxy(request: Request):
    start_time = time.time()
    use_movies_service = False
    if GRADUAL_MIGRATION:
        if random.randint(1, 100) <= MOVIES_MIGRATION_PERCENT:
            use_movies_service = True

    target_url = MOVIES_SERVICE_URL if use_movies_service else MONOLITH_URL
    path = str(request.url.path) + ("?" + str(request.url.query) if request.url.query else "")
    proxied_url = target_url + path.replace("/api/movies", "/api/movies")

    logger.debug(f"Incoming request {request.method} {request.url}")
    logger.debug(f"Proxying to: {proxied_url}")

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
        elapsed_ms = (time.time() - start_time) * 1000
        logger.debug(f"Response from backend: {response.status_code} in {elapsed_ms:.2f}ms")

        if request.method == "POST":
            backend_path = str(request.url.path)

            if any(path in backend_path for path in ["/api/users", "/api/payments", "/api/subscriptions"]):

                new_id = extract_id(response.content)
                if new_id and new_id != '1':
                    headers = dict(response.headers)
                    headers["Location"] = f"{request.url.path}/{new_id}"
                    return response.content, 201, headers.items()

        return response.content, response.status_code, response.headers.items()

    except httpx.RequestError as e:
        logger.error(f"Error during proxying request: {e}")
        raise HTTPException(status_code=502, detail=f"Ошибка проксирования: {e}")

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def fallback_proxy(path: str, request: Request):
    start_time = time.time()
    target_url = MONOLITH_URL
    clean_path = str(request.url.path) + ("?" + str(request.url.query) if request.url.query else "")
    full_url = target_url + clean_path

    logger.info(f"[{request.method}] {request.url.path} → monolith:{full_url}")

    body = await request.body()
    headers = dict(request.headers)
    headers.pop("host", None)

    response = None
    try:
        response = await client.request(
            method=request.method,
            url=full_url,
            content=body,
            headers=headers,
            timeout=10.0
        )
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"Monolith response: {response.status_code} in {elapsed_ms:.2f}ms")
    except httpx.RequestError as e:
        logger.error(f"Monolith error: {e}")
        raise HTTPException(status_code=502, detail=f"Monolith unavailable: {e}")


    from fastapi.responses import StreamingResponse 
    
    backend_path = str(request.url.path)
    
    if (request.method == "POST" and 
        backend_path.startswith(("/api/users", "/api/payments", "/api/subscriptions"))):
        new_id = extract_id(response.content)
        
        if new_id and new_id != '1':
            headers = dict(response.headers)
            headers["Location"] = f"{request.url.path}/{new_id}"
            return StreamingResponse(
                response.aiter_bytes(),
                status_code=201,
                headers=headers
            )
    
    return StreamingResponse(
        response.aiter_bytes(),
        status_code=response.status_code,
        headers=dict(response.headers)
    )
