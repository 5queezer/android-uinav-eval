"""Ready-made generative GUI agents (screenshot in, action text out) for eval.py: `--models gen:<name>`.

One adapter per model family builds the model's own prompt (goal, its own short action history, the screenshot;
nothing from the layout), calls the model and parses the reply into a normalised action in device pixels:
  {"type": "tap" | "long_press", "x", "y"}
  {"type": "swipe", "x1", "y1", "x2", "y2", "direction"}  direction of the finger: "up" scrolls the content down
  {"type": "back" | "home"}, {"type": "key", "key": "KEYCODE_..."}, {"type": "type", "text"}, {"type": "wait", "secs"}
  {"type": "answer", "text"}  an answer that does not end the task (Qwen3-VL answers, then terminates)
  {"type": "finish", "answer"}  the model says the task is done (answer: None if it gave none)
  {"type": "abort"}  the model gave up (GELab ABORT, terminate with status failure)
  {"type": "noop", "reason"}  a malformed reply or an action the harness does not offer (open an app, ask the user)
"""
import json, os, re, shlex, time, urllib.error, urllib.request
from datetime import datetime

PREFIX = "gen:"
W, H = 1080, 2400  # the emulator screen, as in eval.parse_layout
OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
LLAMA = "http://localhost:8010/v1"  # llama-server, one model at a time


# ---------------------------------------------------------------- transport
def post(url, body, headers=None, timeout=300):
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}") from None


def image_part(b64):
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}


def with_tool_calls(text, calls):
    """The reply text with tool calls a server lifted out of it put back as <tool_call> blocks."""
    for c in calls or []:
        f = c["function"]
        text += "\n<tool_call>\n" + json.dumps({"name": f["name"], "arguments": f["arguments"]}) + "\n</tool_call>"
    return text


def ollama_messages(messages):
    """OpenAI-style messages as Ollama's /v1/chat/completions turns them into /api/chat ones (openai.go,
    FromChatRequest): each text or image part of a list content becomes a message of its own, in order."""
    out = []
    for m in messages:
        if isinstance(m["content"], str):
            out.append({"role": m["role"], "content": m["content"]})
            continue
        for p in m["content"]:
            if p["type"] == "text":
                out.append({"role": m["role"], "content": p["text"]})
            else:
                out.append({"role": m["role"], "content": "", "images": [p["image_url"]["url"].split(",", 1)[1]]})
    return out


class Ollama:
    """A model on Ollama's /api/chat."""
    options = {"num_ctx": 8192}

    @property
    def ollama(self):  # the name to unload
        return self.served

    def call(self, messages):
        body = {"model": self.served, "messages": ollama_messages(messages), "stream": False, "keep_alive": "30m",
                "options": self.options}
        if getattr(self, "tools", None):  # without declared tools Ollama's parser drops the <tool_call> block entirely
            body["tools"] = self.tools
        m = post(OLLAMA + "/api/chat", body)["message"]
        # Ollama's qwen3-vl parser lifts <tool_call> blocks out of the content
        return with_tool_calls(m.get("content") or "", m.get("tool_calls"))

    def warm(self):  # the same options, or Ollama reloads the model on the first step
        post(OLLAMA + "/api/chat", {"model": self.served, "messages": [{"role": "user", "content": "Hi"}],
                                    "stream": False, "keep_alive": "30m", "options": self.options | {"num_predict": 1}})


class OpenAI:
    """A model on an OpenAI-compatible /v1/chat/completions (llama-server, vLLM)."""
    sampling = {}
    ollama = None  # nothing to unload in Ollama

    def call(self, messages):
        key = os.environ.get(self.env + "_API_KEY", "EMPTY")
        r = post(self.base + "/chat/completions", {"model": self.served, "messages": messages} | self.sampling,
                 {"Authorization": f"Bearer {key}"})
        m = r["choices"][0]["message"]
        think = m.get("reasoning_content")  # llama-server may split a <think> block off
        return (f"<think>{think}</think>\n" if think else "") + with_tool_calls(m.get("content") or "",
                                                                                 m.get("tool_calls"))

    def warm(self):
        key = os.environ.get(self.env + "_API_KEY", "EMPTY")
        post(self.base + "/chat/completions", {"model": self.served, "max_tokens": 1,
                                               "messages": [{"role": "user", "content": "Hi"}]},
             {"Authorization": f"Bearer {key}"})


# ---------------------------------------------------------------- coordinates
def px(v, scale, size):
    """A coordinate on the model's 0..scale grid in device pixels."""
    return min(size - 1, max(0, round(float(v) * size / scale)))


def point(xy, scale):
    if isinstance(xy, str):  # "x,y" or "x y"
        xy = re.split(r"[,\s]+", xy.strip(" ()[]"))
    if len(xy) < 2:
        raise ValueError(f"not a point: {xy!r}")
    return px(xy[0], scale, W), px(xy[1], scale, H)


def swipe(p1, p2):
    (x1, y1), (x2, y2) = p1, p2
    dx, dy = x2 - x1, y2 - y1
    d = ("left" if dx < 0 else "right") if abs(dx) > abs(dy) else ("up" if dy < 0 else "down")
    return {"type": "swipe", "x1": x1, "y1": y1, "x2": x2, "y2": y2, "direction": d}


# ---------------------------------------------------------------- GELab-Zero
GELAB_TASK = """你是一个手机 GUI-Agent 操作专家，你需要根据用户下发的任务、手机屏幕截图和交互操作的历史记录，借助既定的动作空间与手机进行交互，从而完成用户的任务。
请牢记，手机屏幕坐标系以左上角为原点，x轴向右，y轴向下，取值范围均为 0-1000。

# 行动原则：

1. 你需要明确记录自己上一次的action，如果是滑动，不能超过5次。
2. 你需要严格遵循用户的指令，如果你和用户进行过对话，需要更遵守最后一轮的指令

# Action Space:

在 Android 手机的场景下，你的动作空间包含以下9类操作，所有输出都必须遵守对应的参数要求：
1. CLICK：点击手机屏幕坐标，需包含点击的坐标位置 point。
例如：action:CLICK\tpoint:x,y
2. TYPE：在手机输入框中输入文字，需包含输入内容 value、输入框的位置 point。
例如：action:TYPE\tvalue:输入内容\tpoint:x,y
3. COMPLETE：任务完成后向用户报告结果，需包含报告的内容 value。
例如：action:COMPLETE\treturn:完成任务后向用户报告的内容
4. WAIT：等待指定时长，需包含等待时间 value（秒）。
例如：action:WAIT\tvalue:等待时间
5. AWAKE：唤醒指定应用，需包含唤醒的应用名称 value。
例如：action:AWAKE\tvalue:应用名称
6. INFO：询问用户问题或详细信息，需包含提问内容 value。
例如：action:INFO\tvalue:提问内容
7. ABORT：终止当前任务，仅在当前任务无法继续执行时使用，需包含 value 说明原因。
例如：action:ABORT\tvalue:终止任务的原因
8. SLIDE：在手机屏幕上滑动，滑动的方向不限，需包含起点 point1 和终点 point2。
例如：action:SLIDE\tpoint1:x1,y1\tpoint2:x2,y2
9. LONGPRESS：长按手机屏幕坐标，需包含长按的坐标位置 point。
例如：action:LONGPRESS\tpoint:x,y
"""
GELAB_FORMAT = """

在执行操作之前，请务必回顾你的历史操作记录和限定的动作空间，先进行思考和解释然后输出动作空间和对应的参数：
1. 思考（THINK）：在 <THINK> 和 </THINK> 标签之间。
2. 解释（explain）：在动作格式中，使用 explain: 开头，简要说明当前动作的目的和执行方式。
在执行完操作后，请输出执行完当前步骤后的新历史总结。
输出格式示例：
<THINK> 思考的内容 </THINK>
explain:解释的内容\taction:动作空间和对应的参数\tsummary:执行完当前步骤后的新历史总结
"""


class GELab(OpenAI):
    """GELab-Zero-4B-preview (StepFun), https://github.com/stepfun-ai/gelab-zero: the prompt and parser of
    copilot_tools/parser_0920_summary.py (task_type parser_0922_summary in examples/run_single_task.py), the sampling of
    that example, 0-1000 coordinates (copilot_front_end/pu_frontend_executor.py). The history is the model's own
    summary of everything so far, from its last reply. Served by llama-server (Ollama cannot import it)."""
    env = "GELAB"
    served = os.environ.get("GELAB_MODEL", "gelab-zero-4b-preview")
    base = os.environ.get("GELAB_BASE_URL", LLAMA).rstrip("/")
    sampling = {"temperature": 0.1, "top_p": 0.95, "frequency_penalty": 0.0, "max_tokens": 4096}

    def messages(self, goal, notes, image):
        history = notes[-1] if notes and notes[-1].strip() else "暂无历史操作"
        status = f"\n已知用户指令为：{goal}指令结束\n\n\n已知已经执行过的历史动作如下：{history}\n当前手机屏幕截图如下：\n"
        return [{"role": "user", "content": [{"type": "text", "text": GELAB_TASK}, {"type": "text", "text": status},
                                             image_part(image), {"type": "text", "text": GELAB_FORMAT}]}]

    def parse(self, text):
        """(action, summary) from '<THINK> .. </THINK>\\nexplain:..\\taction:CLICK\\tpoint:x,y\\tsummary:..'."""
        s = re.sub(r"<\s*/?\s*(?:THINK|TINK)\s*>", lambda m: "</THINK>" if "/" in m.group() else "<THINK>", text.strip(),
                   flags=re.I)
        kv = s.split("</THINK>", 1)[1] if "</THINK>" in s else s
        f = dict(p.split(":", 1) for p in (p.strip() for p in kv.split("\t")) if ":" in p)
        f = {k.strip(): v.strip() for k, v in f.items()}
        act = f.get("action", "").upper()
        if act == "CLICK":
            x, y = point(f["point"], 1000)
            a = {"type": "tap", "x": x, "y": y}
        elif act == "LONGPRESS":
            x, y = point(f["point"], 1000)
            a = {"type": "long_press", "x": x, "y": y}
        elif act == "SLIDE":
            a = swipe(point(f["point1"], 1000), point(f["point2"], 1000))
        elif act == "TYPE":
            a = {"type": "type", "text": f["value"]}
        elif act == "WAIT":
            a = {"type": "wait", "secs": float(f.get("value") or 1)}
        elif act == "COMPLETE":
            a = {"type": "finish", "answer": f.get("return") or None}
        elif act == "ABORT":
            a = {"type": "abort"}
        elif act in ("AWAKE", "INFO"):  # opening an app by name / asking the user: not offered to any model here
            a = {"type": "noop", "reason": f"unsupported action {act}"}
        else:
            raise ValueError(f"no known action in {act!r}")
        return a, f.get("summary")


# ---------------------------------------------------------------- mobile_use tool call (Qwen3-VL, GUI-Owl)
def tool_call(text):
    """The arguments of the first <tool_call> block (a missing closing tag is tolerated)."""
    i = text.index("<tool_call>") + len("<tool_call>")
    args = json.JSONDecoder().raw_decode(text[i:].lstrip())[0]["arguments"]
    return json.loads(args) if isinstance(args, str) else args


def action_note(text):
    """The 'Action: ...' sentence before the tool call, which the official loops keep as the history entry."""
    m = re.search(r"Action:\s*(.*?)\s*(?:<tool_call>|$)", text, re.S)
    return m.group(1).replace("\n", "").replace('"', "") if m and m.group(1) else None


def mobile_use(args, scale, answer_ends):
    act = args["action"]
    if act in ("click", "long_press"):
        x, y = point(args["coordinate"], scale)
        return {"type": "tap" if act == "click" else "long_press", "x": x, "y": y}
    if act in ("swipe", "scroll"):
        return swipe(point(args["coordinate"], scale), point(args["coordinate2"], scale))
    if act == "type":
        return {"type": "type", "text": str(args["text"])}
    if act in ("system_button", "key"):  # Back, Home, Menu, Enter / an adb keyevent name
        b = str(args["button" if act == "system_button" else "text"]).lower()
        return {"type": b} if b in ("back", "home") else {"type": "key", "key": "KEYCODE_" + b.upper()}
    if act == "wait":
        return {"type": "wait", "secs": float(args.get("time") or 2)}
    if act == "answer":
        text = str(args.get("text") or "")
        return {"type": "finish", "answer": text or None} if answer_ends else {"type": "answer", "text": text}
    if act == "terminate":
        return {"type": "finish", "answer": None} if args.get("status", "success") == "success" else {"type": "abort"}
    return {"type": "noop", "reason": f"unsupported action {act!r}"}  # open (an app by name), interact, call_user


QWEN_TOOL = {"type": "function", "function": {
    "name": "mobile_use",
    "description": "Use a touchscreen to interact with a mobile device, and take screenshots.\n* This is an interface to "
                   "a mobile device with touchscreen. You can perform actions like clicking, typing, swiping, etc.\n* "
                   "Some applications may take time to start or process actions, so you may need to wait and take "
                   "successive screenshots to see the results of your actions.\n* The screen's resolution is "
                   "999x999.\n* Make sure to click any buttons, links, icons, etc with the cursor tip in the center of "
                   "the element. Don't click boxes on their edges unless asked.",
    "parameters": {"properties": {
        "action": {"description": "The action to perform. The available actions are:\n* `click`: Click the point on "
                                  "the screen with coordinate (x, y).\n* `long_press`: Press the point on the screen "
                                  "with coordinate (x, y) for specified seconds.\n* `swipe`: Swipe from the starting "
                                  "point with coordinate (x, y) to the end point with coordinates2 (x2, y2).\n* "
                                  "`type`: Input the specified text into the activated input box.\n* `answer`: Output "
                                  "the answer.\n* `system_button`: Press the system button.\n* `wait`: Wait specified "
                                  "seconds for the change to happen.\n* `terminate`: Terminate the current task and "
                                  "report its completion status.",
                   "enum": ["click", "long_press", "swipe", "type", "answer", "system_button", "wait", "terminate"],
                   "type": "string"},
        "coordinate": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) "
                                      "coordinates to move the mouse to. Required only by `action=click`, "
                                      "`action=long_press`, and `action=swipe`.", "type": "array"},
        "coordinate2": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) "
                                       "coordinates to move the mouse to. Required only by `action=swipe`.",
                        "type": "array"},
        "text": {"description": "Required only by `action=type` and `action=answer`.", "type": "string"},
        "time": {"description": "The seconds to wait. Required only by `action=long_press` and `action=wait`.",
                 "type": "number"},
        "button": {"description": "Back means returning to the previous interface, Home means returning to the "
                                  "desktop, Menu means opening the application background menu, and Enter means "
                                  "pressing the enter. Required only by `action=system_button`",
                   "enum": ["Back", "Home", "Menu", "Enter"], "type": "string"},
        "status": {"description": "The status of the task. Required only by `action=terminate`.", "type": "string",
                   "enum": ["success", "failure"]}},
        "required": ["action"], "type": "object"}}}
QWEN_SYSTEM = f"""

# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{json.dumps(QWEN_TOOL)}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{{"name": <function-name>, "arguments": <args-json-object>}}
</tool_call>

# Response format

Response format for every step:
1) Thought: one concise sentence explaining the next move (no multi-step reasoning).
2) Action: a short imperative describing what to do in the UI.
3) A single <tool_call>...</tool_call> block containing only the JSON: {{"name": <function-name>, "arguments": <args-json-object>}}.

Rules:
- Output exactly in the order: Thought, Action, <tool_call>.
- Be brief: one sentence for Thought, one for Action.
- Do not output anything else outside those three parts.
- If finishing, use action=terminate in the tool call."""


class Qwen3VL(Ollama):
    """Qwen3-VL-4B-Instruct on Ollama: the mobile_use function call of the Qwen3-VL cookbook
    https://github.com/QwenLM/Qwen3-VL/blob/main/cookbooks/mobile_agent.ipynb (system prompt, user query with
    'Step i: ...; ' history, coordinates on a 0-999 grid, rescaled by x / 999 * width as in its rescale_coordinates).
    Its `answer` does not end the task; `terminate` does. Ollama's qwen3-vl:4b is the thinking variant."""
    served = os.environ.get("QWEN3VL_MODEL", "qwen3-vl:4b-instruct")
    options = Ollama.options | {"temperature": 0}  # the cookbook sets none; 0 keeps runs comparable and repeatable

    @property
    def tools(self):  # the mobile_use function of QWEN_SYSTEM, declared so Ollama returns the call in tool_calls
        return [{"type": "function", "function": json.loads(re.search(r"<tools>\s*(\{.*?\})\s*</tools>",
                                                                          QWEN_SYSTEM, re.S).group(1))["function"]}]

    def messages(self, goal, notes, image):
        done = "".join(f"Step {i}: {n}; " for i, n in enumerate(notes, 1))
        query = (f"The user query: {goal}.\nTask progress (You have done the following operation on the current "
                 f"device): {done}.\n")
        return [{"role": "system", "content": [{"type": "text", "text": QWEN_SYSTEM}]},
                {"role": "user", "content": [{"type": "text", "text": query}, image_part(image)]}]

    def parse(self, text):
        return mobile_use(tool_call(text), 999, answer_ends=False), action_note(text)


GUI_OWL_SYSTEM = '''# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{"type": "function", "function": {"name_for_human": "mobile_use", "name": "mobile_use", "description": "Use a touchscreen to interact with a mobile device, and take screenshots.
* This is an interface to a mobile device with touchscreen. You can perform actions like clicking, typing, swiping, etc.
* Some applications may take time to start or process actions, so you may need to wait and take successive screenshots to see the results of your actions.
* The screen's resolution is 1000x1000.
* Make sure to click any buttons, links, icons, etc with the cursor tip in the center of the element. Don't click boxes on their edges unless asked.", "parameters": {"properties": {"action": {"description": "The action to perform. The available actions are:
* `key`: Perform a key event on the mobile device.
    - This supports adb's `keyevent` syntax.
    - Examples: \\"volume_up\\", \\"volume_down\\", \\"power\\", \\"camera\\", \\"clear\\".
* `click`: Click the point on the screen with coordinate (x, y).
* `long_press`: Press the point on the screen with coordinate (x, y) for specified seconds.
* `swipe`: Swipe from the starting point with coordinate (x, y) to the end point with coordinates2 (x2, y2).
* `type`: Input the specified text into the activated input box.
* `system_button`: Press the system button.
* `open`: Open an app on the device.
* `wait`: Wait specified seconds for the change to happen.
* `answer`: Terminate the current task and output the answer.
* `interact`: Resolve the blocking window by interacting with the user.
* `terminate`: Terminate the current task and report its completion status.", "enum": ["key", "click", "long_press", "swipe", "type", "system_button", "open", "wait", "answer", "interact", "terminate"], "type": "string"}, "coordinate": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) coordinates to move the mouse to. Required only by `action=click`, `action=long_press`, and `action=swipe`.", "type": "array"}, "coordinate2": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) coordinates to move the mouse to. Required only by `action=swipe`.", "type": "array"}, "text": {"description": "Required only by `action=key`, `action=type`, `action=open`, `action=answer`,and `action=interact`.", "type": "string"}, "time": {"description": "The seconds to wait. Required only by `action=long_press` and `action=wait`.", "type": "number"}, "button": {"description": "Back means returning to the previous interface, Home means returning to the desktop, Menu means opening the application background menu, and Enter means pressing the enter. Required only by `action=system_button`", "enum": ["Back", "Home", "Menu", "Enter"], "type": "string"}, "status": {"description": "The status of the task. Required only by `action=terminate`.", "type": "string", "enum": ["success", "failure"]}}, "required": ["action"], "type": "object"}, "args_format": "Format the arguments as a JSON object."}}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{"name": <function-name>, "arguments": <args-json-object>}
</tool_call>

# Response format

Response format for every step:
1) Action: a short imperative describing what to do in the UI.
2) A single <tool_call>...</tool_call> block containing only the JSON: {"name": <function-name>, "arguments": <args-json-object>}.

Rules:
- Output exactly in the order: Action, <tool_call>.
- Be brief: one sentence for Action.
- Do not output anything else outside those two parts.
- If finishing, use action=terminate in the tool call.'''
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class GUIOwl(OpenAI):  # keeps the episode's turns; one episode at a time
    """GUI-Owl-1.5-4B-Instruct (mPLUG), https://github.com/X-PLUG/MobileAgent/tree/main/Mobile-Agent-v3.5:
    SYSTEM_PROMPT and build_messages of mobile_use/utils.py with its default history_n=4 (the last four steps as
    screenshot + reply turns, earlier steps as their 'Action:' sentence), coordinates on a 0-1000 grid (rescale_coordinates in
    mobile_use/run_gui_owl_1_5_for_mobile.py); its `answer` ends the task. The official wrapper stores temperature 0.0
    but never sends it; we send it, so llama-server's default 0.8 does not apply."""
    env = "GUI_OWL"
    sampling = {"temperature": 0.0}
    served = os.environ.get("GUI_OWL_MODEL", "GUI-Owl-1.5-4B-Instruct")
    base = os.environ.get("GUI_OWL_BASE_URL", LLAMA).rstrip("/")

    history_n = 4  # the official default: the last 4 steps as screenshot + reply turns, earlier ones as text

    def messages(self, goal, notes, image):
        if not notes:  # a new episode
            self.turns = []
        start = max(0, len(self.turns) - self.history_n)
        prev = "\n".join(f"Step {i}: {n}" for i, n in enumerate(notes[:start], 1)) or "None"
        d = datetime.today()
        prompt = (f"Please generate the next move according to the UI screenshot, instruction and previous actions."
                  f"\n\nInstruction: Today's date is: {d:%Y-%m-%d} {WEEKDAYS[d.weekday()]}.{goal}\n\n"
                  f"Previous actions:\n{prev}")
        msgs = [{"role": "system", "content": [{"type": "text", "text": GUI_OWL_SYSTEM}]}]
        for i, (img, reply) in enumerate(self.turns[start:]):
            msgs.append({"role": "user", "content": ([{"type": "text", "text": prompt}] if i == 0 else [])
                         + [image_part(img)]})
            msgs.append({"role": "assistant", "content": [{"type": "text", "text": reply}]})
        msgs.append({"role": "user", "content": ([] if self.turns[start:] else [{"type": "text", "text": prompt}])
                     + [image_part(image)]})
        self.pending = image
        return msgs

    def parse(self, text):
        self.turns.append((self.pending, text))
        return mobile_use(tool_call(text), 1000, answer_ends=True), action_note(text)


ADAPTERS = {"gelab-zero-4b": GELab(), "qwen3-vl-4b": Qwen3VL(), "gui-owl-1.5-4b": GUIOwl()}


# ---------------------------------------------------------------- used by eval.episode
def is_gen(model):
    return model.startswith(PREFIX)


def adapter(model):
    name = model[len(PREFIX):]
    if name not in ADAPTERS:
        raise SystemExit(f"unknown generative agent {model!r}; known: "
                         + ", ".join(PREFIX + k for k in ADAPTERS))
    return ADAPTERS[name]


def label(a):
    t = a["type"]
    if t in ("tap", "long_press"):
        return f"{t}({a['x']},{a['y']})"
    if t == "swipe":
        return f"swipe {a['direction']} ({a['x1']},{a['y1']})->({a['x2']},{a['y2']})"
    if t == "key":
        return f"key {a['key']}"
    if t in ("type", "answer"):
        return f"{t} {a['text']!r}"
    if t == "wait":
        return f"wait {a['secs']:g}s"
    if t == "finish":
        return "finish" + (f" {a['answer']!r}" if a["answer"] else "")
    if t == "noop":
        return f"noop ({a['reason']})"
    return t


def decide(agent, goal, notes, image):
    """One model call: (raw reply, normalised action, history note). An unparseable reply is a noop."""
    msgs = agent.messages(goal, notes, image)
    try:
        reply = agent.call(msgs)
    except Exception as e:  # one retry, then the episode is an error (as for System One)
        print(f"  model request failed, retrying once: {e}", flush=True)
        time.sleep(2)
        reply = agent.call(msgs)
    try:
        action, note = agent.parse(reply)
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as e:
        action, note = {"type": "noop", "reason": f"malformed reply: {type(e).__name__}: {e}"[:200]}, None
    return reply, action, note or label(action)


def hit(a, cands):
    """The smallest candidate whose bounds hold the tap point, or None."""
    if a["type"] not in ("tap", "long_press"):
        return None
    inside = [c for c in cands if c["x"] <= a["x"] < c["x"] + c["w"] and c["y"] <= a["y"] < c["y"] + c["h"]]
    return min(inside, key=lambda c: c["w"] * c["h"], default=None)


def commands(a):
    """The adb argument lists that carry out the action (none for wait, answer, finish, abort, noop)."""
    t = a["type"]
    if t == "tap":
        return [("shell", "input", "tap", str(a["x"]), str(a["y"]))]
    if t == "long_press":
        return [("shell", "input", "swipe", *map(str, (a["x"], a["y"], a["x"], a["y"])), "800")]
    if t == "swipe":
        return [("shell", "input", "swipe", *map(str, (a["x1"], a["y1"], a["x2"], a["y2"])), "400")]
    if t in ("back", "home"):
        return [("shell", "input", "keyevent", f"KEYCODE_{t.upper()}")]
    if t == "key":
        return [("shell", "input", "keyevent", a["key"])]
    if t == "type":  # adb shell joins its arguments into one remote command line
        return [("shell", "input", "text", shlex.quote(a["text"].replace(" ", "%s")))]
    return []
