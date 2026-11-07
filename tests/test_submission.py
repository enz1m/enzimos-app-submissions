"""One public-admission workflow: valid listing, maintainer update, hostile changes."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import unittest
from PIL import Image

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('validator',HERE/'tools/validate.py')
validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)


def stage(root):
    subprocess.run(['git','-C',str(root),'add','--all'],check=True,stdout=subprocess.DEVNULL)


def repo(root):
    root.mkdir();subprocess.run(['git','-C',str(root),'init','-q'],check=True)
    (root/'reviewers.json').write_text('{"reviewers":["enz1m"]}')
    (root/'apps').mkdir();(root/'apps/.gitkeep').touch();stage(root)


class Admission(unittest.TestCase):
    def test_submission_and_update_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            scratch=Path(temporary);base=scratch/'base';proposal=scratch/'proposal';repo(base)
            shutil.copytree(base,proposal,ignore=shutil.ignore_patterns('.git'))
            subprocess.run(['git','-C',str(proposal),'init','-q'],check=True)
            app=proposal/'apps/org.example.MyApp';(app/'screenshots').mkdir(parents=True)
            entry=json.loads((HERE/'docs/submission.example.json').read_text());entry['maintainers']=['developer-one']
            (app/'submission.json').write_text(json.dumps(entry))
            manifest={'app-id':entry['id'],'runtime':'org.freedesktop.Platform','runtime-version':'25.08','sdk':'org.freedesktop.Sdk','command':'example','finish-args':['--socket=wayland'],'modules':[{'name':'example','buildsystem':'simple','build-commands':['true'],'sources':[{'type':'git','url':entry['source']['url'],'commit':entry['source']['commit']}]}]}
            (app/'manifest.json').write_text(json.dumps(manifest))
            (app/'metainfo.xml').write_text('<component type="desktop-application"><id>org.example.MyApp</id><name>My App</name><summary>An example</summary><metadata_license>CC0-1.0</metadata_license><project_license>MIT</project_license><screenshots><screenshot type="default"><image>https://example.org/01.png</image></screenshot></screenshots></component>')
            Image.new('RGB',(512,512)).save(app/'icon.png');Image.new('RGB',(1280,720)).save(app/'screenshots/01.png');stage(proposal)
            self.assertIn(entry['id'],validator.check(proposal,base,'developer-one'))
            export=scratch/'operator-catalog.json'
            subprocess.run([sys.executable,str(HERE/'tools/export_catalog.py'),'--root',str(proposal),'--output',str(export)],check=True,stdout=subprocess.DEVNULL)
            self.assertEqual(json.loads(export.read_text())['apps'][0]['listing_root'],str(app))
            leaked=proposal/'operator-catalog.json'
            refused=subprocess.run([sys.executable,str(HERE/'tools/export_catalog.py'),'--root',str(proposal),'--output',str(leaked)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.assertNotEqual(refused.returncode,0);self.assertFalse(leaked.exists())

            # Admission must not grant update rights to a different account.
            approved=scratch/'approved';shutil.copytree(proposal,approved)
            entry['version']='1.0.1';entry['release_notes']='A reviewed update.'
            (app/'submission.json').write_text(json.dumps(entry));stage(proposal)
            validator.check(proposal,approved,'developer-one')
            entry['maintainers'].append('attacker');(app/'submission.json').write_text(json.dumps(entry));stage(proposal)
            with self.assertRaisesRegex(ValueError,'approved maintainer'):validator.check(proposal,approved,'attacker')
            entry['maintainers'].remove('attacker');(app/'submission.json').write_text(json.dumps(entry));stage(proposal)
            # Ordinary authors cannot alter policy helpers in an app update.
            (proposal/'reviewers.json').write_text('{"reviewers":["attacker"]}');stage(proposal)
            with self.assertRaisesRegex(ValueError,'only their app'):validator.check(proposal,approved,'developer-one')
            shutil.copyfile(approved/'reviewers.json',proposal/'reviewers.json')
            # Assets must be real bounded images; paths cannot escape the app.
            (app/'screenshots/01.png').unlink();(app/'screenshots/01.png').symlink_to(app/'icon.png');stage(proposal)
            with self.assertRaisesRegex(ValueError,'nonregular/escaping'):validator.check(proposal,approved,'developer-one')
            (app/'screenshots/01.png').unlink();(app/'screenshots/01.png').write_bytes(b'not an image');stage(proposal)
            with self.assertRaises(OSError):validator.check(proposal,approved,'developer-one')
            Image.new('RGB',(1280,720)).save(app/'screenshots/01.png')
            manifest['modules'][0]['sources'][0].pop('commit');manifest['modules'][0]['sources'][0]['branch']='main'
            (app/'manifest.json').write_text(json.dumps(manifest));stage(proposal)
            with self.assertRaisesRegex(ValueError,'moving source'):validator.check(proposal,approved,'developer-one')


if __name__=='__main__':unittest.main()
