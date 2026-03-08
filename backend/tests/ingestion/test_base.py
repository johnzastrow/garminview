from garminview.ingestion.base import BaseAdapter


def test_base_adapter_is_abstract():
    import pytest
    with pytest.raises(TypeError):
        BaseAdapter()  # cannot instantiate abstract class
