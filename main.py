# ============================================================
# Nebulix Labs Future AI Agent

# An open-source AI agent powered by free AI APIs.

# Planner  : Cohere North Mini Code you can change this
# Executor : NVIDIA Nemotron 3 Super 120B you can change this
# Search   : Tavily you can use cheap options or DuckDuck Go its free


# Powered by accessible/free AI services via OpenRouter.
# Feel free to fork, modify, and build upon this project.
# Please give courtesy/credit to Nebulix Labs of Future AI.
# ============================================================

from openai import OpenAI
from flask import Flask, jsonify, request, send_file, redirect
import json
import os
from dotenv import load_dotenv 
import requests
import uuid 
import webbrowser 
from flask_cors import CORS
from tavily import TavilyClient
from datetime import datetime
import subprocess
import threading
import concurrent.futures
import re
from bs4 import BeautifulSoup

load_dotenv('Aiapi.env')
app = Flask(__name__) 
CORS(app) 
with open('system.json','r',encoding='utf-8') as file:
    system = json.load(file)

plan_sys = system['Planner']['System'] 
exe_sys = system['Executor']['System']

client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv('OPENROUTER'), 
)

nvidia_client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv('AIAPI')
)

pending_actions = {}
session_chat_history = [] 
action_history = []

session_attachments = {}

def youtube_transcript(url: str):
    pattern = r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})"
    match = re.search(pattern, url)
    if not match:
        raise ValueError("Invalid YouTube URL")
    video_id = match.group(1)
    api_url = "https://api.freetranscriptapi.com/v1/transcript"
    response = requests.get(
        api_url,
        params={"video_url": video_id, "format": "text"},
        timeout=30
    )
    response.raise_for_status()
    return response.text

def web_search(query: str) -> str: 
        client = TavilyClient(os.getenv('SEARCHAPI'))
        response = client.search(
        query= query,
        include_answer= "basic", 
        search_depth="basic" 
        )
        return response['answer']

def get_page_content(url: str, max_words: int = 200) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()
    paragraphs = soup.find_all("p")
    text = " ".join(p.get_text(" ", strip=True) for p in paragraphs)
    words = text.split()
    return " ".join(words[:max_words])

def read_file(path: str) -> str:
       if os.path.isfile(path):
              with open(path,'r',encoding='utf-8') as file:
                     return file.read()
       return "File not exist"

def write_file(path: str, content: str = "") -> str:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Success: File '{path}' successfully written."
    except Exception as e:
        return f"Error: {str(e)}"

def create_file(path: str) -> str:
     if os.path.isfile(path):
          return "File already exist try another name or path"
     with open(path,'x') as a: 
          a.write("") 
     return f"Done file created at path {path}"

def local_RAG(path: str) -> str: 
     if os.path.isfile(path):
          with open(path,'r',encoding='utf-8') as file:
               return file.read()

def load_skill(path: str) -> str:
     if os.path.isfile(path) and path.endswith(('.txt','.md')):
          with open(path,'r',encoding='utf-8') as file:
               return file.read()
     return "Skill or file not found"

def memory(about: str, data: str) -> str: 
     date = datetime.now().strftime('%d-%m-%Y')
     data_format = {
          "About": about,
          "Data": data,
          "Date_created": date,
          "Lable": 'new'
     }
     listy = []
     if os.path.isfile('memory.json'):
         try:
             with open('memory.json', 'r', encoding='utf-8') as f:
                 content = f.read().strip()
                 if content:
                     listy = json.loads(content)
         except json.JSONDecodeError:
             pass
     listy.append(data_format)
     with open('memory.json', 'w', encoding='utf-8') as f:
          json.dump(listy, f, indent=4)
     return "Done new memory saved"

def cmd(command: str) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, shell=True, timeout=120)
        output = result.stdout.strip()
        error = result.stderr.strip()
        if result.returncode == 0:
            return f"Success. Output:\n{output if output else 'No output generated.'}"
        return f"Failed. Error:\n{error}"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 120 seconds."
    except Exception as e:
        return f"Error: {str(e)}"

def check_perms() -> str: 
     with open('perms.txt','r',encoding='utf-8') as perms:
          return perms.read()

def get_user_location():
    ip = requests.get('https://ipwho.is/')
    return ip.json()

def date_time(): 
    return datetime.now().strftime("%d-%m-%Y" "%H:%M:%S")

def tool_policy(): 
    with open('tool_policy.txt','r',encoding='utf-8') as policy:
        return policy.read()

def get_action_history() -> str:
    if not action_history:
        return "No actions have been executed yet in this session."
    return json.dumps(action_history[-20:], indent=2)

def vlm(media_url: str, prompt: str = "What is in this media?") -> str:
    system_instruction = "Describe everything in the provided media in extreme detail. Include all details about what it is, how it looks, colors, actions, background, types of objects, and context. Provide as much exhaustive visual detail as possible."
    
    actual_url = session_attachments.get(media_url, media_url)

    try:
        res = client.chat.completions.create(
            model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            messages=[
                {"role": "system", "content": system_instruction},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": actual_url}}
                    ]
                }
            ],
            extra_body={"reasoning": {"enabled": True}}
        )
        return res.choices[0].message.content
    except Exception as e1:
        print(f"OpenRouter VLM failed: {e1}. Trying NVIDIA fallback...")
        try:
            invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {os.getenv('AIAPI')}",
                "Accept": "application/json",
            }
            payload = {
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": actual_url}}
                        ]
                    }
                ],
                "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
                "max_tokens": 1024,
                "stream": False,
                "temperature": 0.6,
                "top_p": 0.95
            }
            fallback_res = requests.post(invoke_url, headers=headers, json=payload)
            if fallback_res.status_code == 200:
                return fallback_res.json()["choices"][0]["message"]["content"]
            return f"Error: {fallback_res.text}"
        except Exception as e2:
            return f"Both APIs Failed. Error: {str(e2)}"


date_now = datetime.now().strftime('%d-%m-%Y') 
try:
    with open('memory.json', 'r', encoding='utf-8') as f:
        content = f.read().strip()
        if content:
            check = json.loads(content)
            for item in check:
                if item.get("Date_created") != date_now: 
                    item["Lable"] = "old"
            with open('memory.json', 'w', encoding='utf-8') as f_write:
                 json.dump(check, f_write, indent=4)
        else:
            check = [] 
except (FileNotFoundError, json.JSONDecodeError):
    check = []
    with open('memory.json', 'w', encoding='utf-8') as f:
        json.dump(check, f)

with open('tools.json','r',encoding='utf-8') as tooL:
    tools = json.load(tooL)

vlm_schema_exists = any(t.get("function", {}).get("name") == "vlm" for t in tools)
if not vlm_schema_exists:
    tools.append({
        "type": "function",
        "function": {
            "name": "vlm",
            "description": "Analyze an image, video, or audio file to understand what is inside it. Use this tool whenever the user provides media.",
            "parameters": {
                "type": "object",
                "properties": {
                    "media_url": {
                        "type": "string",
                        "description": "The URL or internal ID of the media/image provided by the user (e.g. 'media_a1b2c3')."
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Specific instruction on what to look for in the media."
                    }
                },
                "required": ["media_url"]
            }
        }
    })

available_tools = {
    "web_search": web_search,
    "read_file": read_file,
    "write_file": write_file,
    "create_file": create_file,
    "local_RAG": local_RAG,
    "load_skill": load_skill,
    "memory": memory,
    "cmd": cmd,
    "check_perms": check_perms,
    "get_action_history": get_action_history,
    "date_time": date_time,
    "tool_policy": tool_policy,
    "youtube_transcript": youtube_transcript,
    "get_page_content": get_page_content,
    "vlm": vlm,
    "get_user_location": get_user_location
}

def execute_single_tool(tc): 
    func_name = tc["function"]["name"]
    try:
        args = json.loads(tc["function"]["arguments"])
    except json.JSONDecodeError:
        args = {}
    
    func = available_tools.get(func_name)
    
    if func:
        try:
            if func_name in ["check_perms", "get_action_history"]:
                res = func()
            else:
                res = func(**args)
        except Exception as e:
            res = f"Error executing {func_name}: {str(e)}"
    else:
        res = f"Tool {func_name} not found."
        
    action_history.append({
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "tool": func_name,
        "arguments": args,
        "status": "Success" if not str(res).startswith("Error") else "Failed"
    })
    
    return {
        "role": "tool",
        "tool_call_id": tc["id"],
        "name": func_name,
        "content": str(res)
    }

def get_long_term_memory():
    if os.path.isfile('memory.json'):
        try:
            with open('memory.json', 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            pass
    return "No long-term memory stored."

def executor(user_input: str):
    ltm_context = get_long_term_memory() 
    chat_context_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in session_chat_history[-8:]])
    
    available_tools_schema = json.dumps(tools, indent=2)
    
    planner_prompt = (
            f"{plan_sys}\n\n"
            f"--- AVAILABLE TOOLS ---\n"
            f"You can instruct the executor to use the following tools. Here is their JSON schema:\n"
            f"{available_tools_schema}\n\n"
            f"--- LONG TERM MEMORY ---\n{ltm_context}\n\n" 
            f"--- RECENT CHAT HISTORY ---\n{chat_context_str}\n\n"
            f"CURRENT USER REQUEST: {user_input}\n\n"
            f"INSTRUCTIONS FOR YOUR RESPONSE FORMAT:\n"
            f"Step 1: On the very first line, output a JSON object with a chat title (10-20 words). Example: {{\"chat_title\": \"Title here\"}}\n"
            f"Step 2: IMMEDIATELY after the JSON, write your detailed plan for the Executor. YOU MUST PROVIDE A PLAN. Do not stop generating after the JSON.\n\n"
            f"Example Format:\n"
            f"{{\"chat_title\": \"Generated Title Here\"}}\n"
            f"PLAN:\n"
            f"1. Action 1...\n"
            f"2. Action 2...\n"
        )

    planner_messages = [
        {"role": "user", "content": planner_prompt}
    ]
    
    executor_sys_prompt = f"{exe_sys}\n\nRemember to check your Action History using the tool if you need to know what you already did. You also have access to the user's Long Term Memory:\n{ltm_context}"
    
    executor_messages = [
        {"role": "system", "content": executor_sys_prompt}
    ]
    
    for _ in range(5):
        yield "\n\n### 🧠 [Planner Phase]\n"
        plan_text = ""
        
        try:
            planner_response = client.chat.completions.create(
                model="cohere/north-mini-code:free",
                messages=planner_messages,
                stream=True,
                extra_body={"reasoning": {"enabled": False}}
            )
            for chunk in planner_response:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                    plan_text += text
                    yield text
        except Exception:
            planner_response = nvidia_client.chat.completions.create(
                model="nvidia/nemotron-3.5-lightning-30b-a3b", 
                messages=planner_messages,
                temperature=1,
                top_p=0.95,
                max_tokens=16384,
                extra_body={"chat_template_kwargs":{"enable_thinking":False}},
                stream=True
            )
            for chunk in planner_response:
                if not chunk.choices:
                    continue
                reasoning = getattr(chunk.choices[0].delta, "reasoning_content", None)
                if reasoning:
                    plan_text += reasoning
                    yield reasoning
                if chunk.choices[0].delta.content is not None:
                    text = chunk.choices[0].delta.content
                    plan_text += text
                    yield text
        
        planner_messages.append({"role": "assistant", "content": plan_text})

        clean_plan = re.sub(r'\{.*?\}', '', plan_text, flags=re.DOTALL).strip()
        if len(clean_plan) < 15:
            plan_text += "\nPLAN: Directly analyze the user's request and take necessary actions using the available tools to complete the task."
            yield "\n[System] Auto-generated plan added to assist Executor.\n"

        yield "\n\n### ⚙️ [Executor Phase]\n"
        executor_prompt = f"Planner's Directive:\n{plan_text}\n\nExecute the required tools or provide the requested output based on this directive."
        executor_messages.append({"role": "user", "content": executor_prompt})
        
        try:
            executor_response = client.chat.completions.create(
                model="minimax/minimax-m3:free",
                messages=executor_messages,
                tools=tools,
                tool_choice="auto",
                extra_body={"reasoning": {"enabled": True}}
            )
            msg = executor_response.choices[0].message
            executor_text = msg.content or ""
        except Exception:
            executor_response = nvidia_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=executor_messages,
                temperature=1,
                top_p=1,
                max_tokens=4096,
                tools=tools,
                tool_choice="auto",
                stream=False
            )
            msg = executor_response.choices[0].message
            executor_text = ""
            reasoning = getattr(msg, "reasoning_content", None)
            if reasoning:
                executor_text += reasoning + "\n"
            if msg.content:
                executor_text += msg.content
        
        if executor_text:
            for i in range(0, len(executor_text), 15):
                yield executor_text[i:i+15]
                
        assistant_message = {
            "role": "assistant",
            "content": msg.content or None
        }
        
        if hasattr(msg, 'reasoning_details') and msg.reasoning_details:
            assistant_message["reasoning_details"] = msg.reasoning_details
        if getattr(msg, "reasoning_content", None):
            assistant_message["reasoning_content"] = msg.reasoning_content
            
        if not msg.tool_calls:
            executor_messages.append(assistant_message)
            break
            
        reconstructed_tool_calls = []
        for tc in msg.tool_calls:
            reconstructed_tool_calls.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments
                }
            })
            
        assistant_message["tool_calls"] = reconstructed_tool_calls
        executor_messages.append(assistant_message)
        
        yield "\n\n"
        tool_results = []
        
        for tc in reconstructed_tool_calls:
            func_name = tc["function"]["name"]
            
            if func_name in ["cmd", "write_file", "create_file"]:
                req_id = str(uuid.uuid4())
                ev = threading.Event()
                pending_actions[req_id] = {'event': ev, 'approved': False}
                
                yield f"\n[ACTION_REQUIRED] Tool: {func_name} | Args: {tc['function']['arguments']} | ID: {req_id}\n"
                
                ev.wait()
                
                if pending_actions[req_id]['approved']:
                    res = execute_single_tool(tc)
                else:
                    res = {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": func_name,
                        "content": "Action declined by user."
                    }
                    action_history.append({
                        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "tool": func_name,
                        "arguments": tc["function"]["arguments"],
                        "status": "Declined by user frontend"
                    })
                del pending_actions[req_id]
            else:
                res = execute_single_tool(tc)
            tool_results.append(res)
            yield f"```\n{res['name']} Output:\n{res['content']}\n```\n"
        
        executor_messages.extend(tool_results)
        gathered_data = "\n".join([f"Tool: {r['name']} -> Result: {r['content']}" for r in tool_results])
        planner_messages.append({
            "role": "user",
            "content": f"The Executor used tools and gathered this data:\n{gathered_data}\nIs this data sufficient? If yes, provide instructions for the final response. If no, determine what tools should be used next."
        })

@app.route('/')
def index():
    return redirect('/home')

@app.route('/home') 
def home():
    if os.path.exists('index.html'):
        return send_file('index.html')
    else:
        return "<h1>File Not Found</h1><p>Please create an <b>index.html</b> file in the same directory as this script.</p>"

@app.route('/api/approve', methods=['POST']) 
def approve_action():
    data = request.json
    req_id = data.get('id')
    action = data.get('action') 
    if req_id in pending_actions:
        pending_actions[req_id]['approved'] = (action == 'allow')
        pending_actions[req_id]['event'].set()
        return jsonify({"status": "success"})
    return jsonify({"status": "not found"})

@app.route('/api/chat', methods=['POST']) 
def api_chat():
    user_data = request.json
    user_message = user_data.get('message', '')
    attachments = user_data.get('attachments', [])
    
    att_info_texts = []
    for att in attachments:
        att_id = f"media_{uuid.uuid4().hex[:8]}"
        session_attachments[att_id] = att['data']
        att_info_texts.append(f"- File Type: {att.get('type', 'Unknown')}, Internal Media ID: {att_id}")
    
    if att_info_texts:
        att_block = "\n".join(att_info_texts)
        user_message += f"\n\n[SYSTEM NOTE: The user has uploaded attachments. Here are their details:\n{att_block}\nINSTRUCTION: You MUST instruct the executor to use the 'vlm' tool with the provided 'Internal Media ID' as the 'media_url' to analyze the visual/audio contents of the media.]"

    session_chat_history.append({"role": "user", "content": user_message})
    
    def generate():
        full_response = ""
        try:
            for chunk in executor(user_message):
                full_response += chunk
                yield chunk
            session_chat_history.append({"role": "assistant", "content": full_response})
        except Exception as e:
            error_msg = f"\nInternal Error: {str(e)}"
            session_chat_history.append({"role": "assistant", "content": full_response + error_msg})
            yield error_msg
            
    return app.response_class(generate(), mimetype='text/plain')

if __name__ == "__main__":
    def open_browser():
        webbrowser.open_new("http://127.0.0.1:8080/home")
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        threading.Timer(1.5, open_browser).start()
    app.run(host="127.0.0.1", port=8080)