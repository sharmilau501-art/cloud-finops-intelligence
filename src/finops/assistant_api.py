"""Local-only self-service browser for grounded FinOps metrics."""
from __future__ import annotations

import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from .assistant import answer_question

app = FastAPI(title="FinOps Metrics Assistant", version="0.1.0")


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask")
def ask(payload: Question) -> dict:
    try:
        return answer_question(
            payload.question,
            project=os.getenv("FINOPS_BQ_PROJECT", "finops-cloud-intelligence-2026"),
            dataset=os.getenv("FINOPS_BQ_DATASET", "finops_demo"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # No secrets, raw SQL, or credential details should be exposed to clients.
        raise HTTPException(status_code=503, detail="Warehouse or language-model request failed; check server logs.") from exc


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FinOps Assistant</title><style>
body{font:16px system-ui,sans-serif;background:#f6f7fb;color:#192334;max-width:730px;margin:5vh auto;padding:0 20px}
main{background:white;padding:28px;border-radius:16px;box-shadow:0 8px 34px #15223b15}
input{box-sizing:border-box;width:100%;padding:13px;font:inherit;border:1px solid #9ba7b7;border-radius:9px}
button{background:#194ca9;color:white;border:0;padding:12px 20px;border-radius:9px;margin-top:12px;cursor:pointer}
button:disabled{opacity:.5}.hint{font-size:.88em;color:#586579}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f3f8;padding:15px;border-radius:9px}
</style></head><body><main><h1>FinOps Analytics Assistant</h1>
<p class="hint">Read-only BigQuery metrics from synthetic data. No free-form SQL generation.</p>
<label for="question">Ask a question</label>
<input id="question" value="Which application has the highest cost?" maxlength="500">
<button id="ask">Get verified answer</button>
<p id="status" class="hint" role="status"></p><div id="answer" aria-live="polite"></div>
<p class="hint">Examples: What was total cloud spending? | Which application costs most? | What is the cost per 1,000 requests?</p>
</main><script>
const button=document.querySelector('#ask');
button.addEventListener('click',async()=>{
button.disabled=true;document.querySelector('#status').textContent='Querying read-only metrics...';
const output=document.querySelector('#answer');output.replaceChildren();
try{const response=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:document.querySelector('#question').value})});
const data=await response.json();if(!response.ok)throw Error(data.detail||'Request failed');
const p=document.createElement('p');p.textContent=data.explanation;output.append(p);
const heading=document.createElement('h3');heading.textContent='Verified metrics';output.append(heading);
const pre=document.createElement('pre');pre.textContent=JSON.stringify(data.validated_metrics,null,2);output.append(pre);
document.querySelector('#status').textContent='Source: '+data.source+' | Mode: '+data.mode+(data.narration_warning?' | '+data.narration_warning:'');
}catch(e){document.querySelector('#status').textContent='Error: '+e.message;}finally{button.disabled=false;}
});</script></body></html>"""
