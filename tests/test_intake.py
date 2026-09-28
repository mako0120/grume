import base64

from grume.intake import parse_email_job


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def test_parse_email_job():
    message = {
        "id": "m1",
        "threadId": "t1",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "[グルメCanva] 焼肉しょうちゃん天満"},
                {"name": "From", "value": "User <user@example.com>"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {
                        "data": b64(
                            "店舗名：焼肉しょうちゃん天満\n"
                            "コース：粋コース\n"
                            "料理：\n"
                            "・キムチ盛り合わせ\n"
                            "・厚切りタンブリアン\n"
                            "メモ：\n"
                            "・タン推し"
                        )
                    },
                }
            ],
        },
    }

    job = parse_email_job(message, ["a.jpg"])
    assert job.store_name == "焼肉しょうちゃん天満"
    assert job.course_name == "粋コース"
    assert job.dishes == ["キムチ盛り合わせ", "厚切りタンブリアン"]
    assert job.notes == ["タン推し"]
    assert job.sender == "user@example.com"


def test_subject_fallback():
    message = {
        "id": "m2",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "[グルメCanva] うどん和匠"},
                {"name": "From", "value": "user@example.com"},
            ],
            "body": {"data": ""},
        },
    }
    job = parse_email_job(message, [])
    assert job.store_name == "うどん和匠"
