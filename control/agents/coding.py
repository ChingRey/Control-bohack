"""Fixed todo example adapter. This is not a model-powered coding agent."""
PLAN = ['明确待办事项的添加规则', '实现添加与完成操作', '检查空白输入和刷新后的数据']
FILES = {
 'index.html': '<!doctype html>\n<html lang="zh-CN">\n<head><meta charset="utf-8"><title>我的待办</title>\n<link rel="stylesheet" href="style.css"></head>\n<body>\n<main><h1>我的待办</h1>\n<form id="form"><input id="title" placeholder="添加一件待办"><button>添加</button></form>\n<ul id="list"></ul></main>\n<script src="app.js"></script>\n</body></html>',
 'style.css': 'body { font-family: sans-serif; background: #f4f7f5; color: #24382f; }\nmain { max-width: 540px; margin: 60px auto; padding: 32px; background: white; border-radius: 16px; }\ninput, button { padding: 12px; }\nli { padding: 12px; cursor: pointer; }\n.done { text-decoration: line-through; color: #888; }',
 'app.js': '// 示例项目起点：先确定需求，再逐步实现。\nconst form = document.querySelector("#form");\nconst input = document.querySelector("#title");\nconst list = document.querySelector("#list");\n'
}


class SampleCodingAgent:
 def __init__(self,project,write_project_file):
  self.project=project;self.write_project_file=write_project_file
 def step(self, t, instruction, learning_context=None):
  n=t['step']; path=self.project(t['id'])/'app.js'; before=path.read_text(encoding='utf-8')
  if n == 0:
   after=before+'\n// 需求检查点：本示例将空白输入列为待审查边界。\n'
  elif n == 1:
   after=before+'\n// 教学预置：暂不处理空白输入与数据持久化，供学生审查。\nform.addEventListener("submit", (event) => {\n  event.preventDefault();\n  const li = document.createElement("li");\n  li.textContent = input.value;\n  li.onclick = () => li.classList.toggle("done");\n  list.append(li);\n  input.value = "";\n});\n'
  else:
   after=FILES['app.js']+'\nlet tasks = JSON.parse(localStorage.getItem("control-todos") || "[]");\nfunction render() {\n  list.replaceChildren();\n  tasks.forEach((task, i) => {\n    const li = document.createElement("li");\n    li.textContent = task.title;\n    li.classList.toggle("done", task.done);\n    li.onclick = () => { tasks[i].done = !tasks[i].done; persist(); };\n    list.append(li);\n  });\n}\nfunction persist() {\n  localStorage.setItem("control-todos", JSON.stringify(tasks));\n  render();\n}\nform.addEventListener("submit", (event) => {\n  event.preventDefault();\n  const title = input.value.trim();\n  if (!title) return;\n  tasks.push({ title, done: false });\n  input.value = "";\n  persist();\n});\nrender();\n'
  self.write_project_file(path,after)
  t['changes'].append(dict(file='app.js', before=before, after=after, instruction=instruction))
  return '示例执行已写入 app.js。当前步骤结束，已暂停。请查看代码或打开项目预览；这不是模型生成结果。'

