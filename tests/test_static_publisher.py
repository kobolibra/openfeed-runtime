import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ops'))
from publish_static import equivalent,sync_files

def rss(title='A',stamp='today',guid='g1'):
 return f'<rss><channel><title>{title}</title><lastBuildDate>{stamp}</lastBuildDate><item><guid>{guid}</guid></item></channel></rss>'.encode()

def test_timestamp_only_is_noop():
 assert equivalent(rss(stamp='a'),rss(stamp='b'))
 assert not equivalent(rss(),rss(title='B'))
 assert not equivalent(rss(),rss(guid='g2'))

def test_paused_feed_keeps_existing_url(tmp_path):
 stage=tmp_path/'stage';repo=tmp_path/'repo';stage.mkdir();(repo/'rss').mkdir(parents=True)
 f=repo/'rss'/('a'*26+'.xml');f.write_bytes(rss());(stage/'subscriptions.opml').write_text('<opml/>')
 assert sync_files(stage,repo)==['subscriptions.opml']
 assert f.read_bytes()==rss()

def test_changed_content_and_noop(tmp_path):
 stage=tmp_path/'stage';repo=tmp_path/'repo';(stage/'rss').mkdir(parents=True);repo.mkdir()
 f='rss/'+('b'*26)+'.xml';(stage/f).write_bytes(rss())
 assert sync_files(stage,repo)==[f]
 (stage/f).write_bytes(rss(stamp='new'));assert sync_files(stage,repo)==[]
 (stage/f).write_bytes(rss(title='changed'));assert sync_files(stage,repo)==[f]

def test_no_private_files(tmp_path):
 stage=tmp_path/'stage';repo=tmp_path/'repo';stage.mkdir();repo.mkdir();(stage/'database.sqlite').write_text('private')
 with pytest.raises(ValueError):sync_files(stage,repo)
 assert not (repo/'database.sqlite').exists()

def test_no_symlink_escape(tmp_path):
 stage=tmp_path/'stage';repo=tmp_path/'repo';outside=tmp_path/'outside';(stage/'rss').mkdir(parents=True);repo.mkdir();outside.mkdir();(repo/'rss').symlink_to(outside,target_is_directory=True)
 (stage/'rss'/('c'*26+'.xml')).write_bytes(rss())
 with pytest.raises(ValueError):sync_files(stage,repo)
 assert not list(outside.iterdir())

def test_initial_deployment_can_verify_actual_refresh_timestamp(tmp_path):
 stage=tmp_path/'stage';repo=tmp_path/'repo';(stage/'rss').mkdir(parents=True);repo.mkdir()
 f='rss/'+('d'*26)+'.xml';(stage/f).write_bytes(rss(stamp='old'));sync_files(stage,repo)
 (stage/f).write_bytes(rss(stamp='new'))
 assert sync_files(stage,repo,include_refresh_times=True)==[f]
 assert (repo/f).read_bytes()==rss(stamp='new')
