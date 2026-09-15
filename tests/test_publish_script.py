"""Exercise the publisher with real local Git and a simulated GitHub CLI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]

class Publisher(unittest.TestCase):
    def test_publish_and_reject_existing_tag(self):
        if not shutil.which('rsync') or not shutil.which('git'):
            self.skipTest('git and rsync are required')
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); home=base/'home'; home.mkdir()
            bin_dir=base/'bin'; bin_dir.mkdir()
            remote=base/'remote.git'
            real_git=shutil.which('git')
            env=dict(os.environ, HOME=str(home), GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.invalid', GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.invalid', GIT_CONFIG_NOSYSTEM='1')
            def git(*args):
                return subprocess.run([real_git,*args],env=env,check=True,capture_output=True,text=True).stdout
            git('init','--bare','--initial-branch=main',str(remote))
            seed=base/'seed';git('clone',str(remote),str(seed))
            (seed/'README.md').write_text('# Existing repo\n')
            (seed/'keep.txt').write_text('Unrelated file must survive.\n')
            git('-C',str(seed),'add','.');git('-C',str(seed),'commit','-m','Initial');git('-C',str(seed),'push','origin','main')
            wrapper='''#!/usr/bin/env python3
import os,sys
args=sys.argv[1:]
if args[:3]==['remote','get-url','origin']:
 print('https://github.com/SebastianKristo/ki-varslinger.git');sys.exit(0)
if 'clone' in args:
 args=[os.environ['TEST_REMOTE'] if x=='https://github.com/SebastianKristo/ki-varslinger.git' else x for x in args]
os.execv(os.environ['REAL_GIT'],[os.environ['REAL_GIT']]+args)
'''
            (bin_dir/'git').write_text(wrapper);(bin_dir/'git').chmod(0o755)
            (bin_dir/'gh').write_text('''#!/usr/bin/env python3
import json,os,sys
with open(os.environ['GH_CALLS'],'a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[1:3]==['repo','view']:print('false')
''');(bin_dir/'gh').chmod(0o755)
            calls=base/'calls.jsonl'
            env.update(PATH=str(bin_dir)+os.pathsep+env['PATH'],TEST_REMOTE=str(remote),REAL_GIT=real_git,GH_CALLS=str(calls))
            downloads=home/'Downloads';downloads.mkdir()
            archive=downloads/'ki-varslinger-2.1.0.zip'
            with zipfile.ZipFile(archive,'w') as z:
                for p in ROOT.rglob('*'):
                    if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts:
                        z.write(p,Path('ki-varslinger')/p.relative_to(ROOT))
            script=ROOT/'scripts/publish-macos.sh'
            run=subprocess.run(['bash',str(script),'2.1.0'],env=env,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertEqual(git('--git-dir',str(remote),'show','main:keep.txt').strip(),'Unrelated file must survive.')
            self.assertEqual(git('--git-dir',str(remote),'rev-parse','main').strip(),git('--git-dir',str(remote),'rev-parse','v2.1.0^{}').strip())
            github_calls=[json.loads(line) for line in calls.read_text().splitlines()]
            self.assertEqual(sum(c[:2]==['release','create'] for c in github_calls),1)
            second=subprocess.run(['bash',str(script),'2.1.0'],env=env,capture_output=True,text=True)
            self.assertNotEqual(second.returncode,0)
            self.assertIn('finnes allerede',second.stderr)
            github_calls=[json.loads(line) for line in calls.read_text().splitlines()]
            self.assertEqual(sum(c[:2]==['release','create'] for c in github_calls),1)
            local=home/'Documents/HomeAssistant/ki-varslinger'
            (local/'keep.txt').write_text('Local modification')
            third=subprocess.run(['bash',str(script),'2.1.0'],env=env,capture_output=True,text=True)
            self.assertNotEqual(third.returncode,0)
            self.assertIn('lokale endringer',third.stderr)

if __name__ == '__main__':unittest.main()
