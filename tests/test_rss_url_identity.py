from openfeed.extract import canonical_link,guid_for


def test_liepin_tracking_changes_do_not_create_duplicate_rss_items():
    base='https://www.liepin.com/company-jobs/8652522/'
    a=canonical_link('https://www.liepin.com/lptjob/83203669?d_ckId=first&d_headId=one&d_posi=6',base)
    b=canonical_link('https://www.liepin.com/lptjob/83203669?d_ckId=second&d_headId=two&d_posi=8',base)
    assert a==b=='https://www.liepin.com/lptjob/83203669'
    assert guid_for(a)==guid_for(b)


def test_normalization_preserves_content_parameters_and_other_sites():
    base='https://www.liepin.com/'
    assert canonical_link('/lptjob/123?language=en&d_posi=3',base)=='https://www.liepin.com/lptjob/123?language=en'
    other='https://example.org/research?d_posi=3&report=12'
    assert canonical_link(other,base)==other
