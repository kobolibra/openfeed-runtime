"""Validate untrusted browser worker IPC payloads and queue entries."""
import json
import pytest
from openfeed.sandbox_worker import read_job_safely


def make_job(tmp_path, payload):
    p=tmp_path/'job.json'
    p.write_text(json.dumps(payload))
    return p


def test_reject_non_object_job(tmp_path):
    with pytest.raises(ValueError,match='JSON object'):
        read_job_safely(make_job(tmp_path, ['not','a','job']))


def test_reject_extra_field_job(tmp_path):
    with pytest.raises(ValueError,match='Unexpected'):
        read_job_safely(make_job(tmp_path,{'id':'a','url':'https://example.org','wait_selector':'', 'submitted_at':1,'debug':'extra'}))


def test_reject_wrong_type_job(tmp_path):
    with pytest.raises(ValueError,match='field types'):
        read_job_safely(make_job(tmp_path,{'id':'a','url':['https://example.org'], 'wait_selector':'','submitted_at':1}))


@pytest.mark.parametrize('submitted', ['NaN', float('nan'), float('inf'), True, None])
def test_reject_invalid_timestamps(tmp_path,submitted):
    with pytest.raises(ValueError,match='timestamp'):
        read_job_safely(make_job(tmp_path, {'id':'a','url':'https://example.org',
            'wait_selector':'', 'submitted_at':submitted}))
