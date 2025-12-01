# main.py
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import json
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("events-service")

app = FastAPI()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BROKERS", "kafka:9092")

# Pydantic модели событий
class MovieEvent(BaseModel):
    movie_id: int
    title: str
    action: str
    user_id: int | None = None
    rating: float | None = None
    genres: list[str] | None = None
    description: str | None = None

class UserEvent(BaseModel):
    user_id: int
    username: str | None = None
    email: str | None = None
    action: str
    timestamp: str

class PaymentEvent(BaseModel):
    payment_id: int
    user_id: int
    amount: float
    status: str
    timestamp: str
    method_type: str | None = None

# Инициализация Kafka Producer и Consumer
producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
consumer = AIOKafkaConsumer(
    "movie-events", "user-events", "payment-events",
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    group_id="events-service-group",
    auto_offset_reset="latest",
)

@app.on_event("startup")
async def startup_event():
    await producer.start()
    await consumer.start()
    # Запустим задачу фонового чтения сообщений
    asyncio.create_task(consume_messages())

@app.on_event("shutdown")
async def shutdown_event():
    await producer.stop()
    await consumer.stop()

@app.post("/api/events/movie", status_code=201)
async def create_movie_event(event: MovieEvent):
    try:
        message = event.json().encode("utf-8")
        await producer.send_and_wait("movie-events", message)
        return {"status": "success", "event": event}
    except Exception as e:
        logger.error(f"Error producing message: {e}")
        raise HTTPException(status_code=500, detail="Failed to produce event")

@app.post("/api/events/user", status_code=201)
async def create_user_event(event: UserEvent):
    try:
        message = event.json().encode("utf-8")
        await producer.send_and_wait("user-events", message)
        return {"status": "success", "event": event}
    except Exception as e:
        logger.error(f"Error producing user event: {e}")
        raise HTTPException(status_code=500, detail="Failed to produce user event")

@app.post("/api/events/payment", status_code=201)
async def create_payment_event(event: PaymentEvent):
    try:
        message = event.json().encode("utf-8")
        await producer.send_and_wait("payment-events", message)
        return {"status": "success", "event": event}
    except Exception as e:
        logger.error(f"Error producing payment event: {e}")
        raise HTTPException(status_code=500, detail="Failed to produce payment event")

async def consume_messages():
    try:
        async for msg in consumer:
            event_data = msg.value.decode("utf-8")
            logger.info(f"Consumed event on topic {msg.topic}: {event_data}")
    except Exception as e:
        logger.error(f"Error consuming messages: {e}")

@app.get("/api/events/health")
async def health_check():
    return {"status": True, "message": "Events service is healthy"}
