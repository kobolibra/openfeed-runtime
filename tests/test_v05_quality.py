import pytest
from openfeed.quality import validate_items


def test_malformed_items_filtered_and_reported():
    records=[{'title':'Good title','url':'https://site.example/a','summary':'a'},
             {'title':'Other','url':'http://127.0.0.1/internal'},
             {'title':'Good title','url':'https://site.example/a'},
             {'title':' ','url':'https://site.example/b'}]
    valid,report=validate_items(records)
    assert len(valid)==1
    assert report['rejected']=={'invalid_link':1,'duplicate':1,'invalid_title':1}
    assert report['date_missing']==1


def test_all_records_invalid_fail_closed():
    with pytest.raises(ValueError,match='last good feed preserved'):
        validate_items([{'title':'bad','url':'file:///etc/passwd'}])


def test_valid_history_retains_unknown_dates():
    valid,report=validate_items([{'title':'Bond Research','url':'https://site.example/research','published_at':None}])
    assert valid[0]['published_at'] is None
    assert report['date_missing']==1


def test_large_unbounded_batch_rejected():
    with pytest.raises(ValueError,match='budget'):
        validate_items([{'title':'A','url':'https://site.example/a'}]*301)


def test_malformed_summary_rejected():
    valid,report=validate_items([{'title':'T','url':'https://site.example/a','summary':42},
                                 {'title':'T2','url':'https://site.example/b','summary':'ok'}])
    assert len(valid)==1 and report['rejected']['invalid_summary']==1
