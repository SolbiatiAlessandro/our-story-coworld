# One image serves the game and runs both players (baseline, and the Bedrock LLM player
# uploaded separately as a policy).
FROM docker.io/library/python:3.12-slim

RUN pip install --no-cache-dir fastapi==0.115.5 uvicorn[standard]==0.34.2 websockets==15.0.1 boto3==1.40.40

ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
WORKDIR /app
COPY ourstory /app/ourstory

CMD ["python", "-m", "ourstory.game.server"]
