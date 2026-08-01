import httpx
import pytest
from fastapi import FastAPI, Request

from gate.meta_client import send_text_message


@pytest.mark.asyncio
async def test_send_text_message_posts_correct_payload_and_auth():
    received = {}
    mock_app = FastAPI()

    @mock_app.post("/{phone_number_id}/messages")
    async def send(phone_number_id: str, request: Request):
        received["phone_number_id"] = phone_number_id
        received["body"] = await request.json()
        received["auth"] = request.headers.get("authorization")
        return {"messages": [{"id": "wamid.sent1"}]}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=mock_app), base_url="http://meta.internal"
    ) as client:
        response = await send_text_message(
            client, "pn123", "test-token", "5511999999999", "hello there",
            base_url="http://meta.internal",
        )

    assert response.status_code == 200
    assert received["phone_number_id"] == "pn123"
    assert received["auth"] == "Bearer test-token"
    assert received["body"]["to"] == "5511999999999"
    assert received["body"]["text"]["body"] == "hello there"
    assert received["body"]["messaging_product"] == "whatsapp"
