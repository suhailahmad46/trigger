# FastAPI Trigger Application

This FastAPI application provides endpoints to create, schedule, fire, and manage triggers. It uses Redis to log events with a built-in retention and archival mechanism and demonstrates integration with an external API.

## Features

- **Trigger Management:** Create, update, list, and delete triggers.
- **Scheduling:** Schedule triggers to fire after a specified interval with optional repeat functionality.
- **API Trigger:** Fire triggers that call an external API (Agify.io) and log the response.
- **Event Logging:** Logs trigger events to Redis with automatic expiration and archival.
- **Authentication:** Secured endpoints using HTTP Basic Authentication.

## Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/) (recommended for multi-container setups)
- (For local development) Python 3.8+ and a local Redis installation.

## Getting Started

### Running Locally (Without Docker)

1. **Install Python Dependencies:**

   Make sure you have Python 3.8+ installed. Then install the required packages:

   ```bash
   pip install fastapi uvicorn redis requests pydantic
