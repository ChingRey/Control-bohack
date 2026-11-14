import json
import sqlite3
import unittest
from agents import project_titles
import backend as b
import test_checkpoints as fixture


class RepositoryNameTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.addCleanup(self.c.close)
  self.c.execute('CREATE TABLE tasks (id TEXT PRIMARY KEY,body TEXT)')
 def create(self,value=''):
  task={'id':str(self.c.execute('SELECT count(*) FROM tasks').fetchone()[0]),'mode':'opencode','messages':[]}
  project_titles.initialize(self.c,task,value)
  self.c.execute('INSERT INTO tasks VALUES (?,?)',(task['id'],json.dumps(task)))
  return task
 def test_blank_names_are_sequential_and_skip_existing_custom_names(self):
  self.create('未命名仓库一')
  second=self.create();third=self.create('   ')
  self.assertEqual(second['title'],'未命名仓库二');self.assertEqual(third['title'],'未命名仓库三')
  project_titles.rename(third,'计分仓库');self.c.execute('UPDATE tasks SET body=? WHERE id=?',(json.dumps(third),third['id']))
  self.assertEqual(self.create()['title'],'未命名仓库四')
 def test_named_and_blank_titles_are_pinned_across_chat(self):
  for task in (self.create(' 我的游戏 '),self.create()):
   title=task['title'];task['messages']=[{'channel':'coding','role':'user','content':'我想做一个恐龙游戏'}]
   self.assertFalse(project_titles.update(task));self.assertEqual(task['title'],title)
 def test_invalid_name_has_no_counter_side_effect(self):
  for value in (None,12,'bad\nname','x'*61):
   with self.assertRaises(ValueError):self.create(value)
  self.assertEqual(self.create()['title'],'未命名仓库一')
 def test_chinese_ordinals(self):
  self.assertEqual([project_titles.chinese_number(x) for x in (1,10,11,20,101,1001)],['一','十','十一','二十','一百零一','一千零一'])


class RepositoryHTTPTests(unittest.TestCase):
 def setUp(self):
  self.h=fixture.CheckpointIntegrationTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
 def test_creation_accepts_title_and_rename_updates_library_sources_without_rewriting_audit(self):
  status,task=self.h.call('/api/tasks',{'coding_mode':'opencode','title':'链表仓库'})
  self.assertEqual(status,200);self.assertEqual(task['title'],'链表仓库')
  before=self.h.call('/api/experience-library')[1]
  self.assertEqual(before['project_names'][task['id']],'链表仓库')
  self.assertEqual(self.h.call('/api/tasks/'+task['id']+'/project/rename',{'title':'链表第二课'})[0],200)
  after=self.h.call('/api/experience-library')[1]
  self.assertEqual(after['project_names'][task['id']],'链表第二课')
  self.assertEqual(after['batches'],before['batches']);self.assertEqual(after['revision'],before['revision'])
  loaded=b.load(task['id']);loaded['messages'].append({'channel':'coding','role':'user','content':'我想做一个其他游戏'});b.save(loaded)
  self.assertEqual(b.load(task['id'])['title'],'链表第二课')
