import pytest
from relay_logic import *
KEY='test-only-key'
def test_owner_root_and_expiry():
 assert authorize('owner','owner',KEY,{},'123',1000)['generation']==0
 assert authorize('owner','owner',KEY,{},'123',EXPIRY) is None
@pytest.mark.parametrize('field,value',[('root','999'),('generation','2'),('not_before','1500'),('signature','bad')])
def test_tampered_child_rejected(field,value):
 data={'root':'123','generation':'1','not_before':'1000','signature':signature(KEY,'123',1,1000)};data[field]=value
 with pytest.raises(ValueError):authorize('github-actions[bot]','owner',KEY,data,'124',1001)
def test_valid_child_and_untrusted_actor():
 data={'root':'123','generation':'1','not_before':'1000','signature':signature(KEY,'123',1,1000)}
 assert authorize('github-actions[bot]','owner',KEY,data,'124',1001)['root']=='123'
 with pytest.raises(ValueError):authorize('stranger','owner',KEY,data,'124',1001)
def test_no_duplicate_or_parallel_root():
 c=claim(None,'123',0,'123',1000);assert c
 assert claim(c,'456',0,'456',1100) is None
 assert claim(c,'123',1,'124',1600)
 assert claim(c,'123',0,'125',1100) is None
 c=claim(c,'123',1,'124',1600)
 assert claim(c,'123',1,'126',1700) is None
 assert claim(c,'456',2,'127',1700) is None
 assert claim(c,'456',0,'456',3000)

def test_signed_child_with_preserved_owner_actor():
 data={'root':'123','generation':'1','not_before':'1000','signature':signature(KEY,'123',1,1000)}
 assert authorize('owner','owner',KEY,data,'124',1001)['generation']==1
