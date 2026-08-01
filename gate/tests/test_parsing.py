from gate.parsing import extract_inbound_message

MESSAGE_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "1",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "pn1"},
                        "contacts": [{"wa_id": "5511999999999"}],
                        "messages": [
                            {"from": "5511999999999", "id": "wamid.1", "type": "text",
                             "text": {"body": "hi"}}
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}

STATUS_CALLBACK_PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "1",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"phone_number_id": "pn1"},
                        "statuses": [{"id": "wamid.1", "status": "delivered"}],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}


def test_extracts_inbound_message():
    msg = extract_inbound_message(MESSAGE_PAYLOAD)
    assert msg is not None
    assert msg.wa_id == "5511999999999"
    assert msg.message_id == "wamid.1"
    assert msg.phone_number_id == "pn1"
    assert msg.message_type == "text"


def test_status_callback_returns_none():
    assert extract_inbound_message(STATUS_CALLBACK_PAYLOAD) is None


def test_empty_payload_returns_none():
    assert extract_inbound_message({}) is None


def test_malformed_payload_returns_none_not_raise():
    assert extract_inbound_message({"entry": "not-a-list"}) is None
    assert extract_inbound_message({"entry": [{"changes": "nope"}]}) is None


def test_falls_back_to_message_from_field_when_no_contacts():
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"phone_number_id": "pn1"},
                    "messages": [{"from": "5511888888888", "id": "wamid.2", "type": "text"}],
                }
            }]
        }]
    }
    msg = extract_inbound_message(payload)
    assert msg is not None
    assert msg.wa_id == "5511888888888"
