from __future__ import annotations

def test_make_hidden_tk_root_reuses_process_root():
    from tests.tk_support import make_hidden_tk_root

    first = make_hidden_tk_root()
    second = make_hidden_tk_root()

    assert second is first
    assert first.winfo_exists()
