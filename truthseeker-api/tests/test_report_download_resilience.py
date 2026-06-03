from app.services import report_generator


def test_execute_supabase_query_retries_transient_read_errors():
    calls = {"count": 0}

    def flaky_query():
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("ReadError")
        return "ok"

    assert report_generator._execute_supabase_query(flaky_query) == "ok"
    assert calls["count"] == 2
