from __future__ import annotations

import json
import os

import boto3

from tokuye.utils.config import settings

BEDROCK_MODEL_ID = settings.bedrock_embedding_model_id
EMBED_DIM = int(os.environ.get("BEDROCK_EMBED_DIM", "512"))
NORMALIZE = os.environ.get("BEDROCK_EMBED_NORMALIZE", "true").lower() != "false"

_client = boto3.client("bedrock-runtime")


def get_embedding(text: str) -> list[float]:
    payload = {"inputText": text, "dimensions": EMBED_DIM}
    if NORMALIZE:
        payload["normalize"] = True
    resp = _client.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload),
    )
    body = resp["body"].read()
    data = json.loads(body)
    return data.get("embedding", [])
