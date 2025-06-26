# ZypherAI ML Prediction Platform

A high-performance, scalable web application for machine learning model deployment and inference simulation, built with FastAPI and Redis.

---

##  Approach

This project simulates a production-ready ML inference platform with the following design:

- **Synchronous and Asynchronous Prediction**: Implemented via HTTP headers; async jobs are enqueued to Redis Streams.
- **Redis-backed Queuing**: Ensures decoupled, scalable background processing.
- **FastAPI**: Chosen over Flask for async support, auto-generated docs, and type validation.
- **Containerization**: Dockerized services for Redis, web API, and optional Redis Commander.
- **Mock ML Model**: Simulated latency and logic in a lightweight manner.

---
## Requirements

- Python 3.11+
- Redis 7+
- Docker & Docker Compose (for containerized deployment)

---

## Quick Start

### With Docker Compose (Recommended)

```bash
cd SDE_Assessment_Bilal_Shakeel
docker-compose up --build
```

- API: http://localhost:8080
- Swagger UI: http://localhost:8080/docs

### Manual Setup

```bash
pip install -r requirements.txt
redis-server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

---

## API Usage

### Synchronous

```bash
curl -X 'POST' \
  'http://localhost:8080/predict' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{"input": "Sample input data"}'
```

### Asynchronous
**Submit:**
```bash
curl -X POST "http://localhost:8080/predict" \
  -H "Content-Type: application/json" \
  -H "Async-Mode: true" \
  -d '{"input": "Sample input data"}'
```

**Check Result:**
```bash
curl "http://localhost:8080/predict/<prediction_id>"
```

---

## Assumptions

- The ML model is mocked (returns hash of input), simulating latency.
- Redis is used as both the broker and in-memory DB.
- Workers are single-threaded and stateless.
- One background worker is sufficient for the simulation.

---

## Alternatives Not Selected

- **RabbitMQ/Kafka**: Overhead was too high for a single-node simulation.
- **Flask**: Lacks async support and automatic OpenAPI schema generation.

---

## Testing

```bash
pytest
pytest --cov=app --cov-report=html
```

---

## Monitoring & Debugging

- Health Check: `curl http://localhost:8080/health`
- Metrics: `curl http://localhost:8080/metrics`
- Redis CLI: `redis-cli`
- Logs: `docker-compose logs`

---

---

## Security

- Non-root Docker user
- Input validation (Pydantic)
- Structured error logging

---
