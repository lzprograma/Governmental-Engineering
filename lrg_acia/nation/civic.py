"""Serviços persistentes de governo, deliberação, memória nacional e aprendizagem.

Estas capacidades são um protótipo administrativo local. Não representam uma
instituição pública real nem implementam autenticação/eleições juridicamente válidas.
"""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from contextlib import contextmanager
from typing import Any, Iterator


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class CivicStore:
    def __init__(self, db_path: str | Path):
        self.path = str(db_path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    @contextmanager
    def db(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init(self):
        with self.db() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS departments(
              id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
              mission TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS proposals(
              id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
              department_id TEXT REFERENCES departments(id) ON DELETE SET NULL,
              category TEXT NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL,
              decision TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS deliberations(
              id TEXT PRIMARY KEY, topic TEXT NOT NULL, prompt TEXT NOT NULL,
              status TEXT NOT NULL, created_by TEXT NOT NULL, participants_json TEXT NOT NULL,
              created_at TEXT NOT NULL, completed_at TEXT);
            CREATE TABLE IF NOT EXISTS deliberation_turns(
              id TEXT PRIMARY KEY, deliberation_id TEXT NOT NULL REFERENCES deliberations(id) ON DELETE CASCADE,
              citizen_id TEXT NOT NULL, citizen_name TEXT NOT NULL, round_no INTEGER NOT NULL,
              turn_index INTEGER NOT NULL, content TEXT NOT NULL, model_id TEXT NOT NULL,
              created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_delib_turns ON deliberation_turns(deliberation_id,round_no,turn_index);
            CREATE TABLE IF NOT EXISTS shared_memories(
              id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL,
              memory_type TEXT NOT NULL, scope TEXT NOT NULL, citizen_id TEXT,
              source_kind TEXT NOT NULL, source_url TEXT NOT NULL DEFAULT '', source_title TEXT NOT NULL DEFAULT '',
              confidence REAL NOT NULL, status TEXT NOT NULL, tags_json TEXT NOT NULL,
              created_by TEXT NOT NULL, created_at TEXT NOT NULL, approved_by TEXT, approved_at TEXT);
            CREATE INDEX IF NOT EXISTS idx_shared_memory_status ON shared_memories(status,scope,citizen_id,created_at);
            CREATE TABLE IF NOT EXISTS learning_feedback(
              id TEXT PRIMARY KEY, citizen_id TEXT NOT NULL, prompt TEXT NOT NULL, response TEXT NOT NULL,
              rating INTEGER NOT NULL, feedback TEXT NOT NULL, approved_to_learn INTEGER NOT NULL DEFAULT 0,
              processed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS national_audit(
              id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
              entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, details_json TEXT NOT NULL);
            """)
            defaults = [
              ("executive", "Governo e Coordenação", "Coordenação administrativa e execução de decisões aprovadas."),
              ("science", "Ciência e Tecnologia", "Pesquisa, engenharia, experimentação e inovação."),
              ("infrastructure", "Infraestrutura e Energia", "Planejamento de infraestrutura física e digital."),
              ("education", "Educação e Conhecimento", "Formação, documentação e preservação do conhecimento."),
              ("security", "Segurança e Continuidade", "Segurança cibernética, continuidade e gestão de riscos."),
              ("external", "Relações Externas", "Gestão de fontes externas, interoperabilidade e cooperação."),
            ]
            for code, name, mission in defaults:
                c.execute("INSERT OR IGNORE INTO departments(id,code,name,mission,created_at) VALUES(?,?,?,?,?)",
                          (str(uuid4()), code, name, mission, utcnow()))

    def audit(self, actor: str, action: str, entity_type: str, entity_id: str, details: dict[str, Any] | None = None):
        with self.db() as c:
            c.execute("INSERT INTO national_audit VALUES(?,?,?,?,?,?,?)",
                      (str(uuid4()), utcnow(), actor, action, entity_type, entity_id,
                       json.dumps(details or {}, ensure_ascii=False)))

    def departments(self):
        with self.db() as c:
            return [dict(r) for r in c.execute("SELECT * FROM departments ORDER BY name")]

    def create_proposal(self, title: str, description: str, category: str, department_id: str | None, actor: str):
        pid, ts = str(uuid4()), utcnow()
        with self.db() as c:
            if department_id and not c.execute("SELECT 1 FROM departments WHERE id=?", (department_id,)).fetchone():
                raise ValueError("Órgão/departamento não encontrado.")
            c.execute("""INSERT INTO proposals(id,title,description,department_id,category,status,created_by,created_at,updated_at)
                         VALUES(?,?,?,?,?,'draft',?,?,?)""", (pid,title,description,department_id,category,actor,ts,ts))
        self.audit(actor,"proposal.created","proposal",pid,{"title":title})
        return self.get_proposal(pid)

    def get_proposal(self, pid: str):
        with self.db() as c:
            r = c.execute("""SELECT p.*,d.name AS department_name FROM proposals p LEFT JOIN departments d
                            ON d.id=p.department_id WHERE p.id=?""",(pid,)).fetchone()
        return dict(r) if r else None

    def proposals(self, status: str | None = None):
        with self.db() as c:
            sql = "SELECT p.*,d.name AS department_name FROM proposals p LEFT JOIN departments d ON d.id=p.department_id"
            params = []
            if status:
                sql += " WHERE p.status=?"; params.append(status)
            sql += " ORDER BY p.created_at DESC LIMIT 200"
            return [dict(r) for r in c.execute(sql,params)]

    def transition_proposal(self, pid: str, new_status: str, decision: str, actor: str):
        transitions = {"draft":{"under_review"}, "under_review":{"approved","rejected","draft"}}
        if new_status not in {"under_review","approved","rejected","draft"}:
            raise ValueError("Estado de proposta inválido.")
        current = self.get_proposal(pid)
        if not current: raise KeyError("Proposta não encontrada.")
        if new_status not in transitions.get(current["status"], set()):
            raise ValueError(f"Transição não permitida: {current['status']} → {new_status}.")
        if new_status in {"approved","rejected"} and len(decision.strip()) < 5:
            raise ValueError("Registre uma justificativa com pelo menos 5 caracteres.")
        with self.db() as c:
            c.execute("UPDATE proposals SET status=?,decision=?,updated_at=? WHERE id=?",
                      (new_status, decision.strip(), utcnow(), pid))
        self.audit(actor,f"proposal.{new_status}","proposal",pid,{"decision":decision})
        return self.get_proposal(pid)

    def create_deliberation(self, topic: str, prompt: str, citizen_ids: list[str], actor: str):
        did, ts = str(uuid4()), utcnow()
        with self.db() as c:
            c.execute("INSERT INTO deliberations VALUES(?,?,?,?,?,?,?,NULL)",
                      (did,topic,prompt,"running",actor,json.dumps(citizen_ids),ts))
        self.audit(actor,"deliberation.created","deliberation",did,{"participants":citizen_ids})
        return did

    def add_deliberation_turn(self, did: str, citizen_id: str, citizen_name: str, round_no: int,
                              turn_index: int, content: str, model_id: str):
        with self.db() as c:
            c.execute("INSERT INTO deliberation_turns VALUES(?,?,?,?,?,?,?,?,?)",
                      (str(uuid4()),did,citizen_id,citizen_name,round_no,turn_index,content,model_id,utcnow()))

    def finish_deliberation(self, did: str, status: str = "completed"):
        with self.db() as c:
            c.execute("UPDATE deliberations SET status=?,completed_at=? WHERE id=?",(status,utcnow(),did))

    def deliberation(self, did: str):
        with self.db() as c:
            head = c.execute("SELECT * FROM deliberations WHERE id=?",(did,)).fetchone()
            turns = c.execute("SELECT * FROM deliberation_turns WHERE deliberation_id=? ORDER BY round_no,turn_index",(did,)).fetchall()
        if not head: return None
        item = dict(head); item["participants"] = json.loads(item.pop("participants_json")); item["turns"] = [dict(x) for x in turns]
        return item

    def list_deliberations(self):
        with self.db() as c:
            rows = c.execute("SELECT id FROM deliberations ORDER BY created_at DESC LIMIT 100").fetchall()
        return [self.deliberation(r["id"]) for r in rows]

    def add_memory(self, title: str, content: str, memory_type: str, scope: str, citizen_id: str | None,
                   source_kind: str, source_url: str, source_title: str, confidence: float,
                   tags: list[str], actor: str, status: str = "candidate"):
        if not 0 <= confidence <= 1: raise ValueError("Confiança deve ficar entre 0 e 1.")
        if scope not in {"national","citizen"}: raise ValueError("Escopo de memória inválido.")
        if scope == "citizen" and not citizen_id: raise ValueError("Memória individual exige citizen_id.")
        mid, ts = str(uuid4()), utcnow()
        with self.db() as c:
            c.execute("""INSERT INTO shared_memories VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (mid,title,content,memory_type,scope,citizen_id,source_kind,source_url,source_title,
                       confidence,status,json.dumps(tags,ensure_ascii=False),actor,ts,None,None))
        self.audit(actor,"memory.created","memory",mid,{"status":status,"scope":scope})
        return self.get_memory(mid)

    def get_memory(self, mid: str):
        with self.db() as c: r = c.execute("SELECT * FROM shared_memories WHERE id=?",(mid,)).fetchone()
        if not r: return None
        item=dict(r); item["tags"] = json.loads(item.pop("tags_json")); return item

    def memories(self, status: str | None = None, scope: str | None = None, citizen_id: str | None = None):
        sql="SELECT * FROM shared_memories WHERE 1=1"; params=[]
        if status: sql += " AND status=?"; params.append(status)
        if scope: sql += " AND scope=?"; params.append(scope)
        if citizen_id: sql += " AND (scope='national' OR citizen_id=?)"; params.append(citizen_id)
        sql += " ORDER BY created_at DESC LIMIT 300"
        with self.db() as c: rows=c.execute(sql,params).fetchall()
        out=[]
        for r in rows:
            x=dict(r); x["tags"]=json.loads(x.pop("tags_json")); out.append(x)
        return out

    def search_memories(self, query: str, citizen_id: str | None = None, limit: int = 8):
        terms=[t for t in query.strip().split() if len(t)>2][:8]
        if not terms: return []
        conditions=[]; params=[]
        for term in terms:
            conditions.append("(content LIKE ? OR title LIKE ? OR tags_json LIKE ?)")
            like=f"%{term}%"; params.extend([like,like,like])
        sql="SELECT * FROM shared_memories WHERE status='approved' AND (scope='national'"
        if citizen_id:
            sql += " OR (scope='citizen' AND citizen_id=?)"; params.append(citizen_id)
        sql += ") AND ("+" OR ".join(conditions)+") ORDER BY confidence DESC,created_at DESC LIMIT ?"
        params.append(limit)
        with self.db() as c: rows=c.execute(sql,params).fetchall()
        out=[]
        for r in rows:
            x=dict(r); x["tags"]=json.loads(x.pop("tags_json")); out.append(x)
        return out

    def review_memory(self, mid: str, decision: str, actor: str):
        if decision not in {"approved","rejected"}: raise ValueError("Decisão inválida.")
        with self.db() as c:
            cur=c.execute("UPDATE shared_memories SET status=?,approved_by=?,approved_at=? WHERE id=? AND status='candidate'",
                          (decision,actor,utcnow(),mid))
            if not cur.rowcount: raise ValueError("Memória não encontrada ou já revisada.")
        self.audit(actor,f"memory.{decision}","memory",mid)
        return self.get_memory(mid)

    def add_feedback(self, citizen_id: str, prompt: str, response: str, rating: int, feedback: str, approved: bool):
        fid=str(uuid4())
        with self.db() as c:
            c.execute("INSERT INTO learning_feedback VALUES(?,?,?,?,?,?,?,?,?)",
                      (fid,citizen_id,prompt,response,rating,feedback,int(approved),0,utcnow()))
        self.audit("local-operator","learning.feedback","feedback",fid,{"citizen_id":citizen_id,"rating":rating})
        return self.feedback(fid)

    def feedback(self, fid: str):
        with self.db() as c: r=c.execute("SELECT * FROM learning_feedback WHERE id=?",(fid,)).fetchone()
        return dict(r) if r else None

    def feedback_items(self, citizen_id: str | None = None):
        with self.db() as c:
            if citizen_id: rows=c.execute("SELECT * FROM learning_feedback WHERE citizen_id=? ORDER BY created_at DESC LIMIT 300",(citizen_id,)).fetchall()
            else: rows=c.execute("SELECT * FROM learning_feedback ORDER BY created_at DESC LIMIT 300").fetchall()
        return [dict(r) for r in rows]

    def approve_feedback_for_learning(self, fid: str, scope: str, actor: str):
        item=self.feedback(fid)
        if not item: raise KeyError("Feedback não encontrado.")
        if item["processed"]: raise ValueError("Feedback já processado.")
        scope = scope if scope in {"national","citizen"} else "citizen"
        if item["rating"] <= 3 and len(item["feedback"].strip()) < 8:
            raise ValueError("Para transformar uma avaliação baixa em lição, registre uma correção ou explicação humana (mínimo de 8 caracteres).")
        if item["rating"] >= 4:
            memory_title="Exemplo de resposta bem avaliada"
            memory_content=(f"Pergunta: {item['prompt']}\nResposta bem avaliada: {item['response']}\n"
                            f"Nota: {item['rating']}/5. Comentário: {item['feedback']}")
            exportable=1
            tags=["feedback","positive-example"]
        else:
            memory_title="Erro a evitar — correção humana"
            memory_content=(f"Pergunta: {item['prompt']}\nResposta anterior considerada insatisfatória (não a reproduza): "
                            f"{item['response']}\nCorreção/orientação humana: {item['feedback']}")
            exportable=0
            tags=["feedback","negative-example","human-correction"]
        self.add_memory(title=memory_title, content=memory_content, memory_type="lesson",
            scope=scope, citizen_id=item["citizen_id"] if scope=="citizen" else None,
            source_kind="human_feedback", source_url="", source_title="Feedback revisado",
            confidence=min(0.95,0.5+item["rating"]*0.09), tags=tags, actor=actor, status="approved")
        with self.db() as c: c.execute("UPDATE learning_feedback SET processed=1,approved_to_learn=? WHERE id=?",(exportable,fid))
        self.audit(actor,"learning.lesson_added","feedback",fid,{"scope":scope,"exportable":bool(exportable)})
        return self.feedback(fid)

    def training_examples(self, citizen_id: str | None = None):
        sql="SELECT * FROM learning_feedback WHERE approved_to_learn=1"; params=[]
        if citizen_id: sql+=" AND citizen_id=?"; params.append(citizen_id)
        sql+=" ORDER BY created_at"
        with self.db() as c: rows=c.execute(sql,params).fetchall()
        return [{"messages":[{"role":"user","content":r["prompt"]},{"role":"assistant","content":r["response"]}]} for r in rows]

    def audit_events(self, limit: int = 100):
        with self.db() as c: rows=c.execute("SELECT * FROM national_audit ORDER BY timestamp DESC LIMIT ?",(limit,)).fetchall()
        return [{**dict(r),"details":json.loads(r["details_json"])} for r in rows]

    def dashboard(self):
        with self.db() as c:
            return {"departments":c.execute("SELECT COUNT(*) FROM departments WHERE status='active'").fetchone()[0],
                    "proposals":c.execute("SELECT COUNT(*) FROM proposals").fetchone()[0],
                    "deliberations":c.execute("SELECT COUNT(*) FROM deliberations").fetchone()[0],
                    "shared_memories":c.execute("SELECT COUNT(*) FROM shared_memories WHERE status='approved'").fetchone()[0],
                    "pending_memories":c.execute("SELECT COUNT(*) FROM shared_memories WHERE status='candidate'").fetchone()[0],
                    "feedback":c.execute("SELECT COUNT(*) FROM learning_feedback").fetchone()[0]}
