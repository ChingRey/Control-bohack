import base64
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import backend as b
from agents import project_files, opencode_executor as e
import test_checkpoints as fixture


class GenericFileTests(unittest.TestCase):
    def setUp(self):
        self.h=fixture.CheckpointIntegrationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        task=b.load(self.h.task['id']);task.update(checkpoint_delivery='manual',plan=[],plan_draft=[]);b.save(task)

    def test_explicit_authorization_is_writable_without_formal_plan(self):
        def execute(files,packet,planning=False,chatting=False):
            self.assertFalse(planning);self.assertFalse(chatting)
            self.assertTrue(packet['project_requirements'])
            return {'text':'已创建工程文件','files':{**files,'.settings/runtime.custom':'setting=true','BUILD':'target'},'events':[]}
        with patch.object(e,'execute',side_effect=execute):
            self.assertEqual(self.h.call(self.h.path+'/coding/messages',{'message':'你自己选择最合适的方案执行'})[0],202)
            task=self.h.wait()
        self.assertEqual(task['coding_run']['status'],'completed')
        self.assertEqual(b.read_project_files(task['id'])['.settings/runtime.custom'],'setting=true')

    def test_binary_round_trip_and_external_binary_change_rejects_checkpoint_resume(self):
        original=base64.b64encode(b'\x00\xfforiginal').decode()
        updated=base64.b64encode(b'\x00\xfeupdated').decode()
        root=b.project(self.h.task['id'])
        b.write_project_bytes(root/'assets/data.anything',project_files.decode(original))
        def execute(files,packet,planning,chatting,assets):
            self.assertEqual(assets['assets/data.anything'],original)
            return {'text':'已更新二进制资源','files':{**files,'src/main.unknown':'ready'},'binary_files':{'assets/data.anything':updated},'events':[]}
        with patch.object(e,'execute',side_effect=execute):
            self.assertEqual(self.h.call(self.h.path+'/coding/messages',{'message':'创建代码文件并修改二进制资源'})[0],202)
            task=self.h.wait()
        self.assertEqual(task['coding_run']['status'],'completed')
        self.assertEqual((root/'assets/data.anything').read_bytes(),project_files.decode(updated))
        snap=self.h.call(self.h.path)[1]
        self.assertIn('assets/data.anything',snap['binary_files'])
        self.assertNotIn('assets/data.anything',snap['files'])
        checkpoint=task['coding_checkpoints'][-1]
        self.assertTrue(checkpoint['project_evidence']['binary_changes'])
        b.write_project_bytes(root/'assets/data.anything',b'\x00\xffexternal')
        body={'session_id':task['id'],'request_id':'resume','confirmed':True,'teaching_completed':True,
              'expected_code_hash':checkpoint['project_evidence']['code_hash']}
        self.assertEqual(self.h.call(self.h.path+'/checkpoints/'+checkpoint['checkpoint_id']+'/resume',body)[0],400)

    def test_executor_preserves_unknown_binary_and_unknown_text_extensions(self):
        binary=base64.b64encode(b'\x00\xffbinary').decode()
        def execute(command,**options):
            root=Path(options['cwd'])
            self.assertEqual((root/'image.rawasset').read_bytes(),project_files.decode(binary))
            (root/'new.arbitrary').write_bytes(b'new text\r\n')
            (root/'other.bin').write_bytes(b'\x00\xffnew')
            return subprocess.CompletedProcess(command,0,json.dumps({'type':'text','part':{'text':'done'}}),'')
        with patch.object(e.subprocess,'run',side_effect=execute):
            result=e.execute({'old.whatever':'a\r\nb\r\n'}, {},binary_files={'image.rawasset':binary})
        self.assertEqual(result['files']['old.whatever'],'a\r\nb\r\n')
        self.assertEqual(result['files']['new.arbitrary'],'new text\r\n')
        self.assertEqual(result['binary_files']['image.rawasset'],binary)
        self.assertEqual(project_files.decode(result['binary_files']['other.bin']),b'\x00\xffnew')

    def test_permissions_are_not_filename_whitelists_and_timeout_is_900(self):
        for name in ('main.js','db.sqlite','assets/icon.png','BUILD','.env','.config/custom.whatever','node_modules/demo/file.any'):
            self.assertTrue(project_files.allowed(name),name)
        for name in ('../secret','C:/secret','C:secret','/root/file','a/../../secret'):
            self.assertFalse(project_files.allowed(name),name)
        with patch.dict('os.environ',{},clear=True):
            self.assertEqual(e.execution_timeout(False),900)


if __name__=='__main__':unittest.main()
